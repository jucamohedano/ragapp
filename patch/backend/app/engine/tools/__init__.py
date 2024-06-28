import os
import yaml
import json
import importlib
from cachetools import cached, LRUCache
from llama_index.core.tools.tool_spec.base import BaseToolSpec
from llama_index.core.tools.function_tool import FunctionTool
from app.api.routers.events import EventCallbackHandler, ExtendedCBEventType
import uuid
import time


class ToolType:
    LLAMAHUB = "llamahub"
    LOCAL = "local"

from qdrant_client import QdrantClient, models
import pandas as pd

def generate_report(event_handler):
    qdrant_client = QdrantClient(host='localhost', port=6333)  # Update with actual host and port if different

    # Check if the "events" collection exists and delete it if it does
    if qdrant_client.collection_exists(collection_name="events"):
        qdrant_client.delete_collection(collection_name="events")
    time.sleep(1.0)
    # Create the "events" collection
    qdrant_client.create_collection(collection_name="events",
                                    vectors_config=models.VectorParams(size=4, 
                                                                       distance=models.Distance.COSINE))


    # Check if the "requirement" collection exists
    if not qdrant_client.collection_exists(collection_name="requirement"):
        raise ValueError("Collection 'requirement' does not exist in the database.")
    # Check if the "description" collection exists
    if not qdrant_client.collection_exists(collection_name="description"):
        raise ValueError("Collection 'description' does not exist in the database.")
    
    req_records = qdrant_client.scroll(collection_name="requirement", 
                                         limit=1000, # Adjust limit as needed
                                         with_vectors=True, 
                                         with_payload=True)[0]
    # Check if the "requirement" collection is empty
    if not req_records:
        raise ValueError("Collection 'requirement' is empty.")
    
    def find_top_match(requirement_vector):
        event_handler.emit(ExtendedCBEventType.TOP_MATCH_START, {"top_match_start":"started the search"})
        search_result = qdrant_client.search(
            collection_name="description",
            query_vector=requirement_vector,
            limit=1,
            search_params=models.SearchParams(
                hnsw_ef=200,  # Adjust this parameter as needed for optimal accuracy
                exact=False
            ),
            with_payload=True
        )
        event_handler.emit(ExtendedCBEventType.TOP_MATCH_END, {"top_match_end":"finished the search"})
        return search_result[0] if search_result else None
    
    # Prepare results list
    results = []
    prompts = []

    # Iterating over req_records
    for index, req_record in enumerate(req_records):
        # Generate UUID for the event
        event_uuid = str(uuid.uuid4())
        # Generate current timestamp
        timestamp = int(time.time())
        # Generate Event Text
        event_text = f"Retrieving Context for Requirement {index+1}..."
        
        # Insert event record into the "events" collection
        qdrant_client.upsert(
            collection_name="events",
            points=[
                models.PointStruct(
                    id=index,
                    payload={
                        "UUID": event_uuid,
                        "Request ID": req_record.payload['ID'],
                        "Event Text": event_text,
                        "Timestamp": timestamp
                    },
                    vector=[0.9, 0.1, 0.1, 0.1],
                ),])
        
        time.sleep(1)
        
        match = find_top_match(req_record.vector)
        
        node_content_str = req_record.payload['_node_content']
        node_content = json.loads(node_content_str)
        if match:
            match_content_str = match.payload['_node_content']
            match_content = json.loads(match_content_str)
            result_row = {
                'Requirement ID': req_record.payload['ID'],
                'Requirement Text': node_content.get('text'),
                'Description ID': match.payload['ID'],
                'Description Text': match_content.get('text'),
                'Similarity Score': match.score
            }

            prompt = (\
            f"Requirement: {result_row['Requirement Text']}\n"
            f"Capability: {result_row['Description Text']}\n")
            prompts.append(prompt)
            results.append(result_row)
    return prompts, results, qdrant_client, len(req_records)

from llama_index.core.query_engine import CustomQueryEngine
from llama_index.llms.ollama import Ollama
from llama_index.core import PromptTemplate
event_handler = EventCallbackHandler()
class RAGStringQueryEngine(CustomQueryEngine):
    """RAG String Query Engine."""

    # retriever: BaseRetriever
    # response_synthesizer: BaseSynthesizer
    llm: Ollama
    qa_prompt: PromptTemplate
    event_handler: EventCallbackHandler

    def custom_query(self, query_str: str):
        # event_handler = EventCallbackHandler()

        try:
            prompts, results, qdrant_client, num_records = generate_report(self.event_handler)
        except Exception as e:
            return f"Error generating report: {e}"
        results_df = pd.DataFrame(results)
        responses = []
        # Initialize lists to store the Llama3 results
        llm_results = []
        llm_reasons = []
        # print(f"There are {len(prompts)} prompts")
        for index, prompt in enumerate(prompts):
            # Splitting the text to extract Requirement and Capability
            event_handler.emit(ExtendedCBEventType.REASONING_START, {"reasoning_start":"started reasoning over req and desc"})
            requirement = prompt.split("Capability:")[0].strip().replace("Requirement: ", "")
            capability = prompt.split("Capability:")[1].strip()
            # Generate UUID for the event
            event_uuid = str(uuid.uuid4())
            # Generate current timestamp
            timestamp = int(time.time())
            # Generate Event Text
            event_text = f"Reasoning with Context for Requirement {index+1}..."
            
            # Insert event record into the "events" collection
            qdrant_client.upsert(
                collection_name="events",
                points=[
                    models.PointStruct(
                        id=num_records+index,
                        payload={
                            "UUID": event_uuid,
                            "Request ID": str(uuid.uuid4()),
                            "Event Text": event_text,
                            "Timestamp": timestamp
                        },
                        vector=[0.9, 0.1, 0.1, 0.1],
                    ),])
            response = self.llm.complete(
                self.qa_prompt.format(requirement_text=requirement, description_text=capability)
            )

            responses.append(response)

            try:
                response_json = json.loads(response.json())
            except json.JSONDecodeError:
                response_json = {}

                time.slee(1.0)
            try:
                response_text = response_json.get('text', '{}')
                print(100*"-")
                print(response_json)
                print(100*"-")
                response_json = json.loads(response_text)
                print(100*"%")
                print(response_json)
                print(100*"%")

                # Handle both cases: when Result and Reason are nested or simple key-value pairs
                if isinstance(response_json.get("Result"), dict):
                    result = response_json.get("Result", {}).get("Result", "N/A")
                    print("result is nested: ", result)
                else:
                    result = response_json.get("Result", "N/A")

                if isinstance(response_json.get("Reason"), dict):
                    reason = response_json.get("Reason", {}).get("Reason", "N/A")
                    print("reason is nested: ", result)
                else:
                    reason = response_json.get("Reason", "N/A")

            except (TypeError, json.JSONDecodeError) as e:
                print(f"Error parsing JSON response: {e}")
                # result = "Error"
                # reason = "Error parsing response"
                print(response_json)
                return f"Error generating report: {e}"
            
            event_handler.emit(ExtendedCBEventType.REASONING_END, {"reasoning_end":"finished reasoning over req and desc"})

            llm_results.append(result)
            llm_reasons.append(reason)

            # Update the DataFrame and write to the Excel file incrementally
            results_df.at[index, 'Result'] = result
            results_df.at[index, 'Reason'] = reason
            
        save_dir = "reports/Results-LLM.xlsx"
        results_df.to_excel(save_dir, index=False, columns=[
            'Requirement ID',
            'Requirement Text',
            'Description ID',
            'Description Text',
            'Similarity Score',
            'Result',
            'Reason'
        ])
        qdrant_client.upsert(
                collection_name="events",
                points=[
                    models.PointStruct(
                        id=11111,
                        payload={
                            "UUID": event_uuid,
                            "Request ID": str(uuid.uuid4()),
                            "Event Text": "Results-LLM.xlsx",
                            "Timestamp": timestamp
                        },
                        vector=[0.9, 0.1, 0.1, 0.1],
                    ),])

        return f"Report between requirements and descriptions was generated and saved to Excel file in {save_dir}."

class ToolFactory:

    TOOL_SOURCE_PACKAGE_MAP = {
        ToolType.LLAMAHUB: "llama_index.tools",
        ToolType.LOCAL: "app.engine.tools",
    }

    def load_tools(tool_type: str, tool_name: str, config: dict) -> list[FunctionTool]:
        source_package = ToolFactory.TOOL_SOURCE_PACKAGE_MAP[tool_type]
        try:
            if "ToolSpec" in tool_name:
                tool_package, tool_cls_name = tool_name.split(".")
                module_name = f"{source_package}.{tool_package}"
                module = importlib.import_module(module_name)
                tool_class = getattr(module, tool_cls_name)
                tool_spec: BaseToolSpec = tool_class(**config)
                return tool_spec.to_tool_list()
            else:
                module = importlib.import_module(f"{source_package}.{tool_name}")
                tools = module.get_tools()
                if not all(isinstance(tool, FunctionTool) for tool in tools):
                    raise ValueError(
                        f"The module {module} does not contain valid tools"
                    )
                return tools
        except ImportError as e:
            raise ValueError(f"Failed to import tool {tool_name}: {e}")
        except AttributeError as e:
            raise ValueError(f"Failed to load tool {tool_name}: {e}")

    @staticmethod
    def from_env() -> list[FunctionTool]:
        tools = []
        if os.path.exists("config/tools.yaml"):
            with open("config/tools.yaml", "r") as f:
                tool_configs = yaml.safe_load(f)
                for tool_type, config_entries in tool_configs.items():
                    for tool_name, config in config_entries.items():
                        tools.extend(
                            ToolFactory.load_tools(tool_type, tool_name, config)
                        )
        if len(tools) != 0:
            for tool in tools:
                print(tool.metadata)
        return tools
import json
import uuid
import time

from app.api.routers.events import EventCallbackHandler, ExtendedCBEventType
from qdrant_client import QdrantClient, models
import pandas as pd

from llama_index.core.query_engine import CustomQueryEngine
from llama_index.llms.ollama import Ollama
from llama_index.core import PromptTemplate

def insert_event_record(qdrant_client, collection_name, event_text, index):
    event_uuid = str(uuid.uuid4())
    timestamp = int(time.time())
    # event_text = event_text_template.format(index=index+1)
    
    qdrant_client.upsert(
        collection_name=collection_name,
        points=[
            models.PointStruct(
                id=index,
                payload={
                    "UUID": event_uuid,
                    "Request ID": str(uuid.uuid4()),
                    "Event Text": event_text,
                    "Timestamp": timestamp
                },
                vector=[0.9, 0.1, 0.1, 0.1],
            ),
        ]
    )


class ComplianceQueryEngine(CustomQueryEngine):
    """RAG String Query Engine."""

    # retriever: BaseRetriever
    # response_synthesizer: BaseSynthesizer
    llm: Ollama
    qa_prompt: PromptTemplate


    def custom_query(self, query_str: str):
        event_handler = EventCallbackHandler()
        qdrant_client = QdrantClient(host='localhost', port=6333)  # Update with actual host and port if different

        # Check if the "events" collection exists and delete it if it does
        if qdrant_client.collection_exists(collection_name="events"):
            qdrant_client.delete_collection(collection_name="events")
            raise Exception("Collection already exists")
        # Create the "events" collection
        qdrant_client.create_collection(
                                collection_name="events",
                                vectors_config=models.VectorParams(
                                                size=4, 
                                                distance=models.Distance.COSINE
                                        ))
        

        try:
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
            responses = []
            llm_results = []
            llm_reasons = []
            results_df = pd.DataFrame()

            # Iterating over req_records
            for index, req_record in enumerate(req_records):
                req_event_text = f"Retrieving Context for Requirement {index+1}..."
                insert_event_record(qdrant_client, "events", req_event_text, index)
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

                    results.append(result_row)
                    # append new results to results_df
                    new_df = pd.DataFrame.from_records(results)
                    # concatenate new_df with the initially empty results_df
                    results_df = pd.concat([results_df, new_df], ignore_index=True)
                    
                    time.sleep(1.0)
                    event_handler.emit(ExtendedCBEventType.REASONING_START, {"reasoning_start":"started reasoning over req and desc"})
                    reasoning_event_text = f"Reasoning with Context for Requirement {index+1}..."
                    insert_event_record(qdrant_client, "events", reasoning_event_text, index+1)
                    
                    print(self.qa_prompt.format(
                                    requirement_text=result_row['Requirement Text'], 
                                    description_text=result_row['Description Text']))
                    response = self.llm.complete(
                                self.qa_prompt.format(
                                    requirement_text=result_row['Requirement Text'], 
                                    description_text=result_row['Description Text']),
                                formatted=True
                            )
                    

                    responses.append(response)

                    try:
                        response_json = json.loads(response.json())
                    except json.JSONDecodeError:
                        response_json = {}

                        time.slee(1.0)
                    try:
                        response_text = response_json.get('text', '{}')
                        response_json = json.loads(response_text)

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

                        time.sleep(1.0)

                    except (TypeError, json.JSONDecodeError) as e:
                        print(f"Error parsing JSON response: {e}")
                        print()
                        print(100*"&")
                        print(response_json)
                        print(100*"&")
                        print()
                        return f"Error generating report: {e}"
                    try:
                        response_json = json.loads(response.json())
                    except json.JSONDecodeError as e:
                        print(f"Error decoding initial JSON response: {e}")
                        response_json = {}



                    except (TypeError, ValueError, json.JSONDecodeError) as e:
                        print(f"Error parsing JSON response: {e}")
                        print(100*"&")
                        print(response_json)
                        print(100*"&")
                        return f"Error generating report: {e}"
                    event_handler.emit(ExtendedCBEventType.REASONING_END, {"reasoning_end":"finished reasoning over req and desc"})

                    llm_results.append(result)
                    llm_reasons.append(reason)

                    # Update the DataFrame and write to the Excel file incrementally
                    results_df.at[index, 'Result'] = result
                    results_df.at[index, 'Reason'] = reason

        except Exception as e:
            return f"Error generating report: {e}"
            
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
        insert_event_record(qdrant_client=qdrant_client, 
                            collection_name="events", 
                            event_text="Results-LLM.xlsx", 
                            index=len(req_records)*2)
        return f"Report between requirements and descriptions was generated and saved to Excel file in {save_dir}."
    
def get_compliance_tool():
    from llama_index.core.tools.query_engine import QueryEngineTool
    from llama_index.core.settings import Settings


    # qa_prompt = PromptTemplate(
    #     # "You are a deeply analytical person who I trust to identify commonalities and differences between a pair of statements. \n"
    #     "Statement 1 will represent the Requirement. Statement 2 will represent the Capability. This is the INPUT. You need to deduce whether the Capability can fulfill the Requirement and OUTPUT a Result (possible choices: Yes, No, Partial) and Reason.\n"
    #     "Requirement: {requirement_text}\n"
    #     "Capability: {description_text}\n"
    #     "Respond in JSON of the form:\n:\n"
    #     '{{\n  "Result": {{\n    "Result": "Yes"\n  }},\n  "Reason": {{\n    "Reason": "n77 bands are supported by this capability."\n  }}\n}}'
    # )

    qa_prompt = PromptTemplate(
        "I need you to carefully identify commonalities and differences between a pair of statements.\n"
        "The first statement is the Requirement. The second statement is the Capability.\n "
        "You need to deduce whether the Capability can fulfill the Requirement, producing a Result.\n"
        "Your Result choices are: Yes, No, Partial. You should also generate a Reason for why you picked your choice.\n"
        "Requirement: {requirement_text}\n"
        "Capability: {description_text}\n"
        "Respond in JSON of the form:\n\n"
        '{{\n  "Result": {{\n    "Result": "Yes"\n  }},\n  "Reason": {{\n    "Reason": "n77 bands are supported by this capability."\n  }}\n}}'
    )

    compliance_query_engine = ComplianceQueryEngine(llm=Settings.llm, qa_prompt=qa_prompt)
    generate_report_tool = QueryEngineTool.from_defaults(
        query_engine=compliance_query_engine,
        name="generate_report",
        description= "Tool Name: Compliance Check\n Trigger Prompt: Perform Compliance Check\n Tool Description: Performs compliance check between requirements and capabilities in order to produce a report.",
    )

    return generate_report_tool
import os
import json
import uuid
import time

from app.api.routers.events import EventCallbackHandler, ExtendedCBEventType
from qdrant_client import QdrantClient, models
import pandas as pd

from llama_index.core.query_engine import CustomQueryEngine
from llama_index.llms.ollama import Ollama
from llama_index.core import PromptTemplate

from typing import List
from pydantic import BaseModel

from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.callbacks.schema import CBEventType, EventPayload
from llama_index.core.base.response.schema import RESPONSE_TYPE
from typing import Any, List, Optional, Sequence


import llama_index.core.instrumentation as instrument
dispatcher = instrument.get_dispatcher(__name__)

class ComplianceOutput(BaseModel):
    """Data model for a Compliance Check output."""

    result: str
    reason: str
    extra_info: str = None

class ComplianceQueryEngine(CustomQueryEngine):
    """Compliance Check Query Engine."""

    # retriever: BaseRetriever
    # response_synthesizer: BaseSynthesizer
    llm: Ollama
    qa_prompt: PromptTemplate


    def _insert_event_record(self, qdrant_client, collection_name, event_text, index, url=None):
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
                        "Timestamp": timestamp,
                        "fileUrl": url,
                    },
                    vector=[0.9, 0.1, 0.1, 0.1],
                ),
            ]
        )


    def custom_query(self, query_str: str):
        event_handler = EventCallbackHandler()
        qdrant_client = QdrantClient(url=os.getenv('QDRANT_URL'))

        # Check if the "events" collection exists and delete it if it does
        if qdrant_client.collection_exists(collection_name="events"):
            qdrant_client.delete_collection(collection_name="events")

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
                return "Report to the user that the collection 'requirement' does not exist in the database and we can't perform the compliance check."
                # raise ValueError("Collection 'requirement' does not exist in the database.")
            # Check if the "description" collection exists
            if not qdrant_client.collection_exists(collection_name="description"):
                return "Report to the user that the collection 'description' does not exist in the database and we can't perform the compliance check."
                # raise ValueError("Collection 'description' does not exist in the database.")
            
            req_records = qdrant_client.scroll(collection_name="requirement", 
                                                limit=1000, # Adjust limit as needed
                                                with_vectors=True, 
                                                with_payload=True)[0]
            # Check if the "requirement" collection is empty
            if not req_records:
                return "Report to the user that the collection 'requirement' in the database is empty and that they need to upload data to the colleciton requirement."
                # raise ValueError("Collection 'requirement' is empty.")
            
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
            responses = []
            llm_results = []
            llm_reasons = []
            results_df = pd.DataFrame()
            last_index = None

            # Iterating over req_records
            for index, req_record in enumerate(req_records):
                req_event_text = f"Retrieving Context for Requirement {index+1}..."
                print(req_event_text)
                self._insert_event_record(qdrant_client, "events", req_event_text, index*3)
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
                    
                    time.sleep(1.0)
                    event_handler.emit(ExtendedCBEventType.REASONING_START, {"reasoning_start":"started reasoning over req and desc"})
                    reasoning_event_text = f"Reasoning with Context for Requirement {index+1}..."
                    print(reasoning_event_text)
                    self._insert_event_record(qdrant_client, "events", reasoning_event_text, (index*3)+1)
                    
                    response = self.llm.complete(
                                self.qa_prompt.format(
                                    requirement_text=result_row['Requirement Text'], 
                                    description_text=result_row['Description Text']),
                            )

                    responses.append(response)

                    try:
                        response_json = json.loads(response.text)

                        # Extract nested or direct values for Result and Reason
                        def extract_value(data, key):
                            if isinstance(data.get(key), dict):
                                return data.get(key, {}).get(key, "N/A")
                            return data.get(key, "N/A")

                        result = extract_value(response_json, "Result")
                        reason = extract_value(response_json, "Reason")

                        time.sleep(1.0)

                    except (TypeError, json.JSONDecodeError) as e:
                        qdrant_client.delete_collection(collection_name="events")
                        print(f"Error parsing JSON response: {e}")
                        print(100 * "&")
                        print(response)
                        print(100 * "&")
                        return "Report to the user that there was an error in the JSON structure produced by the LLM to generate the compliance report."

                    event_handler.emit(ExtendedCBEventType.REASONING_END, {"reasoning_end": "finished reasoning over req and desc"})


                    llm_results.append(result)
                    llm_reasons.append(reason)

                    # Update the DataFrame
                    persist_event_text = f"Persisting result to spreadsheet..."
                    print(persist_event_text)
                    self._insert_event_record(qdrant_client, "events", persist_event_text, (index*3)+2)
                    time.sleep(1.0)
                    last_index = (index*3)+2

                    print()
                    print()
                    print(f"full response:\n {response}\n")
                    print(f"result: {result}")
                    print(f"reason: {reason}")
                    print(f"index: {index}")
                    print()
                    print()


                    result_row['Result'] = result
                    result_row['Reason'] = reason
                    results.append(result_row)
            results_df = pd.DataFrame.from_records(results)

        except Exception as e:
            qdrant_client.delete_collection(collection_name="events")
            return "Report to the user that there was an error while generating the compliance report."
            
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

        self._insert_event_record(qdrant_client=qdrant_client, 
                            collection_name="events", 
                            event_text="Results-LLM.xlsx", 
                            index=last_index+1,
                            url='/api/chat/download')
        time.sleep(5.0)
        return f"Report to the user that requirements compliance report is ready and nothing else."

    
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
    compliance_check_tool = QueryEngineTool.from_defaults(
        query_engine=compliance_query_engine,
        name="compliance_check",
        description= "Tool Name: Compliance Check\n Trigger Prompt: Perform Compliance Check\n Tool Description: Performs compliance check between requirements and capabilities in order to produce a report.",
        # return_direct=True
    )

    return compliance_check_tool


def get_compliance_engine():
    from llama_index.core import get_response_synthesizer
    from llama_index.core.settings import Settings

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
    
    compliance_query_engine = ComplianceQueryEngine(llm=Settings.llm, 
                                                    qa_prompt=qa_prompt)
    return compliance_query_engine
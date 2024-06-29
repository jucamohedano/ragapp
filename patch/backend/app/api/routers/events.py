import json
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
from llama_index.core.callbacks.base import BaseCallbackHandler
from llama_index.core.callbacks.schema import CBEventType
from llama_index.core.tools.types import ToolOutput
from pydantic import BaseModel
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

# Extending CBEventType with more values
class ExtendedCBEventType(Enum):
    # Include existing values from CBEventType
    CHUNKING = CBEventType.CHUNKING.value
    NODE_PARSING = CBEventType.NODE_PARSING.value
    EMBEDDING = CBEventType.EMBEDDING.value
    LLM = CBEventType.LLM.value
    QUERY = CBEventType.QUERY.value
    RETRIEVE = CBEventType.RETRIEVE.value
    SYNTHESIZE = CBEventType.SYNTHESIZE.value
    TREE = CBEventType.TREE.value
    SUB_QUESTION = CBEventType.SUB_QUESTION.value
    TEMPLATING = CBEventType.TEMPLATING.value
    FUNCTION_CALL = CBEventType.FUNCTION_CALL.value
    RERANKING = CBEventType.RERANKING.value
    EXCEPTION = CBEventType.EXCEPTION.value
    AGENT_STEP = CBEventType.AGENT_STEP.value
    # Add new values
    TOP_MATCH_START = "top_match_start"
    TOP_MATCH_END = "top_match_end"
    REASONING_START = "reasoning_start"
    REASONING_END = "reasoning_end"
    

class CallbackEvent(BaseModel):
    event_type: ExtendedCBEventType
    payload: Optional[Dict[str, Any]] = None
    event_id: str = ""

    def get_retrieval_message(self) -> dict | None:
        if self.payload:
            nodes = self.payload.get("nodes")
            if nodes:
                msg = f"Retrieved {len(nodes)} sources to use as context for the query"
            else:
                msg = f"Retrieving context for query: '{self.payload.get('query_str')}'"
            return {
                "type": "events",
                "data": {"title": msg},
            }
        else:
            return None

    def get_tool_message(self) -> dict | None:
        func_call_args = self.payload.get("function_call")
        if func_call_args is not None and "tool" in self.payload:
            tool = self.payload.get("tool")
            return {
                "type": "events",
                "data": {
                    "title": f"Calling tool: {tool.name} with inputs: {func_call_args}",
                },
            }

    def _is_output_serializable(self, output: Any) -> bool:
        try:
            json.dumps(output)
            return True
        except TypeError:
            return False

    def get_agent_tool_response(self) -> dict | None:
        response = self.payload.get("response")
        if response is not None:
            sources = response.sources
            for source in sources:
                # Return the tool response here to include the toolCall information
                if isinstance(source, ToolOutput):
                    if self._is_output_serializable(source.raw_output):
                        output = source.raw_output
                    else:
                        output = source.content

                    return {
                        "type": "tools",
                        "data": {
                            "toolOutput": {
                                "output": output,
                                "isError": source.is_error,
                            },
                            "toolCall": {
                                "id": None,  # There is no tool id in the ToolOutput
                                "name": source.tool_name,
                                "input": source.raw_input,
                            },
                        },
                    }

    def to_response(self):
        # print(f'event type: {self.event_type}')
        try:
            match self.event_type:
                case "retrieve":
                    return self.get_retrieval_message()
                case "function_call":
                    return self.get_tool_message()
                case "agent_step":
                    return self.get_agent_tool_response()
                case "top_match_start":
                    return {
                            "type": "events",
                            "data": {"title": "top match start!"},
                        }
                case "top_match_end":
                    return {
                            "type": "events",
                            "data": {"title": "top match end!"},
                        }
                case "reasoning_start":
                    return {
                            "type": "events",
                            "data": {"title": "Start reasoning between requirement and description"},
                        }
                case "reasoning_end":
                    return {
                            "type": "events",
                            "data": {"title": "End reasoning between requirement and description"},
                        }
                case _:
                    return None
        except Exception as e:
            logger.error(f"Error in converting event to response: {e}")
            return None


from fastapi import WebSocket
class EventCallbackHandler(BaseCallbackHandler):
    _aqueue: asyncio.Queue
    is_done: bool = False
    websocket: Optional[WebSocket] = None
    current_event: Optional[dict] = None
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(EventCallbackHandler, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the base callback handler."""
        ignored_events = [
            ExtendedCBEventType.CHUNKING,
            ExtendedCBEventType.NODE_PARSING,
            ExtendedCBEventType.EMBEDDING,
            ExtendedCBEventType.LLM,
            ExtendedCBEventType.TEMPLATING,
        ]
        super().__init__(ignored_events, ignored_events)
        self._aqueue = asyncio.Queue()

    def on_event_start(self, event_type: ExtendedCBEventType, payload: Optional[Dict[str, Any]] = None, event_id: str = "", **kwargs: Any) -> str:
        event = CallbackEvent(event_id=event_id, event_type=event_type, payload=payload)
        if event.to_response() is not None:
            self._aqueue.put_nowait(event)

    def on_event_end(self, event_type: ExtendedCBEventType, payload: Optional[Dict[str, Any]] = None, event_id: str = "", **kwargs: Any) -> None:
        event = CallbackEvent(event_id=event_id, event_type=event_type, payload=payload)
        if event.to_response() is not None:
            self._aqueue.put_nowait(event)

    async def async_event_gen(self) -> AsyncGenerator[CallbackEvent, None]:
        while not self._aqueue.empty() or not self.is_done:
            try:
                yield await asyncio.wait_for(self._aqueue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                pass

    def emit(self, event_type: ExtendedCBEventType, payload: Optional[Dict[str, Any]] = None) -> None:
        self.current_event = {"event type": str(event_type)}
        event_id = str(uuid.uuid4())  # Generate a unique event ID
        event = CallbackEvent(event_id=event_id, event_type=event_type, payload=payload)
        if event.to_response() is not None:
            self._aqueue.put_nowait(event)

    def start_trace(self, trace_id: Optional[str] = None) -> None:
        """No-op."""

    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """No-op."""
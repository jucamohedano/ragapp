import logging
from typing import Optional, Annotated, List
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.controllers.tools import ToolsManager, tools_manager
from src.models.tools import Tools

tools_router = r = APIRouter()

logger = logging.getLogger("uvicorn")


@r.get("")
def get_tools(
    tools_manager: Annotated[ToolsManager, Depends(tools_manager)],
) -> Tools:
    """
    Get all configured tools.
    """
    return tools_manager.get_tools()


@r.post("/{tool_name}")
def update_tool(
    tool_name: str,
    data: dict,
    tools_manager: Annotated[ToolsManager, Depends(tools_manager)],
) -> JSONResponse:
    """
    Update a tool configuration.
    """
    tools_manager.update_tool(tool_name, data)
    if tool_name == "requirementsCompliance" and data.get("enabled"):
        run_requirements_compliance()
    return JSONResponse(content={"message": "Tool updated."})


def run_requirements_compliance():
    from app.engine.tools import RAGStringQueryEngine
    from llama_index.core.settings import Settings
    from llama_index.core import PromptTemplate
    # from llama_index.core.tools.query_engine import QueryEngineTool


    qa_prompt = PromptTemplate(
        "Requirement: {requirement_text}\n"
        "Capability: {description_text}\n"
        "Respond in JSON of the form:\n"
        '{{\n  "Result": {{\n    "Result": "Yes"\n  }},\n  "Reason": {{\n    "Reason": "n77 bands are supported by this capability."\n  }}\n}}'
    )
    similarity_query_engine = RAGStringQueryEngine(llm=Settings.llm, qa_prompt=qa_prompt)
    similarity_query_engine.query("Generate a report based on the requirements and descriptions collections in Qdrant")
    

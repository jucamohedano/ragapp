import os
from llama_index.core.settings import Settings
from llama_index.core.agent import AgentRunner
from app.engine.tools import ToolFactory, generate_report, RAGStringQueryEngine, event_handler
from app.engine.index import get_index
from functools import partial
from llama_index.core.tools.function_tool import FunctionTool
from llama_index.core import PromptTemplate


def get_chat_engine():
    
    top_k = int(os.getenv("TOP_K", "3"))
    system_prompt = os.getenv("SYSTEM_PROMPT")

    index = get_index()
    if index is None:
        raise RuntimeError("Index is not found")

    tools = ToolFactory.from_env()
    from llama_index.core.tools.query_engine import QueryEngineTool

    # Add the query engine tool to the list of tools
    query_engine_tool = QueryEngineTool.from_defaults(
        query_engine=index.as_query_engine(similarity_top_k=top_k)
    )
    tools.append(query_engine_tool)

    # add custom query engine
    qa_prompt = PromptTemplate(
        "You are a deeply analytical person who I trust to identify commonalities and differences between a pair of statements. \n"
        "Statement 1 will represent the Requirement. Statement 2 will represent the Capability. This is the INPUT. You need to deduce whether the Capability can fulfill the Requirement and OUTPUT a Result (possible choices: Yes, No, Partial) and Reason.\n"
        "Requirement: {requirement_text}\n"
        "Capability: {description_text}\n"
        "Strictly follow the format in JSON of the form:\n"
        '{{\n  "Result": {{\n    "Result": "Yes"\n  }},\n  "Reason": {{\n    "Reason": "n77 bands are supported by this capability."\n  }}\n}}'
    )
    # qa_prompt = PromptTemplate(
    # "Requirement: {requirement_text}\n"
    # "Capability: {description_text}\n"
    # "Respond in JSON following the structure in the next example:\n"
    # '{{\n  "Result": {{\n    "Result": "Yes" or "No"\n  }},\n  "Reason": {{\n    "Reason": "Provide a detailed reason here."\n  }}\n}}\n'
    # "Ensure that the JSON is correctly formatted and all fields are included exactly as specified."
    # )
    similarity_query_engine = RAGStringQueryEngine(llm=Settings.llm, qa_prompt=qa_prompt, event_handler=event_handler)
    generate_report_tool = QueryEngineTool.from_defaults(
        query_engine=similarity_query_engine,
        name="generate_report_tool",
        description="Generate a report based on the requirements \
                    and descriptions collections in Qdrant. \
                    Notify the user whether the task was successful or unsuccessful.")

    # generate_report_tool = FunctionTool.from_defaults(
    #     fn=generate_report,
    #     name="generate_report",
    #     description="Generate a report based on the requirements and descriptions collections in Qdrant",
    # )
    tools.append(generate_report_tool)

    # Use the context chat engine if no tools are provided
    if len(tools) == 0:
        from llama_index.core.chat_engine import CondensePlusContextChatEngine

        return CondensePlusContextChatEngine.from_defaults(
            retriever=index.as_retriever(top_k=top_k),
            system_prompt=system_prompt,
            llm=Settings.llm,
        )
    else:
        from llama_index.core.agent import AgentRunner
        # from llama_index.core.tools.query_engine import QueryEngineTool

    #     # Add the query engine tool to the list of tools
    #     query_engine_tool = QueryEngineTool.from_defaults(
    #         query_engine=index.as_query_engine(similarity_top_k=top_k)
    #     ) 
    #     tools.append(query_engine_tool)

    #     generate_report_tool = FunctionTool.from_defaults(
    #         # fn=generate_report,
    #         fn=partial(generate_report, event_handler=event_handler),
    #         name="generate_report", 
    #         description="Generate a report based on the requirements and descriptions collections in Qdrant",
    #     )
        # tools.append(generate_report_tool)
        return AgentRunner.from_llm(
            llm=Settings.llm,
            tools=tools,
            system_prompt=system_prompt,
            verbose=True,  # Show agent logs to console
        )

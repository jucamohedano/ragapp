from llama_index.core.tools.function_tool import FunctionTool

def requirements_compliance():
    """
    Generate a report based on the requirements and descriptions collections in Qdrant.
    """
    try:
        from __init__ import generate_report
    except ImportError:
        raise ImportError(
            "generate_report function is required to use this function."
            "Please ensure it is defined in __init__.py within the current directory."
        )

    prompts, results = generate_report()
    return results

def get_tools():
    return [FunctionTool.from_defaults(requirements_compliance)]
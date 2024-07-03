import os
import logging
from llama_parse import LlamaParse
from pydantic import BaseModel, validator
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


class FileLoaderConfig(BaseModel):
    data_dir: str = "data"
    use_llama_parse: bool = False

    @validator("data_dir")
    def data_dir_must_exist(cls, v):
        if not os.path.isdir(v):
            raise ValueError(f"Directory '{v}' does not exist")
        return v


def llama_parse_parser():
    if os.getenv("LLAMA_CLOUD_API_KEY") is None:
        raise ValueError(
            "LLAMA_CLOUD_API_KEY environment variable is not set. "
            "Please set it in .env file or in your shell environment then run again!"
        )
    parser = LlamaParse(
        result_type="markdown",
        verbose=True,
        language="en",
        ignore_errors=False,
    )
    return parser

# Function to read the CSV file conditionally
def csv_has_col(directory_path, column_name):
    # Read the first row of the CSV to check if the "Description" column exists
    files = list(Path(directory_path).glob("*.csv"))
    # Check if there are any CSV files in the directory
    if not files:
        raise FileNotFoundError("No CSV files found in the directory")
    
    # should be just one file for now
    csv_file_path = files[0]
    first_row = pd.read_csv(csv_file_path, nrows=1)
    
    # Check if "Description" column exists
    if column_name in first_row.columns:
        return True
    return False
    

def get_file_documents(config: FileLoaderConfig):
    from llama_index.core.readers import SimpleDirectoryReader
    from llama_index.readers.file import PandasCSVReader
    from llama_index.core import Document

    try:
        # CSV Reader example
        if csv_has_col(config.data_dir, column_name="Description"):
            pandas_config={'usecols':['ID','Description']}
        elif csv_has_col(config.data_dir, column_name="Sub-requirement Text"):
            pandas_config={'usecols':['Requirement ID','Sub-requirement Text']}
        else:
            pandas_config={}
        parser = PandasCSVReader(concat_rows=False, pandas_config=pandas_config)
        file_extractor = {".csv": parser}  # Add other CSV formats as needed
        reader = SimpleDirectoryReader(
            config.data_dir,
            recursive=True,
            filename_as_id=True,
            raise_on_error=True,
            file_extractor=file_extractor
        )
        if config.use_llama_parse:
            # LlamaParse is async first,
            # so we need to use nest_asyncio to run it in sync mode
            import nest_asyncio

            nest_asyncio.apply()

            parser = llama_parse_parser()
            reader.file_extractor = {".pdf": parser}
        
        # Load data
        data = reader.load_data()
        # Post-process to extract only the Description column
        processed_data = []
        for document in data:
            # Read the document text into a DataFrame
            split_doc = document.text.split(',', maxsplit=1)
            id = split_doc[0]
            doc = Document(text=split_doc[1], metadata={"ID": id})
            processed_data.append(doc)
        return processed_data
    except Exception as e:
        import sys, traceback

        # Catch the error if the data dir is empty
        # and return as empty document list
        _, _, exc_traceback = sys.exc_info()
        function_name = traceback.extract_tb(exc_traceback)[-1].name
        if function_name == "_add_files":
            logger.warning(
                f"Failed to load file documents, error message: {e} . Return as empty document list."
            )
            return []
        else:
            # Raise the error if it is not the case of empty data dir
            raise e

import os
import importlib
import logging

logger = logging.getLogger(__name__)


def get_vector_store(collection_name=None):
    provider = os.getenv("VECTOR_STORE_PROVIDER", "chroma")
    provider = 'qdrant'
    try:
        module = importlib.import_module(f"app.engine.vectordbs.{provider}")
        logger.info(f"Using vector provider: {provider}")
        return module.get_vector_store(collection_name)
    except ImportError:
        raise ValueError(f"Unsupported vector provider: {provider}")

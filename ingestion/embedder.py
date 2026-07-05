from __future__ import annotations

from llama_index.core.embeddings import BaseEmbedding
from llama_index.embeddings.google import GeminiEmbedding

from config.settings import settings

_DEFAULT_MODEL = "models/text-embedding-004"


def get_embed_model(model_name: str = _DEFAULT_MODEL) -> BaseEmbedding:
    """Return a configured GeminiEmbedding instance.

    The API key is read from settings. The return type is BaseEmbedding so
    callers remain decoupled from the provider — MockEmbedding can substitute
    in tests.

    Args:
        model_name: Gemini embedding model identifier. Defaults to
            ``"models/text-embedding-004"`` (768 dimensions).

    Returns:
        A configured embedding model ready for use with VectorStoreIndex.
    """
    return GeminiEmbedding(
        model_name=model_name,
        api_key=settings.gemini_api_key,
    )

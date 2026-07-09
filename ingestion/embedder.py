from __future__ import annotations

from llama_index.core.embeddings import BaseEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding

from config.settings import settings

_DEFAULT_MODEL = "text-embedding-3-small"


def get_embed_model(model_name: str = _DEFAULT_MODEL) -> BaseEmbedding:
    """Return a configured OpenAIEmbedding instance.

    The API key is read from settings. The return type is BaseEmbedding so
    callers remain decoupled from the provider — MockEmbedding can substitute
    in tests.

    Args:
        model_name: OpenAI embedding model identifier. Defaults to
            ``"text-embedding-3-small"`` (1536 dimensions).

    Returns:
        A configured embedding model ready for use with VectorStoreIndex.
    """
    return OpenAIEmbedding(
        model=model_name,
        api_key=settings.openai_api_key,
        max_retries=settings.openai_max_retries,
    )

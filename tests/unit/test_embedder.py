from __future__ import annotations

from unittest.mock import patch

from config.settings import settings
from ingestion.embedder import get_embed_model


def test_get_embed_model_uses_configured_max_retries() -> None:
    with patch("ingestion.embedder.OpenAIEmbedding") as mock_cls:
        get_embed_model()

    mock_cls.assert_called_once_with(
        model="text-embedding-3-small",
        api_key=settings.openai_api_key,
        max_retries=settings.openai_max_retries,
    )


def test_get_embed_model_accepts_custom_model_name() -> None:
    with patch("ingestion.embedder.OpenAIEmbedding") as mock_cls:
        get_embed_model(model_name="text-embedding-3-large")

    mock_cls.assert_called_once_with(
        model="text-embedding-3-large",
        api_key=settings.openai_api_key,
        max_retries=settings.openai_max_retries,
    )

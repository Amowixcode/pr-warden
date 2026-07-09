"""Proves the retry-with-backoff behavior our `max_retries` configuration relies on.

These drive the real `openai.OpenAI` client and the real `OpenAIEmbedding` (the exact
classes used in core/review_service.py and ingestion/embedder.py) against a fake
transport, so no network call is made but the library's actual retry logic executes.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import openai
import pytest
from llama_index.embeddings.openai import OpenAIEmbedding

_MODEL_JSON = {"id": "gpt-4.1-mini", "created": 0, "object": "model", "owned_by": "openai"}
_EMBEDDING_JSON = {
    "object": "list",
    "data": [{"object": "embedding", "embedding": [0.1, 0.2], "index": 0}],
    "model": "text-embedding-3-small",
    "usage": {"prompt_tokens": 1, "total_tokens": 1},
}


def _counting_handler(
    responses: list[httpx.Response | Exception],
) -> tuple[Callable[[httpx.Request], httpx.Response], list[int]]:
    """Return a MockTransport handler that yields `responses` in order, plus a call counter."""
    calls = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        outcome = responses[min(calls[0], len(responses)) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return handler, calls


def _openai_client(
    handler: Callable[[httpx.Request], httpx.Response], max_retries: int
) -> openai.OpenAI:
    return openai.OpenAI(
        api_key="test-key",
        max_retries=max_retries,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _embed_model(
    handler: Callable[[httpx.Request], httpx.Response], max_retries: int
) -> OpenAIEmbedding:
    return OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key="test-key",
        max_retries=max_retries,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


# ── openai.OpenAI client (core/review_service.py's _call_openai) ────────────


def test_openai_client_retries_on_429_then_succeeds() -> None:
    handler, calls = _counting_handler(
        [
            httpx.Response(
                429, headers={"retry-after": "0"}, json={"error": {"message": "rate limited"}}
            ),
            httpx.Response(
                429, headers={"retry-after": "0"}, json={"error": {"message": "rate limited"}}
            ),
            httpx.Response(200, json=_MODEL_JSON),
        ]
    )
    client = _openai_client(handler, max_retries=3)

    result = client.models.retrieve("gpt-4.1-mini")

    assert result.id == "gpt-4.1-mini"
    assert calls[0] == 3


def test_openai_client_retries_on_timeout_then_succeeds() -> None:
    handler, calls = _counting_handler(
        [httpx.TimeoutException("timed out"), httpx.Response(200, json=_MODEL_JSON)]
    )
    client = _openai_client(handler, max_retries=3)

    result = client.models.retrieve("gpt-4.1-mini")

    assert result.id == "gpt-4.1-mini"
    assert calls[0] == 2


def test_openai_client_does_not_retry_on_400() -> None:
    handler, calls = _counting_handler(
        [httpx.Response(400, json={"error": {"message": "bad request"}})]
    )
    client = _openai_client(handler, max_retries=3)

    with pytest.raises(openai.BadRequestError):
        client.models.retrieve("gpt-4.1-mini")

    assert calls[0] == 1


def test_openai_client_exhausts_retries_and_raises() -> None:
    handler, calls = _counting_handler(
        [
            httpx.Response(
                429, headers={"retry-after": "0"}, json={"error": {"message": "rate limited"}}
            )
        ]
    )
    client = _openai_client(handler, max_retries=2)

    with pytest.raises(openai.RateLimitError):
        client.models.retrieve("gpt-4.1-mini")

    assert calls[0] == 3  # initial attempt + 2 retries


# ── OpenAIEmbedding (ingestion/embedder.py's get_embed_model) ───────────────


def test_embedding_retries_on_429_then_succeeds() -> None:
    handler, calls = _counting_handler(
        [
            httpx.Response(
                429, headers={"retry-after": "0"}, json={"error": {"message": "rate limited"}}
            ),
            httpx.Response(200, json=_EMBEDDING_JSON),
        ]
    )
    embed_model = _embed_model(handler, max_retries=3)

    result = embed_model.get_text_embedding("hello world")

    assert result == [0.1, 0.2]
    assert calls[0] == 2


def test_embedding_retries_on_timeout_then_succeeds() -> None:
    handler, calls = _counting_handler(
        [httpx.TimeoutException("timed out"), httpx.Response(200, json=_EMBEDDING_JSON)]
    )
    embed_model = _embed_model(handler, max_retries=3)

    result = embed_model.get_text_embedding("hello world")

    assert result == [0.1, 0.2]
    assert calls[0] == 2


def test_embedding_does_not_retry_on_400() -> None:
    handler, calls = _counting_handler(
        [httpx.Response(400, json={"error": {"message": "bad request"}})]
    )
    embed_model = _embed_model(handler, max_retries=3)

    with pytest.raises(openai.BadRequestError):
        embed_model.get_text_embedding("hello world")

    assert calls[0] == 1

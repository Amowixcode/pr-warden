from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore, TextNode
from openai import APIConnectionError

from core.exceptions import VectorStoreError
from retrieval.query_engine import retrieve


def _make_node(text: str = "node") -> NodeWithScore:
    return NodeWithScore(node=TextNode(text=text), score=0.9)


def _make_index_mock(nodes: list[NodeWithScore]) -> MagicMock:
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = nodes
    mock_index = MagicMock(spec=VectorStoreIndex)
    mock_index.as_retriever.return_value = mock_retriever
    return mock_index


# ── return values ────────────────────────────────────────────────────────────


async def test_retrieve_returns_nodes() -> None:
    nodes = [_make_node("a"), _make_node("b")]
    index = _make_index_mock(nodes)

    result = await retrieve(index, "query text", "issue", "owner", "repo")

    assert result == nodes


async def test_retrieve_empty_result() -> None:
    index = _make_index_mock([])

    result = await retrieve(index, "query", "issue", "owner", "repo")

    assert result == []


# ── filter construction ──────────────────────────────────────────────────────


async def test_retrieve_filter_contains_doc_type() -> None:
    index = _make_index_mock([])

    await retrieve(index, "query", "merged_pr", "owner", "repo")

    filters = index.as_retriever.call_args.kwargs["filters"]
    assert any(f.key == "doc_type" and f.value == "merged_pr" for f in filters.filters)


async def test_retrieve_filter_contains_repo() -> None:
    index = _make_index_mock([])

    await retrieve(index, "query", "commit", "myorg", "myrepo")

    filters = index.as_retriever.call_args.kwargs["filters"]
    assert any(f.key == "repo" and f.value == "myorg/myrepo" for f in filters.filters)


async def test_retrieve_filter_has_both_keys() -> None:
    index = _make_index_mock([])

    await retrieve(index, "query", "issue", "org", "repo")

    filters = index.as_retriever.call_args.kwargs["filters"]
    keys = {f.key for f in filters.filters}
    assert keys == {"doc_type", "repo"}


# ── top_k propagation ────────────────────────────────────────────────────────


async def test_retrieve_top_k_default() -> None:
    index = _make_index_mock([])

    await retrieve(index, "query", "issue", "owner", "repo")

    assert index.as_retriever.call_args.kwargs["similarity_top_k"] == 5


async def test_retrieve_top_k_custom() -> None:
    index = _make_index_mock([])

    await retrieve(index, "query", "issue", "owner", "repo", top_k=3)

    assert index.as_retriever.call_args.kwargs["similarity_top_k"] == 3


# ── query text forwarded ─────────────────────────────────────────────────────


async def test_retrieve_forwards_query_text() -> None:
    index = _make_index_mock([])

    await retrieve(index, "my specific query", "issue", "owner", "repo")

    retriever = index.as_retriever.return_value
    retriever.retrieve.assert_called_once_with("my specific query")


# ── error handling ───────────────────────────────────────────────────────────


async def test_retrieve_wraps_chroma_failure_as_vector_store_error() -> None:
    mock_retriever = MagicMock()
    mock_retriever.retrieve.side_effect = RuntimeError("chroma query failed")
    mock_index = MagicMock(spec=VectorStoreIndex)
    mock_index.as_retriever.return_value = mock_retriever

    with pytest.raises(VectorStoreError, match="chroma query failed"):
        await retrieve(mock_index, "query", "issue", "owner", "repo")


async def test_retrieve_propagates_openai_error_unwrapped() -> None:
    openai_error = APIConnectionError(
        request=httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    )
    mock_retriever = MagicMock()
    mock_retriever.retrieve.side_effect = openai_error
    mock_index = MagicMock(spec=VectorStoreIndex)
    mock_index.as_retriever.return_value = mock_retriever

    with pytest.raises(APIConnectionError):
        await retrieve(mock_index, "query", "issue", "owner", "repo")

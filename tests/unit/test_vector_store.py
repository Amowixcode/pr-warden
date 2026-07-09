from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import chromadb
import httpx
import pytest
from llama_index.core import VectorStoreIndex
from llama_index.core.embeddings.mock_embed_model import MockEmbedding
from openai import APIConnectionError

from core.exceptions import VectorStoreError
from gh.repo_fetcher import CommitData
from ingestion.github_loader import commits_to_documents
from ingestion.vector_store import (
    build_chroma_collection,
    build_vector_store_index,
    index_documents,
)

_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)


def _make_commit(sha: str = "a" * 40) -> CommitData:
    return CommitData(
        sha=sha,
        message="test commit",
        author="alice",
        committed_at=_NOW,
        url=f"https://github.com/test/repo/commit/{sha}",
    )


@pytest.fixture
def embed_model() -> MockEmbedding:
    return MockEmbedding(embed_dim=768)


@pytest.fixture
def index_and_collection(embed_model: MockEmbedding, tmp_path):
    # Use PersistentClient with a unique tmp dir so each test has isolated state.
    # EphemeralClient shares in-process memory across instantiations in ChromaDB 1.x.
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    collection = client.get_or_create_collection("test_col")
    idx = build_vector_store_index(collection, embed_model)
    return idx, collection


# ── build_chroma_collection ──────────────────────────────────────────────────


def test_build_chroma_collection_uses_settings_defaults():
    mock_collection = MagicMock()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection

    with patch("chromadb.PersistentClient", return_value=mock_client) as mock_pc:
        from config.settings import settings

        result = build_chroma_collection()
        mock_pc.assert_called_once_with(path=settings.chroma_persist_dir)
        mock_client.get_or_create_collection.assert_called_once_with(
            settings.chroma_collection_name
        )
        assert result is mock_collection


def test_build_chroma_collection_overrides_accepted():
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = MagicMock()

    with patch("chromadb.PersistentClient", return_value=mock_client) as mock_pc:
        build_chroma_collection(persist_dir="custom/path", collection_name="my_col")
        mock_pc.assert_called_once_with(path="custom/path")
        mock_client.get_or_create_collection.assert_called_once_with("my_col")


def test_build_chroma_collection_wraps_failure_as_vector_store_error():
    with (
        patch("chromadb.PersistentClient", side_effect=RuntimeError("disk full")),
        pytest.raises(VectorStoreError, match="disk full"),
    ):
        build_chroma_collection(persist_dir="custom/path")


# ── build_vector_store_index ─────────────────────────────────────────────────


def test_build_vector_store_index_returns_vector_store_index(
    embed_model: MockEmbedding,
    tmp_path,
):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    collection = client.get_or_create_collection("test_col")
    result = build_vector_store_index(collection, embed_model)
    assert isinstance(result, VectorStoreIndex)


def test_build_vector_store_index_collection_is_empty(embed_model: MockEmbedding, tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    collection = client.get_or_create_collection("test_col")
    build_vector_store_index(collection, embed_model)
    assert collection.count() == 0


# ── index_documents ──────────────────────────────────────────────────────────


async def test_index_documents_inserts_new_doc(index_and_collection):
    idx, collection = index_and_collection
    docs = commits_to_documents([_make_commit()], "owner", "repo")
    result = await index_documents(docs, idx, collection)
    assert result == 1
    assert collection.count() == 1


async def test_index_documents_skips_existing_doc(index_and_collection):
    idx, collection = index_and_collection
    docs = commits_to_documents([_make_commit()], "owner", "repo")
    await index_documents(docs, idx, collection)
    result = await index_documents(docs, idx, collection)
    assert result == 0
    assert collection.count() == 1


async def test_index_documents_mixed_new_and_existing(index_and_collection):
    idx, collection = index_and_collection
    sha_a = "a" * 40
    sha_b = "b" * 40
    doc_a = commits_to_documents([_make_commit(sha=sha_a)], "owner", "repo")
    doc_b = commits_to_documents([_make_commit(sha=sha_b)], "owner", "repo")
    await index_documents(doc_a, idx, collection)
    result = await index_documents(doc_a + doc_b, idx, collection)
    assert result == 1
    assert collection.count() == 2


async def test_index_documents_empty_list(index_and_collection):
    idx, collection = index_and_collection
    result = await index_documents([], idx, collection)
    assert result == 0
    assert collection.count() == 0


async def test_index_documents_multiple_new_docs(index_and_collection):
    idx, collection = index_and_collection
    shas = ["a" * 39 + str(i) for i in range(3)]
    docs = commits_to_documents([_make_commit(sha=s) for s in shas], "owner", "repo")
    result = await index_documents(docs, idx, collection)
    assert result == 3
    assert collection.count() == 3


async def test_index_documents_wraps_chroma_get_failure_as_vector_store_error(index_and_collection):
    idx, collection = index_and_collection
    docs = commits_to_documents([_make_commit()], "owner", "repo")
    collection.get = MagicMock(side_effect=RuntimeError("query failed"))

    with pytest.raises(VectorStoreError, match="query failed"):
        await index_documents(docs, idx, collection)


async def test_index_documents_wraps_insert_failure_as_vector_store_error(index_and_collection):
    idx, collection = index_and_collection
    docs = commits_to_documents([_make_commit()], "owner", "repo")
    idx.insert = MagicMock(side_effect=RuntimeError("insert failed"))

    with pytest.raises(VectorStoreError, match="insert failed"):
        await index_documents(docs, idx, collection)


async def test_index_documents_propagates_openai_error_unwrapped(index_and_collection):
    idx, collection = index_and_collection
    docs = commits_to_documents([_make_commit()], "owner", "repo")
    openai_error = APIConnectionError(
        request=httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    )
    idx.insert = MagicMock(side_effect=openai_error)

    with pytest.raises(APIConnectionError):
        await index_documents(docs, idx, collection)

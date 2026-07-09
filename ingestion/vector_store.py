from __future__ import annotations

import asyncio
import logging

import chromadb
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import Document
from llama_index.vector_stores.chroma import ChromaVectorStore
from openai import OpenAIError

from config.settings import settings
from core.exceptions import VectorStoreError

logger = logging.getLogger(__name__)


def build_chroma_collection(
    persist_dir: str | None = None,
    collection_name: str | None = None,
) -> chromadb.Collection:
    """Create or open a persistent ChromaDB collection.

    Safe to call on every startup — creates the collection if it does not
    exist, or opens it if it does.

    Args:
        persist_dir: Directory for ChromaDB data files. Falls back to
            ``settings.chroma_persist_dir`` when omitted.
        collection_name: Collection name. Falls back to
            ``settings.chroma_collection_name`` when omitted.

    Returns:
        A ChromaDB Collection ready for reads and writes.
    """
    resolved_dir = persist_dir or settings.chroma_persist_dir
    resolved_name = collection_name or settings.chroma_collection_name
    try:
        client = chromadb.PersistentClient(path=resolved_dir)
        return client.get_or_create_collection(resolved_name)
    except Exception as e:
        raise VectorStoreError(
            f"failed to open ChromaDB collection at {resolved_dir!r}: {e}"
        ) from e


def build_vector_store_index(
    collection: chromadb.Collection,
    embed_model: BaseEmbedding,
) -> VectorStoreIndex:
    """Build an empty VectorStoreIndex backed by a ChromaDB collection.

    Constructs a ChromaVectorStore → StorageContext → VectorStoreIndex with
    no initial documents. Add documents via ``index_documents()``.

    Args:
        collection: A ChromaDB Collection (from ``build_chroma_collection``).
        embed_model: A configured embedding model. Use ``get_embed_model()``
            in production; use ``MockEmbedding`` in tests.

    Returns:
        A VectorStoreIndex connected to the given collection.
    """
    chroma_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=chroma_store)
    return VectorStoreIndex([], storage_context=storage_context, embed_model=embed_model)


async def index_documents(
    documents: list[Document],
    index: VectorStoreIndex,
    collection: chromadb.Collection,
) -> int:
    """Insert new documents, skipping any already indexed.

    Checks for existing nodes in Chroma by querying the ``source_doc_id``
    metadata field before each insert. Every document produced by
    ``github_loader`` carries this field — it mirrors the document's stable
    ``id_`` and is the reliable deduplication key because LlamaIndex node IDs
    are auto-generated UUIDs and are not queryable by document identity.

    VectorStoreIndex.insert is synchronous; it runs in a thread to avoid
    blocking the event loop.

    Args:
        documents: Documents to potentially index.
        index: The target VectorStoreIndex.
        collection: The underlying ChromaDB collection for existence checks.

    Returns:
        Count of documents newly indexed (skipped documents not counted).
    """
    newly_indexed = 0
    for doc in documents:
        source_id = doc.metadata.get("source_doc_id", doc.id_)
        try:
            existing = collection.get(where={"source_doc_id": {"$eq": source_id}})
        except Exception as e:
            raise VectorStoreError(
                f"failed to query ChromaDB for document {source_id!r}: {e}"
            ) from e

        if not existing["ids"]:
            try:
                await asyncio.to_thread(index.insert, doc)
            except OpenAIError:
                raise
            except Exception as e:
                raise VectorStoreError(f"failed to index document {source_id!r}: {e}") from e
            newly_indexed += 1
            logger.debug("Indexed document %s", doc.id_)
        else:
            logger.debug("Skipping already-indexed document %s", doc.id_)
    return newly_indexed

from __future__ import annotations

import asyncio

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters


async def retrieve(
    index: VectorStoreIndex,
    query_text: str,
    doc_type: str,
    owner: str,
    repo: str,
    top_k: int = 5,
) -> list[NodeWithScore]:
    """Retrieve top-k nodes from the index filtered by document type and repo.

    Args:
        index: A VectorStoreIndex backed by ChromaDB.
        query_text: The text to embed and search with.
        doc_type: One of ``"issue"``, ``"merged_pr"``, or ``"commit"``.
        owner: GitHub repository owner.
        repo: Repository name.
        top_k: Maximum number of nodes to return.

    Returns:
        Up to ``top_k`` NodeWithScore results, ordered by similarity.
    """
    filters = MetadataFilters(
        filters=[
            MetadataFilter(key="doc_type", value=doc_type),
            MetadataFilter(key="repo", value=f"{owner}/{repo}"),
        ]
    )
    retriever = index.as_retriever(similarity_top_k=top_k, filters=filters)
    return await asyncio.to_thread(retriever.retrieve, query_text)

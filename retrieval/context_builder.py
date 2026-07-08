from __future__ import annotations

import asyncio
from dataclasses import dataclass

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore

from gh.pr_fetcher import PRData
from retrieval.query_engine import retrieve


@dataclass
class PRContext:
    similar_issues: list[NodeWithScore]
    similar_prs: list[NodeWithScore]
    related_commits: list[NodeWithScore]


async def build_pr_context(
    pr: PRData,
    index: VectorStoreIndex,
    owner: str,
    repo: str,
    top_k: int = 5,
) -> PRContext:
    """Query the vector store for context relevant to a pull request.

    Runs three similarity searches concurrently — one per document type — using
    the PR title and body as the query text.

    Args:
        pr: The pull request to find context for.
        index: A VectorStoreIndex populated by ``ingest_repository``.
        owner: GitHub repository owner.
        repo: Repository name.
        top_k: Maximum results per document type.

    Returns:
        A PRContext with similar issues, merged PRs, and related commits.
    """
    query_text = f"{pr.title}\n\n{pr.body}"

    similar_issues, similar_prs, related_commits = await asyncio.gather(
        retrieve(index, query_text, "issue", owner, repo, top_k),
        retrieve(index, query_text, "merged_pr", owner, repo, top_k),
        retrieve(index, query_text, "commit", owner, repo, top_k),
    )

    return PRContext(
        similar_issues=similar_issues,
        similar_prs=similar_prs,
        related_commits=related_commits,
    )

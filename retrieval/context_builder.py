from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore
from pydantic import BaseModel

from gh.pr_fetcher import PRData
from gh.repo_fetcher import IssueData
from retrieval.query_engine import retrieve


class PersistedAgentResult(BaseModel):
    """Snapshot of one specialist agent's findings, persisted for cache-hit incremental
    re-reviews. Structurally mirrors agents.state.AgentResult but is defined independently
    here — agents.state already imports PRContext from this module, so importing AgentResult
    back into this module would be a circular import.
    """

    summary: str
    verdict: str
    issues: list[str]
    suggestions: list[str]


class ReviewRecord(BaseModel):
    """A persisted review outcome for a PR, keyed by owner/repo/PR number elsewhere
    (core/review_history.py) and used both to compute the incremental diff on the next review
    and to give agents prior-review context.
    """

    head_sha: str
    verdict: str
    summary: str
    issues: list[str]
    suggestions: list[str]
    security_result: PersistedAgentResult
    quality_result: PersistedAgentResult
    test_result: PersistedAgentResult
    reviewed_at: datetime


@dataclass
class PRContext:
    similar_issues: list[NodeWithScore]
    similar_prs: list[NodeWithScore]
    related_commits: list[NodeWithScore]
    linked_issues: list[IssueData] = field(default_factory=list)
    prior_review: ReviewRecord | None = None


async def build_pr_context(
    pr: PRData,
    index: VectorStoreIndex,
    owner: str,
    repo: str,
    linked_issues: list[IssueData] | None = None,
    prior_review: ReviewRecord | None = None,
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
        linked_issues: Issues referenced by the PR's own Fixes/Closes/Resolves #N syntax
            (fetched via ``gh.pr_fetcher.fetch_linked_issues``), passed through as-is — this
            function only performs the RAG lookups, not the live GitHub fetch.
        prior_review: The last-persisted review of this PR, if any (from
            ``core.review_history.load_review_record``), passed through as-is for incremental
            review — this function doesn't touch review history itself.
        top_k: Maximum results per document type.

    Returns:
        A PRContext with similar issues, merged PRs, related commits, linked issues, and any
        prior review record.
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
        linked_issues=linked_issues or [],
        prior_review=prior_review,
    )

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from agents.graph import graph
from agents.state import AgentResult, ReviewState
from config.settings import settings
from core import supabase_history
from core.review_history import load_review_record, save_review_record
from gh.client import GitHubClient
from gh.pr_fetcher import fetch_diff_since, fetch_linked_issues, fetch_pull_request
from ingestion.embedder import get_embed_model
from ingestion.vector_store import build_chroma_collection, build_vector_store_index
from retrieval.context_builder import PersistedAgentResult, ReviewRecord, build_pr_context


@dataclass
class ReviewResult:
    pr_number: int
    summary: str
    verdict: str  # "APPROVE" | "REQUEST_CHANGES" | "COMMENT"
    issues: list[str]
    suggestions: list[str]
    security_result: AgentResult
    quality_result: AgentResult
    test_result: AgentResult
    incremental: bool = False
    cached: bool = False
    prior_verdict: str | None = None
    prior_head_sha: str | None = None


def _to_agent_result(persisted: PersistedAgentResult) -> AgentResult:
    return AgentResult(
        summary=persisted.summary,
        verdict=persisted.verdict,
        issues=persisted.issues,
        suggestions=persisted.suggestions,
    )


def _to_persisted(result: AgentResult) -> PersistedAgentResult:
    return PersistedAgentResult(
        summary=result.summary,
        verdict=result.verdict,
        issues=result.issues,
        suggestions=result.suggestions,
    )


async def review_pr(owner: str, repo: str, pr_number: int, full: bool = False) -> ReviewResult:
    """Fetch a PR, retrieve historical context, and produce a structured review.

    Runs the security/quality/test -> summarizer multi-agent graph (agents/graph.py) rather
    than a single flat prompt — see agents/README.md for the graph shape and merge policy.

    Incremental by default: if this PR was reviewed before (a ReviewRecord exists), only the
    diff since the last-reviewed commit is sent to the agents, and the prior verdict is passed
    along as context. If nothing has changed since the last review, the agents aren't called
    at all — the cached result is returned directly. Pass full=True to ignore history and
    always do a complete review.

    Args:
        owner: GitHub repository owner.
        repo: Repository name.
        pr_number: Pull request number to review.
        full: Force a complete review, ignoring any prior review history.

    Returns:
        A ReviewResult with summary, verdict, issues, and suggestions.
    """
    client = GitHubClient(settings.github_token, max_retries=settings.github_max_retries)
    pr = await fetch_pull_request(client, owner, repo, pr_number)

    prior_record = None if full else load_review_record(owner, repo, pr_number)

    if prior_record is not None and prior_record.head_sha == pr.head_sha:
        # Nothing new since the last review — skip Chroma/RAG setup and the agent graph
        # entirely and return the cached result.
        return ReviewResult(
            pr_number=pr.number,
            summary=prior_record.summary,
            verdict=prior_record.verdict,
            issues=prior_record.issues,
            suggestions=prior_record.suggestions,
            security_result=_to_agent_result(prior_record.security_result),
            quality_result=_to_agent_result(prior_record.quality_result),
            test_result=_to_agent_result(prior_record.test_result),
            incremental=True,
            cached=True,
            prior_verdict=prior_record.verdict,
            prior_head_sha=prior_record.head_sha,
        )

    linked_issues = await fetch_linked_issues(client, owner, repo, pr.body)

    if prior_record is not None:
        incremental_diff = await fetch_diff_since(
            client, owner, repo, prior_record.head_sha, pr.head_sha
        )
        pr = pr.model_copy(update={"diff": incremental_diff})

    collection = build_chroma_collection()
    embed_model = get_embed_model()
    index = build_vector_store_index(collection, embed_model)

    context = await build_pr_context(
        pr, index, owner, repo, linked_issues=linked_issues, prior_review=prior_record
    )

    initial_state: ReviewState = {
        "pr": pr,
        "context": context,
        "security_result": None,
        "quality_result": None,
        "test_result": None,
        "final_verdict": None,
    }
    final_state = await graph.ainvoke(initial_state)
    final = final_state["final_verdict"]
    security_result = final_state["security_result"]
    quality_result = final_state["quality_result"]
    test_result = final_state["test_result"]

    record = ReviewRecord(
        head_sha=pr.head_sha,
        verdict=final.verdict,
        summary=final.summary,
        issues=final.issues,
        suggestions=final.suggestions,
        security_result=_to_persisted(security_result),
        quality_result=_to_persisted(quality_result),
        test_result=_to_persisted(test_result),
        reviewed_at=datetime.now(UTC),
    )
    save_review_record(owner, repo, pr_number, record)
    await asyncio.to_thread(supabase_history.save_review, owner, repo, pr_number, record)

    return ReviewResult(
        pr_number=pr.number,
        summary=final.summary,
        verdict=final.verdict,
        issues=final.issues,
        suggestions=final.suggestions,
        security_result=security_result,
        quality_result=quality_result,
        test_result=test_result,
        incremental=prior_record is not None,
        cached=False,
        prior_verdict=prior_record.verdict if prior_record else None,
        prior_head_sha=prior_record.head_sha if prior_record else None,
    )

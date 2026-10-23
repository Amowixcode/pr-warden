from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from agents.graph import graph
from agents.state import AgentResult, DroppedIssue, ReviewState
from config.settings import get_settings
from core import supabase_history
from core.review_history import load_review_record, save_review_record
from core.supabase_client import get_supabase_client
from core.test_files import filenames_in_diff, find_test_files
from gh.client import GitHubClient
from gh.pr_fetcher import PRData, fetch_diff_since, fetch_linked_issues, fetch_pull_request
from ingestion.embedder import get_embed_model
from ingestion.vector_store import build_chroma_collection, build_vector_store_index
from retrieval.context_builder import PersistedAgentResult, ReviewRecord, build_pr_context

# Bump whenever prompts, evidence verification or verdict rules change: a cached review is only
# reused when the version that produced it matches, so older logic can't keep serving verdicts.
REVIEW_PIPELINE_VERSION = "2"


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
    status: str = "reviewed"  # "reviewed" | "cached" | "nothing_new"
    not_reviewed: list[str] = field(default_factory=list)


def _to_agent_result(persisted: PersistedAgentResult) -> AgentResult:
    return AgentResult(
        summary=persisted.summary,
        verdict=persisted.verdict,
        issues=persisted.issues,
        suggestions=persisted.suggestions,
        dropped_issues=[DroppedIssue(**d) for d in persisted.dropped_issues],
    )


def _to_persisted(result: AgentResult) -> PersistedAgentResult:
    return PersistedAgentResult(
        summary=result.summary,
        verdict=result.verdict,
        issues=result.issues,
        suggestions=result.suggestions,
        dropped_issues=[asdict(d) for d in result.dropped_issues],
    )


def _placeholder_result() -> AgentResult:
    return AgentResult(summary="Not run.", verdict="APPROVE", issues=[], suggestions=[])


async def _load_prior_record(owner: str, repo: str, pr_number: int) -> ReviewRecord | None:
    """The review cache lookup: Supabase when configured (survives deploys), else local JSON.

    A Supabase miss or error also falls back to the local JSON, which the CLI keeps writing.
    A record from a different pipeline version is discarded — it was produced by older logic,
    so it must neither be replayed nor drive an incremental diff.
    """
    record = None
    if get_supabase_client() is not None:
        record = await asyncio.to_thread(
            supabase_history.load_latest_review_record, owner, repo, pr_number
        )
    if record is None:
        record = load_review_record(owner, repo, pr_number)
    if record is not None and record.pipeline_version != REVIEW_PIPELINE_VERSION:
        return None
    return record


async def review_pr(
    owner: str,
    repo: str,
    pr_number: int,
    full: bool = False,
    on_stage: Callable[[str], Awaitable[None]] | None = None,
) -> ReviewResult:
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
        on_stage: Optional async callback invoked with a short human-readable label (e.g.
            "running review agents") as each phase starts — how a background job reports what
            it's doing without a percentage that would have to be invented. Not called on the
            cached short-circuit path, which returns near-instantly. Never called for direct/
            CLI callers, which pass nothing.

    Returns:
        A ReviewResult with summary, verdict, issues, and suggestions.
    """
    settings = get_settings()
    client = GitHubClient(settings.github_token, max_retries=settings.github_max_retries)
    if on_stage:
        await on_stage("fetching pull request")
    pr = await fetch_pull_request(client, owner, repo, pr_number)

    prior_record = None if full else await _load_prior_record(owner, repo, pr_number)

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
            status="cached",
            not_reviewed=pr.unreviewed_files,
        )

    linked_issues = await fetch_linked_issues(client, owner, repo, pr.body)

    if prior_record is not None:
        incremental_diff, skipped = await fetch_diff_since(
            client, owner, repo, prior_record.head_sha, pr.head_sha
        )
        pr = pr.model_copy(update={"diff": incremental_diff, "unreviewed_files": skipped})

    if not pr.diff.strip():
        # Nothing for the agents to read (incremental with no patches, or an all-binary PR):
        # say so rather than letting empty agent output read as an APPROVE of unseen code.
        return _nothing_to_review(pr, prior_record)

    if on_stage:
        await on_stage("retrieving context")
    collection = build_chroma_collection()
    embed_model = get_embed_model()
    index = build_vector_store_index(collection, embed_model)

    context = await build_pr_context(
        pr, index, owner, repo, linked_issues=linked_issues, prior_review=prior_record
    )

    if on_stage:
        await on_stage("running review agents")
    initial_state: ReviewState = {
        "pr": pr,
        "context": context,
        "security_result": None,
        "quality_result": None,
        "test_result": None,
        "final_verdict": None,
        "test_files": find_test_files(filenames_in_diff(pr.diff)),
    }
    final_state = await graph.ainvoke(initial_state)
    final = final_state["final_verdict"]
    security_result = final_state["security_result"]
    quality_result = final_state["quality_result"]
    test_result = final_state["test_result"]

    if on_stage:
        await on_stage("saving results")
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
        pipeline_version=REVIEW_PIPELINE_VERSION,
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
        status="reviewed",
        not_reviewed=pr.unreviewed_files,
    )


def _nothing_to_review(pr: PRData, prior_record: ReviewRecord | None) -> ReviewResult:
    """Result for an empty diff: no agents run, nothing is saved, and the prior verdict (if
    any) is carried through unchanged.
    """
    if prior_record is not None:
        summary = f"Nothing new to review since {prior_record.head_sha[:7]}."
        agent_results = (
            _to_agent_result(prior_record.security_result),
            _to_agent_result(prior_record.quality_result),
            _to_agent_result(prior_record.test_result),
        )
        verdict, issues, suggestions = (
            prior_record.verdict,
            prior_record.issues,
            prior_record.suggestions,
        )
    else:
        summary = "Nothing to review: this PR has no reviewable text changes."
        agent_results = (_placeholder_result(), _placeholder_result(), _placeholder_result())
        verdict, issues, suggestions = "APPROVE", [], []
    return ReviewResult(
        pr_number=pr.number,
        summary=summary,
        verdict=verdict,
        issues=issues,
        suggestions=suggestions,
        security_result=agent_results[0],
        quality_result=agent_results[1],
        test_result=agent_results[2],
        incremental=prior_record is not None,
        cached=False,
        prior_verdict=prior_record.verdict if prior_record else None,
        prior_head_sha=prior_record.head_sha if prior_record else None,
        status="nothing_new",
        not_reviewed=pr.unreviewed_files,
    )

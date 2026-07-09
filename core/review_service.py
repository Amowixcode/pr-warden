from __future__ import annotations

from dataclasses import dataclass

from agents.graph import graph
from agents.state import ReviewState
from config.settings import settings
from gh.client import GitHubClient
from gh.pr_fetcher import fetch_pull_request
from ingestion.embedder import get_embed_model
from ingestion.vector_store import build_chroma_collection, build_vector_store_index
from retrieval.context_builder import build_pr_context


@dataclass
class ReviewResult:
    pr_number: int
    summary: str
    verdict: str  # "APPROVE" | "REQUEST_CHANGES" | "COMMENT"
    issues: list[str]
    suggestions: list[str]


async def review_pr(owner: str, repo: str, pr_number: int) -> ReviewResult:
    """Fetch a PR, retrieve historical context, and produce a structured review.

    Runs the security/quality/test -> summarizer multi-agent graph (agents/graph.py) rather
    than a single flat prompt — see agents/README.md for the graph shape and merge policy.

    Args:
        owner: GitHub repository owner.
        repo: Repository name.
        pr_number: Pull request number to review.

    Returns:
        A ReviewResult with summary, verdict, issues, and suggestions.
    """
    client = GitHubClient(settings.github_token, max_retries=settings.github_max_retries)
    pr = await fetch_pull_request(client, owner, repo, pr_number)

    collection = build_chroma_collection()
    embed_model = get_embed_model()
    index = build_vector_store_index(collection, embed_model)

    context = await build_pr_context(pr, index, owner, repo)

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

    return ReviewResult(
        pr_number=pr.number,
        summary=final.summary,
        verdict=final.verdict,
        issues=final.issues,
        suggestions=final.suggestions,
    )

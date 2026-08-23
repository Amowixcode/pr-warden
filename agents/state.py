from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

from gh.pr_fetcher import PRData
from retrieval.context_builder import PRContext

Verdict = Literal["APPROVE", "REQUEST_CHANGES", "COMMENT"]


@dataclass
class AgentResult:
    """Shape produced by each specialist agent, and by the summarizer's final aggregate.

    Mirrors core.review_service.ReviewResult's existing 4-field shape so the eventual
    summarizer output maps onto it with no translation. Not imported from core directly —
    core orchestrates agents, not the reverse.
    """

    summary: str
    verdict: Verdict
    issues: list[str]
    suggestions: list[str]


class ReviewState(TypedDict):
    """Shared LangGraph state for the security/quality/test -> summarizer review graph.

    `pr` and `context` are populated once before the graph runs — the fan-out inputs, read-only
    to every node. Each `*_result` field is written by exactly one node (security_agent writes
    only `security_result`, etc.), so no LangGraph reducer is needed: there is no concurrent
    write to any single key even though the three agent nodes run in parallel. `final_verdict`
    is written once by the summarizer, which only runs after all three agents complete (it has
    incoming edges from all three), so it can assume every `*_result` field is populated.

    See agents/README.md for the graph shape, node responsibilities, and the merge policy the
    summarizer must implement.
    """

    pr: PRData
    context: PRContext
    security_result: AgentResult | None
    quality_result: AgentResult | None
    test_result: AgentResult | None
    final_verdict: AgentResult | None

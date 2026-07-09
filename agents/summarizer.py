from __future__ import annotations

from agents.state import AgentResult, ReviewState, Verdict


def _merge_verdict(verdicts: list[Verdict]) -> Verdict:
    """REQUEST_CHANGES if any agent flags it, else COMMENT if any has non-blocking issues.

    Else (all APPROVE) -> APPROVE.
    """
    if "REQUEST_CHANGES" in verdicts:
        return "REQUEST_CHANGES"
    if "COMMENT" in verdicts:
        return "COMMENT"
    return "APPROVE"


def summarizer(state: ReviewState) -> dict[str, AgentResult]:
    """LangGraph node: merges security/quality/test agent outputs into a final verdict.

    Runs only after all three specialist agents complete (it has incoming edges from all
    three, per agents/README.md's graph shape), so state["security_result"],
    state["quality_result"], and state["test_result"] are guaranteed populated. Returns a
    partial state update — {"final_verdict": AgentResult(...)} — the only key this node
    writes.

    Deterministic merge, no OpenAI call: verdict follows the policy in _merge_verdict();
    issues and suggestions are the concatenation of all three agents' lists; summary is each
    agent's own summary, labeled by category.
    """
    security = state["security_result"]
    quality = state["quality_result"]
    test = state["test_result"]
    results = (security, quality, test)

    verdict = _merge_verdict([r.verdict for r in results])
    issues = [issue for r in results for issue in r.issues]
    suggestions = [suggestion for r in results for suggestion in r.suggestions]
    summary = (
        f"Security: {security.summary}\nQuality: {quality.summary}\nTest coverage: {test.summary}"
    )

    return {
        "final_verdict": AgentResult(
            summary=summary, verdict=verdict, issues=issues, suggestions=suggestions
        )
    }

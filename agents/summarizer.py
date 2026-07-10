from __future__ import annotations

from itertools import zip_longest

from agents.state import AgentResult, ReviewState, Verdict

_MAX_TOTAL_ISSUES = 5
_MAX_TOTAL_SUGGESTIONS = 3


def _merge_verdict(verdicts: list[Verdict]) -> Verdict:
    """REQUEST_CHANGES if any agent flags it, else COMMENT if any has non-blocking issues.

    Else (all APPROVE) -> APPROVE.
    """
    if "REQUEST_CHANGES" in verdicts:
        return "REQUEST_CHANGES"
    if "COMMENT" in verdicts:
        return "COMMENT"
    return "APPROVE"


def _interleave(lists: list[list[str]]) -> list[str]:
    """Round-robin merge across agent lists — item 0 from each list, then item 1, etc.

    Ensures a single agent with many items can't crowd the others out once the merged result
    is capped (e.g. security alone returning 3 suggestions must not push quality's and test's
    suggestions out of a 3-item total cap).
    """
    merged: list[str] = []
    for group in zip_longest(*lists):
        merged.extend(item for item in group if item is not None)
    return merged


def _synthesize_summary(verdict: Verdict, flagged_by: list[str], total_issues: int) -> str:
    """A short synthesized sentence — never a concatenation of each agent's own summary."""
    if verdict == "APPROVE":
        return "No blocking concerns from security, quality, or test coverage review."
    issue_word = "issue" if total_issues == 1 else "issues"
    return f"{verdict} — {total_issues} {issue_word} flagged by {', '.join(flagged_by)}."


def summarizer(state: ReviewState) -> dict[str, AgentResult]:
    """LangGraph node: merges security/quality/test agent outputs into a final verdict.

    Runs only after all three specialist agents complete (it has incoming edges from all
    three, per agents/README.md's graph shape), so state["security_result"],
    state["quality_result"], and state["test_result"] are guaranteed populated. Returns a
    partial state update — {"final_verdict": AgentResult(...)} — the only key this node
    writes.

    Deterministic merge, no OpenAI call: verdict follows the policy in _merge_verdict().
    issues/suggestions are capped totals across all three agents, round-robin interleaved so
    no single agent's list can crowd the others out of the cap (not an exhaustive
    concatenation), and summary is a synthesized one-liner naming which agents flagged
    something and how many issues in total — not each agent's own summary text repeated.
    """
    named_results = [
        ("security", state["security_result"]),
        ("quality", state["quality_result"]),
        ("test coverage", state["test_result"]),
    ]

    verdict = _merge_verdict([result.verdict for _, result in named_results])
    total_issues = sum(len(result.issues) for _, result in named_results)
    merged_issues = _interleave([result.issues for _, result in named_results])
    merged_suggestions = _interleave([result.suggestions for _, result in named_results])
    flagged_by = [name for name, result in named_results if result.issues]

    return {
        "final_verdict": AgentResult(
            summary=_synthesize_summary(verdict, flagged_by, total_issues),
            verdict=verdict,
            issues=merged_issues[:_MAX_TOTAL_ISSUES],
            suggestions=merged_suggestions[:_MAX_TOTAL_SUGGESTIONS],
        )
    }

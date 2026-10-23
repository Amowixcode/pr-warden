from __future__ import annotations

from itertools import zip_longest

from agents.state import AgentResult, ReviewState, Verdict

_MAX_TOTAL_ISSUES = 5
_MAX_TOTAL_SUGGESTIONS = 3


def _merge_verdict(verdicts: list[Verdict], has_issues: bool) -> Verdict:
    """Merge the agents' verdicts, with surviving issues as the source of truth.

    No surviving issues -> APPROVE, whatever any agent's own verdict says: a REQUEST_CHANGES or
    COMMENT is only meaningful while verified issues back it (evidence verification may have
    stripped them all). Otherwise REQUEST_CHANGES if any agent flags it, else COMMENT — also
    when every agent said APPROVE but issues are listed, since an agent's verdict and its own
    issues list aren't always internally consistent.
    """
    if not has_issues:
        return "APPROVE"
    if "REQUEST_CHANGES" in verdicts:
        return "REQUEST_CHANGES"
    return "COMMENT"


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


def _synthesize_summary(
    verdict: Verdict, flagged_by: list[str], total_issues: int, total_dropped: int = 0
) -> str:
    """A short synthesized sentence — never a concatenation of each agent's own summary.

    Dropped findings (evidence verification rejected them) are mentioned only when there were any.
    """
    if verdict == "APPROVE":
        summary = "No blocking concerns from security, quality, or test coverage review."
    else:
        issue_word = "issue" if total_issues == 1 else "issues"
        summary = f"{verdict} — {total_issues} {issue_word} flagged by {', '.join(flagged_by)}."
    if total_dropped:
        finding_word = "finding" if total_dropped == 1 else "findings"
        summary += f" {total_dropped} {finding_word} discarded: evidence not found in the diff."
    return summary


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

    total_issues = sum(len(result.issues) for _, result in named_results)
    verdict = _merge_verdict(
        [result.verdict for _, result in named_results], has_issues=total_issues > 0
    )
    merged_issues = _interleave([result.issues for _, result in named_results])
    merged_suggestions = _interleave([result.suggestions for _, result in named_results])
    flagged_by = [name for name, result in named_results if result.issues]
    total_dropped = sum(len(result.dropped_issues) for _, result in named_results)

    return {
        "final_verdict": AgentResult(
            summary=_synthesize_summary(verdict, flagged_by, total_issues, total_dropped),
            verdict=verdict,
            issues=merged_issues[:_MAX_TOTAL_ISSUES],
            suggestions=merged_suggestions[:_MAX_TOTAL_SUGGESTIONS],
        )
    }

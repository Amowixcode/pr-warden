"""Proves the graph actually fans out to all three agents and fans back into the summarizer.

Checks that the summarizer runs exactly once, after all three agents complete, with the fully
merged state visible. Note: for this graph's specific topology (all three agents are direct
children of START, always completing in the same superstep), this passes whether the fan-in
edge is registered as add_edge([agent1, agent2, agent3], "summarizer") or as three separate
add_edge(agent, "summarizer") calls — LangGraph schedules each distinct target once per
superstep regardless of edge count (verified empirically). agents/graph.py still uses the list
form since it's the semantically correct, self-documenting way to declare "depends on all
three", and the form that would stay correct if the topology later changes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from agents.graph import build_graph
from agents.state import AgentResult, ReviewState
from gh.pr_fetcher import PRData
from retrieval.context_builder import PRContext

_PATCH = "agents.graph.{}"
_NOW = datetime(2024, 6, 1, tzinfo=UTC)


def _make_initial_state() -> ReviewState:
    pr = PRData(
        number=7,
        title="Add retry logic",
        body="Fixes flaky CI",
        state="open",
        author="dev",
        base_branch="main",
        head_branch="feature/retry",
        created_at=_NOW,
        updated_at=_NOW,
        changed_files=[],
        diff="diff --git a/gh/client.py b/gh/client.py",
    )
    context = PRContext(similar_issues=[], similar_prs=[], related_commits=[])
    return {
        "pr": pr,
        "context": context,
        "security_result": None,
        "quality_result": None,
        "test_result": None,
        "final_verdict": None,
    }


def _mock_agent(key: str, verdict: str = "APPROVE") -> MagicMock:
    return MagicMock(
        return_value={key: AgentResult(summary="s", verdict=verdict, issues=[], suggestions=[])}
    )


def test_all_three_agents_are_called_exactly_once() -> None:
    mock_security = _mock_agent("security_result")
    mock_quality = _mock_agent("quality_result")
    mock_test = _mock_agent("test_result")
    mock_summarizer = MagicMock(
        return_value={
            "final_verdict": AgentResult(summary="s", verdict="APPROVE", issues=[], suggestions=[])
        }
    )

    with (
        patch(_PATCH.format("security_agent"), mock_security),
        patch(_PATCH.format("quality_agent"), mock_quality),
        patch(_PATCH.format("test_agent"), mock_test),
        patch(_PATCH.format("summarizer"), mock_summarizer),
    ):
        compiled = build_graph()
        compiled.invoke(_make_initial_state())

    mock_security.assert_called_once()
    mock_quality.assert_called_once()
    mock_test.assert_called_once()


def test_summarizer_is_called_exactly_once_not_once_per_agent() -> None:
    """The critical fan-in check: three parallel predecessors must trigger one summarizer run."""
    mock_summarizer = MagicMock(
        return_value={
            "final_verdict": AgentResult(summary="s", verdict="APPROVE", issues=[], suggestions=[])
        }
    )

    with (
        patch(_PATCH.format("security_agent"), _mock_agent("security_result")),
        patch(_PATCH.format("quality_agent"), _mock_agent("quality_result")),
        patch(_PATCH.format("test_agent"), _mock_agent("test_result")),
        patch(_PATCH.format("summarizer"), mock_summarizer),
    ):
        compiled = build_graph()
        compiled.invoke(_make_initial_state())

    assert mock_summarizer.call_count == 1


def test_summarizer_receives_all_three_merged_results() -> None:
    security_result = AgentResult(
        summary="sec", verdict="REQUEST_CHANGES", issues=["x"], suggestions=[]
    )
    quality_result = AgentResult(summary="qual", verdict="APPROVE", issues=[], suggestions=[])
    test_result = AgentResult(summary="test", verdict="COMMENT", issues=[], suggestions=["y"])
    mock_summarizer = MagicMock(
        return_value={
            "final_verdict": AgentResult(
                summary="s", verdict="REQUEST_CHANGES", issues=[], suggestions=[]
            )
        }
    )

    with (
        patch(
            _PATCH.format("security_agent"),
            MagicMock(return_value={"security_result": security_result}),
        ),
        patch(
            _PATCH.format("quality_agent"),
            MagicMock(return_value={"quality_result": quality_result}),
        ),
        patch(_PATCH.format("test_agent"), MagicMock(return_value={"test_result": test_result})),
        patch(_PATCH.format("summarizer"), mock_summarizer),
    ):
        compiled = build_graph()
        compiled.invoke(_make_initial_state())

    received_state = mock_summarizer.call_args.args[0]
    assert received_state["security_result"] == security_result
    assert received_state["quality_result"] == quality_result
    assert received_state["test_result"] == test_result


def test_final_output_state_contains_summarizer_result() -> None:
    final = AgentResult(
        summary="final summary", verdict="REQUEST_CHANGES", issues=["x"], suggestions=["y"]
    )
    mock_summarizer = MagicMock(return_value={"final_verdict": final})

    with (
        patch(_PATCH.format("security_agent"), _mock_agent("security_result")),
        patch(_PATCH.format("quality_agent"), _mock_agent("quality_result")),
        patch(_PATCH.format("test_agent"), _mock_agent("test_result")),
        patch(_PATCH.format("summarizer"), mock_summarizer),
    ):
        compiled = build_graph()
        output_state = compiled.invoke(_make_initial_state())

    assert output_state["final_verdict"] == final


def test_real_summarizer_applies_merge_policy_through_the_graph() -> None:
    """Only the three agents are mocked here — summarizer is the real function, not a mock.

    The other tests in this file mock summarizer too, so they only prove graph execution calls
    whatever is registered under that node name — not that the real merge-policy logic is
    correctly wired in. This closes that gap without the overhead of the full HTTP-mocked
    integration test.
    """
    security = AgentResult(
        summary="Found a hardcoded secret",
        verdict="REQUEST_CHANGES",
        issues=["Hardcoded secret"],
        suggestions=["Use an env var"],
    )
    quality = AgentResult(summary="Looks clean", verdict="APPROVE", issues=[], suggestions=[])
    test = AgentResult(summary="Well covered", verdict="APPROVE", issues=[], suggestions=[])

    with (
        patch(
            _PATCH.format("security_agent"), MagicMock(return_value={"security_result": security})
        ),
        patch(_PATCH.format("quality_agent"), MagicMock(return_value={"quality_result": quality})),
        patch(_PATCH.format("test_agent"), MagicMock(return_value={"test_result": test})),
    ):
        compiled = build_graph()
        output_state = compiled.invoke(_make_initial_state())

    final = output_state["final_verdict"]
    assert final.verdict == "REQUEST_CHANGES"
    assert final.issues == ["Hardcoded secret"]
    assert final.suggestions == ["Use an env var"]

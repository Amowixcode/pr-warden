from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from core import supabase_history
from core.ingest_service import IngestResult
from retrieval.context_builder import PersistedAgentResult, ReviewRecord

_NOW = datetime(2024, 6, 1, tzinfo=UTC)


def _review_record(head_sha: str = "abc123") -> ReviewRecord:
    agent = PersistedAgentResult(summary="ok", verdict="APPROVE", issues=[], suggestions=[])
    return ReviewRecord(
        head_sha=head_sha,
        verdict="APPROVE",
        summary="Looks good",
        issues=["bug A"],
        suggestions=["do X"],
        security_result=agent,
        quality_result=agent,
        test_result=agent,
        reviewed_at=_NOW,
        pipeline_version="2",
    )


def _ingest_result() -> IngestResult:
    return IngestResult(issues_indexed=3, prs_indexed=2, commits_indexed=10, total_newly_indexed=15)


def test_save_review_noop_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: None)

    supabase_history.save_review("octocat", "Hello-World", 7, _review_record())


def test_save_review_inserts_expected_row(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    supabase_history.save_review("octocat", "Hello-World", 7, _review_record(head_sha="deadbeef"))

    mock_client.table.assert_called_once_with("reviews")
    insert_call = mock_client.table.return_value.insert
    insert_call.assert_called_once_with(
        {
            "repo": "octocat/Hello-World",
            "pr_number": 7,
            "head_sha": "deadbeef",
            "verdict": "APPROVE",
            "summary": "Looks good",
            "issues": ["bug A"],
            "suggestions": ["do X"],
            "pipeline_version": "2",
            "record": _review_record(head_sha="deadbeef").model_dump(mode="json"),
        }
    )
    insert_call.return_value.execute.assert_called_once_with()


def test_save_review_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("down")
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    supabase_history.save_review("octocat", "Hello-World", 7, _review_record())


def test_save_ingest_noop_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: None)

    supabase_history.save_ingest("octocat", "Hello-World", _ingest_result(), _NOW)


def test_save_ingest_inserts_expected_row(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    supabase_history.save_ingest("octocat", "Hello-World", _ingest_result(), _NOW)

    mock_client.table.assert_called_once_with("ingests")
    insert_call = mock_client.table.return_value.insert
    insert_call.assert_called_once_with(
        {
            "repo": "octocat/Hello-World",
            "last_ingested_at": _NOW.isoformat(),
            "issues_count": 3,
            "merged_prs_count": 2,
            "commits_count": 10,
        }
    )
    insert_call.return_value.execute.assert_called_once_with()


def test_save_ingest_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("down")
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    supabase_history.save_ingest("octocat", "Hello-World", _ingest_result(), _NOW)


def test_list_reviews_returns_empty_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: None)

    assert supabase_history.list_reviews() == []


def test_list_reviews_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    rows = [{"id": 1, "repo": "octocat/Hello-World", "pr_number": 7}]
    query = mock_client.table.return_value.select.return_value.order.return_value.limit
    query.return_value.execute.return_value = MagicMock(data=rows)
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    result = supabase_history.list_reviews(limit=10)

    assert result == rows
    mock_client.table.assert_called_once_with("reviews")
    mock_client.table.return_value.select.assert_called_once_with("*")
    mock_client.table.return_value.select.return_value.order.assert_called_once_with(
        "created_at", desc=True
    )
    query.assert_called_once_with(10)


def test_list_reviews_returns_empty_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    query = mock_client.table.return_value.select.return_value.order.return_value.limit
    query.return_value.execute.side_effect = RuntimeError("down")
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    assert supabase_history.list_reviews() == []


def test_get_review_returns_none_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: None)

    assert supabase_history.get_review(1) is None


def test_get_review_returns_row(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    row = {"id": 1, "repo": "octocat/Hello-World", "pr_number": 7}
    query = mock_client.table.return_value.select.return_value.eq.return_value.limit
    query.return_value.execute.return_value = MagicMock(data=[row])
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    result = supabase_history.get_review(1)

    assert result == row
    mock_client.table.assert_called_once_with("reviews")
    mock_client.table.return_value.select.assert_called_once_with("*")
    mock_client.table.return_value.select.return_value.eq.assert_called_once_with("id", 1)
    query.assert_called_once_with(1)


def test_get_review_returns_none_when_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    query = mock_client.table.return_value.select.return_value.eq.return_value.limit
    query.return_value.execute.return_value = MagicMock(data=[])
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    assert supabase_history.get_review(999) is None


def test_get_review_returns_none_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    query = mock_client.table.return_value.select.return_value.eq.return_value.limit
    query.return_value.execute.side_effect = RuntimeError("down")
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    assert supabase_history.get_review(1) is None


def _record_query(mock_client: MagicMock) -> MagicMock:
    """The mock at the end of load_latest_review_record's select/eq/eq/not/order/limit chain."""
    chain = mock_client.table.return_value.select.return_value
    chain = chain.eq.return_value.eq.return_value.not_.is_.return_value
    return chain.order.return_value.limit.return_value


def test_load_latest_review_record_returns_none_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: None)

    assert supabase_history.load_latest_review_record("octocat", "Hello-World", 7) is None


def test_load_latest_review_record_round_trips_the_saved_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved = _review_record(head_sha="deadbeef")
    mock_client = MagicMock()
    _record_query(mock_client).execute.return_value.data = [
        {"record": saved.model_dump(mode="json")}
    ]
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    loaded = supabase_history.load_latest_review_record("octocat", "Hello-World", 7)

    assert loaded == saved
    select = mock_client.table.return_value.select
    select.return_value.eq.assert_called_once_with("repo", "octocat/Hello-World")
    select.return_value.eq.return_value.eq.assert_called_once_with("pr_number", 7)


def test_load_latest_review_record_returns_none_when_no_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    _record_query(mock_client).execute.return_value.data = []
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    assert supabase_history.load_latest_review_record("octocat", "Hello-World", 7) is None


def test_load_latest_review_record_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    _record_query(mock_client).execute.side_effect = RuntimeError("down")
    monkeypatch.setattr("core.supabase_history.get_supabase_client", lambda: mock_client)

    assert supabase_history.load_latest_review_record("octocat", "Hello-World", 7) is None

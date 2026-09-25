from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from postgrest.exceptions import APIError

from core import supabase_jobs

_JOB_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _row(**overrides: object) -> dict:
    now = datetime.now(UTC).isoformat()
    row = {
        "id": str(_JOB_ID),
        "kind": "review",
        "repo": "octocat/Hello-World",
        "pr_number": 7,
        "status": "running",
        "stage": "queued",
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    row.update(overrides)
    return row


def _unique_violation() -> APIError:
    return APIError({"code": "23505", "message": "duplicate key value violates unique constraint"})


# ── create_job ──────────────────────────────────────────────────────────────


def test_create_job_raises_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: None)

    with pytest.raises(RuntimeError):
        supabase_jobs.create_job(_JOB_ID, "review", "octocat/Hello-World", 7)


def test_create_job_inserts_expected_row(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    expected = _row()
    insert_call = mock_client.table.return_value.insert
    insert_call.return_value.execute.return_value = MagicMock(data=[expected])
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    job, created = supabase_jobs.create_job(_JOB_ID, "review", "octocat/Hello-World", 7)

    assert created is True
    assert job == expected
    insert_call.assert_called_once_with(
        {"id": str(_JOB_ID), "kind": "review", "repo": "octocat/Hello-World", "pr_number": 7}
    )
    # Cleanup runs before the insert, on every call — not just when duplicates happen.
    mock_client.table.return_value.delete.return_value.lt.return_value.execute.assert_called_once()


def test_create_job_cleanup_failure_does_not_block_insert(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.table.return_value.delete.return_value.lt.return_value.execute.side_effect = (
        RuntimeError("down")
    )
    expected = _row()
    mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[expected]
    )
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    job, created = supabase_jobs.create_job(_JOB_ID, "review", "octocat/Hello-World", 7)

    assert created is True
    assert job == expected


def test_create_job_duplicate_id_returns_existing_job(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.side_effect = _unique_violation()
    expected = _row()
    select_query = mock_client.table.return_value.select.return_value.eq.return_value.limit
    select_query.return_value.execute.return_value = MagicMock(data=[expected])
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    job, created = supabase_jobs.create_job(_JOB_ID, "review", "octocat/Hello-World", 7)

    assert created is False
    assert job == expected


def test_create_job_reraises_non_conflict_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    other_error = APIError({"code": "42501", "message": "permission denied"})
    mock_client.table.return_value.insert.return_value.execute.side_effect = other_error
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    with pytest.raises(APIError):
        supabase_jobs.create_job(_JOB_ID, "review", "octocat/Hello-World", 7)


def test_create_job_reraises_when_conflict_but_existing_row_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unique violation fired, but the row can't be read back (e.g. a transient error in
    the follow-up select) — surface the original conflict rather than pretending nothing
    happened.
    """
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.side_effect = _unique_violation()
    select_query = mock_client.table.return_value.select.return_value.eq.return_value.limit
    select_query.return_value.execute.return_value = MagicMock(data=[])
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    with pytest.raises(APIError):
        supabase_jobs.create_job(_JOB_ID, "review", "octocat/Hello-World", 7)


# ── update_job ──────────────────────────────────────────────────────────────


def test_update_job_noop_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: None)

    supabase_jobs.update_job(_JOB_ID, stage="running review agents")


def test_update_job_patches_only_given_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    supabase_jobs.update_job(_JOB_ID, stage="running review agents")

    update_call = mock_client.table.return_value.update
    fields = update_call.call_args.args[0]
    assert fields["stage"] == "running review agents"
    assert "status" not in fields
    assert "result" not in fields
    assert "error" not in fields
    assert "updated_at" in fields
    mock_client.table.return_value.update.return_value.eq.assert_called_once_with(
        "id", str(_JOB_ID)
    )


def test_update_job_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = (
        RuntimeError("down")
    )
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    supabase_jobs.update_job(_JOB_ID, status="failed", error="boom")


# ── get_job ─────────────────────────────────────────────────────────────────


def test_get_job_returns_none_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: None)

    assert supabase_jobs.get_job(_JOB_ID) is None


def test_get_job_returns_none_when_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    query = mock_client.table.return_value.select.return_value.eq.return_value.limit
    query.return_value.execute.return_value = MagicMock(data=[])
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    assert supabase_jobs.get_job(_JOB_ID) is None


def test_get_job_returns_none_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    query = mock_client.table.return_value.select.return_value.eq.return_value.limit
    query.return_value.execute.side_effect = RuntimeError("down")
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    assert supabase_jobs.get_job(_JOB_ID) is None


def test_get_job_returns_running_row_when_recently_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    recent = (datetime.now(UTC) - timedelta(seconds=30)).isoformat()
    row = _row(status="running", updated_at=recent)
    query = mock_client.table.return_value.select.return_value.eq.return_value.limit
    query.return_value.execute.return_value = MagicMock(data=[row])
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    result = supabase_jobs.get_job(_JOB_ID)

    assert result == row


def test_get_job_stale_running_job_reads_as_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The required dead-job test: a running job whose updated_at is stale (no progress in
    over 5 minutes — e.g. the server restarted mid-job) reads back as failed.
    """
    mock_client = MagicMock()
    stale = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    row = _row(status="running", updated_at=stale)
    query = mock_client.table.return_value.select.return_value.eq.return_value.limit
    query.return_value.execute.return_value = MagicMock(data=[row])
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    result = supabase_jobs.get_job(_JOB_ID)

    assert result is not None
    assert result["status"] == "failed"
    assert result["error"]


def test_get_job_stale_but_terminal_status_is_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dead-job check only applies to status=running — an old succeeded/failed job must
    not be rewritten just because it's old.
    """
    mock_client = MagicMock()
    stale = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    row = _row(status="succeeded", updated_at=stale, result={"verdict": "APPROVE"})
    query = mock_client.table.return_value.select.return_value.eq.return_value.limit
    query.return_value.execute.return_value = MagicMock(data=[row])
    monkeypatch.setattr("core.supabase_jobs.get_supabase_client", lambda: mock_client)

    result = supabase_jobs.get_job(_JOB_ID)

    assert result == row

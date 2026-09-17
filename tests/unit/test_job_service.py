from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from agents.state import AgentResult
from core.ingest_service import IngestResult
from core.job_service import start_ingest_job, start_review_job
from core.review_service import ReviewResult

_JOB_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
_PATCH = "core.job_service.{}"


def _agent_result() -> AgentResult:
    return AgentResult(summary="ok", verdict="APPROVE", issues=[], suggestions=[])


def _review_result() -> ReviewResult:
    return ReviewResult(
        pr_number=7,
        summary="Looks good",
        verdict="APPROVE",
        issues=[],
        suggestions=[],
        security_result=_agent_result(),
        quality_result=_agent_result(),
        test_result=_agent_result(),
    )


def _ingest_result() -> IngestResult:
    return IngestResult(issues_indexed=1, prs_indexed=2, commits_indexed=3, total_newly_indexed=6)


# ── start_review_job ──────────────────────────────────────────────────────────


async def test_start_review_job_marks_succeeded_with_result() -> None:
    result = _review_result()
    with (
        patch(_PATCH.format("review_pr"), AsyncMock(return_value=result)),
        patch(_PATCH.format("supabase_jobs.update_job"), MagicMock()) as update_job,
    ):
        await start_review_job(_JOB_ID, "owner", "repo", 7, full=False)

    final_call = update_job.call_args
    assert final_call.args == (_JOB_ID,)
    assert final_call.kwargs["status"] == "succeeded"
    assert final_call.kwargs["stage"] == "done"
    assert final_call.kwargs["result"]["verdict"] == "APPROVE"
    assert final_call.kwargs["result"]["pr_number"] == 7


async def test_start_review_job_forwards_on_stage_to_update_job() -> None:
    async def fake_review_pr(owner, repo, pr_number, full, on_stage=None):
        await on_stage("running review agents")
        return _review_result()

    with (
        patch(_PATCH.format("review_pr"), AsyncMock(side_effect=fake_review_pr)),
        patch(_PATCH.format("supabase_jobs.update_job"), MagicMock()) as update_job,
    ):
        await start_review_job(_JOB_ID, "owner", "repo", 7, full=False)

    stage_calls = [c for c in update_job.call_args_list if "stage" in c.kwargs]
    assert any(c.kwargs["stage"] == "running review agents" for c in stage_calls)


async def test_start_review_job_marks_failed_on_exception() -> None:
    with (
        patch(_PATCH.format("review_pr"), AsyncMock(side_effect=RuntimeError("boom"))),
        patch(_PATCH.format("supabase_jobs.update_job"), MagicMock()) as update_job,
    ):
        await start_review_job(_JOB_ID, "owner", "repo", 7, full=False)

    update_job.assert_called_once_with(_JOB_ID, status="failed", error="boom")


# ── start_ingest_job ──────────────────────────────────────────────────────────


async def test_start_ingest_job_marks_succeeded_with_result() -> None:
    result = _ingest_result()
    with (
        patch(_PATCH.format("ingest_repository"), AsyncMock(return_value=result)),
        patch(_PATCH.format("supabase_jobs.update_job"), MagicMock()) as update_job,
    ):
        await start_ingest_job(_JOB_ID, "owner", "repo", full=False)

    final_call = update_job.call_args
    assert final_call.kwargs["status"] == "succeeded"
    assert final_call.kwargs["stage"] == "done"
    assert final_call.kwargs["result"]["total_newly_indexed"] == 6


async def test_start_ingest_job_marks_failed_on_exception() -> None:
    with (
        patch(_PATCH.format("ingest_repository"), AsyncMock(side_effect=RuntimeError("boom"))),
        patch(_PATCH.format("supabase_jobs.update_job"), MagicMock()) as update_job,
    ):
        await start_ingest_job(_JOB_ID, "owner", "repo", full=False)

    update_job.assert_called_once_with(_JOB_ID, status="failed", error="boom")

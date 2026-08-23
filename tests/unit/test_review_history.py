from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.review_history import load_review_record, save_review_record
from retrieval.context_builder import PersistedAgentResult, ReviewRecord

_NOW = datetime(2024, 6, 1, tzinfo=UTC)


def _make_record(head_sha: str = "abc123") -> ReviewRecord:
    agent = PersistedAgentResult(summary="ok", verdict="APPROVE", issues=[], suggestions=[])
    return ReviewRecord(
        head_sha=head_sha,
        verdict="APPROVE",
        summary="Looks good",
        issues=[],
        suggestions=[],
        security_result=agent,
        quality_result=agent,
        test_result=agent,
        reviewed_at=_NOW,
    )


def test_load_returns_none_when_file_missing(tmp_path: Path) -> None:
    path = str(tmp_path / "review_history.json")
    assert load_review_record("owner", "repo", 1, path=path) is None


def test_load_returns_none_for_unknown_key(tmp_path: Path) -> None:
    path = str(tmp_path / "review_history.json")
    save_review_record("owner", "repo", 1, _make_record(), path=path)

    assert load_review_record("owner", "repo", 2, path=path) is None


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    path = str(tmp_path / "review_history.json")
    record = _make_record(head_sha="deadbeef")
    save_review_record("owner", "repo", 7, record, path=path)

    loaded = load_review_record("owner", "repo", 7, path=path)

    assert loaded is not None
    assert loaded.head_sha == "deadbeef"
    assert loaded.verdict == "APPROVE"
    assert loaded.security_result.summary == "ok"


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    path = str(tmp_path / "nested" / "dir" / "review_history.json")
    save_review_record("owner", "repo", 1, _make_record(), path=path)

    assert Path(path).exists()
    assert load_review_record("owner", "repo", 1, path=path) is not None


def test_different_pr_keys_do_not_clobber_each_other(tmp_path: Path) -> None:
    path = str(tmp_path / "review_history.json")
    save_review_record("owner", "repo", 1, _make_record(head_sha="sha-one"), path=path)
    save_review_record("owner", "repo", 2, _make_record(head_sha="sha-two"), path=path)

    first = load_review_record("owner", "repo", 1, path=path)
    second = load_review_record("owner", "repo", 2, path=path)

    assert first is not None
    assert second is not None
    assert first.head_sha == "sha-one"
    assert second.head_sha == "sha-two"


def test_different_repos_do_not_clobber_each_other(tmp_path: Path) -> None:
    path = str(tmp_path / "review_history.json")
    save_review_record("owner", "repo-a", 1, _make_record(head_sha="sha-a"), path=path)
    save_review_record("owner", "repo-b", 1, _make_record(head_sha="sha-b"), path=path)

    a = load_review_record("owner", "repo-a", 1, path=path)
    b = load_review_record("owner", "repo-b", 1, path=path)

    assert a is not None
    assert b is not None
    assert a.head_sha == "sha-a"
    assert b.head_sha == "sha-b"

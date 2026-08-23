from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.ingest_history import IngestRecord, load_ingest_record, save_ingest_record

_NOW = datetime(2024, 6, 1, tzinfo=UTC)


def test_load_returns_none_when_file_missing(tmp_path: Path) -> None:
    path = str(tmp_path / "ingest_history.json")
    assert load_ingest_record("owner", "repo", path=path) is None


def test_load_returns_none_for_unknown_key(tmp_path: Path) -> None:
    path = str(tmp_path / "ingest_history.json")
    save_ingest_record("owner", "repo", IngestRecord(last_ingested_at=_NOW), path=path)

    assert load_ingest_record("owner", "other-repo", path=path) is None


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    path = str(tmp_path / "ingest_history.json")
    record = IngestRecord(last_ingested_at=_NOW)
    save_ingest_record("owner", "repo", record, path=path)

    loaded = load_ingest_record("owner", "repo", path=path)

    assert loaded is not None
    assert loaded.last_ingested_at == _NOW


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    path = str(tmp_path / "nested" / "dir" / "ingest_history.json")
    save_ingest_record("owner", "repo", IngestRecord(last_ingested_at=_NOW), path=path)

    assert Path(path).exists()
    assert load_ingest_record("owner", "repo", path=path) is not None


def test_different_repos_do_not_clobber_each_other(tmp_path: Path) -> None:
    path = str(tmp_path / "ingest_history.json")
    later = datetime(2024, 7, 1, tzinfo=UTC)
    save_ingest_record("owner", "repo-a", IngestRecord(last_ingested_at=_NOW), path=path)
    save_ingest_record("owner", "repo-b", IngestRecord(last_ingested_at=later), path=path)

    a = load_ingest_record("owner", "repo-a", path=path)
    b = load_ingest_record("owner", "repo-b", path=path)

    assert a is not None
    assert b is not None
    assert a.last_ingested_at == _NOW
    assert b.last_ingested_at == later

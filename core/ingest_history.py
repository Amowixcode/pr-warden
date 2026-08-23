from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from config.settings import settings


class IngestRecord(BaseModel):
    """The last-ingested timestamp for a repo, used as the ``since`` cutoff on the next
    incremental ingest.
    """

    last_ingested_at: datetime


def _key(owner: str, repo: str) -> str:
    return f"{owner}/{repo}"


def _resolve_path(path: str | None) -> Path:
    return Path(path or settings.ingest_history_path)


def _load_all(path: str | None) -> dict[str, dict]:
    resolved = _resolve_path(path)
    if not resolved.exists():
        return {}
    return json.loads(resolved.read_text(encoding="utf-8"))


def _save_all(path: str | None, data: dict[str, dict]) -> None:
    resolved = _resolve_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_ingest_record(owner: str, repo: str, path: str | None = None) -> IngestRecord | None:
    """Load the last-persisted ingest record for a repo, or None if never ingested before.

    Args:
        owner: GitHub repository owner.
        repo: Repository name.
        path: Override for the JSON store's path. Falls back to
            ``settings.ingest_history_path`` when omitted.

    Returns:
        The persisted IngestRecord, or None if this repo has no history.
    """
    raw = _load_all(path).get(_key(owner, repo))
    return IngestRecord.model_validate(raw) if raw is not None else None


def save_ingest_record(
    owner: str,
    repo: str,
    record: IngestRecord,
    path: str | None = None,
) -> None:
    """Persist (overwrite) the ingest record for a repo, keyed by owner/repo.

    Args:
        owner: GitHub repository owner.
        repo: Repository name.
        record: The ingest record to persist.
        path: Override for the JSON store's path. Falls back to
            ``settings.ingest_history_path`` when omitted.
    """
    data = _load_all(path)
    data[_key(owner, repo)] = record.model_dump(mode="json")
    _save_all(path, data)

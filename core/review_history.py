from __future__ import annotations

import json
from pathlib import Path

from config.settings import settings
from retrieval.context_builder import ReviewRecord


def _key(owner: str, repo: str, pr_number: int) -> str:
    return f"{owner}/{repo}#{pr_number}"


def _resolve_path(path: str | None) -> Path:
    return Path(path or settings.review_history_path)


def _load_all(path: str | None) -> dict[str, dict]:
    resolved = _resolve_path(path)
    if not resolved.exists():
        return {}
    return json.loads(resolved.read_text(encoding="utf-8"))


def _save_all(path: str | None, data: dict[str, dict]) -> None:
    resolved = _resolve_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_review_record(
    owner: str,
    repo: str,
    pr_number: int,
    path: str | None = None,
) -> ReviewRecord | None:
    """Load the last-persisted review record for a PR, or None if never reviewed before.

    Args:
        owner: GitHub repository owner.
        repo: Repository name.
        pr_number: Pull request number.
        path: Override for the JSON store's path. Falls back to
            ``settings.review_history_path`` when omitted.

    Returns:
        The persisted ReviewRecord, or None if this PR has no history.
    """
    raw = _load_all(path).get(_key(owner, repo, pr_number))
    return ReviewRecord.model_validate(raw) if raw is not None else None


def save_review_record(
    owner: str,
    repo: str,
    pr_number: int,
    record: ReviewRecord,
    path: str | None = None,
) -> None:
    """Persist (overwrite) the review record for a PR, keyed by owner/repo/PR number.

    Args:
        owner: GitHub repository owner.
        repo: Repository name.
        pr_number: Pull request number.
        record: The review record to persist.
        path: Override for the JSON store's path. Falls back to
            ``settings.review_history_path`` when omitted.
    """
    data = _load_all(path)
    data[_key(owner, repo, pr_number)] = record.model_dump(mode="json")
    _save_all(path, data)

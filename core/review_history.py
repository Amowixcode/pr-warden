from __future__ import annotations

import json
from pathlib import Path

from config.settings import get_settings
from core import supabase_history
from retrieval.context_builder import ReviewRecord


def _key(owner: str, repo: str, pr_number: int) -> str:
    return f"{owner}/{repo}#{pr_number}"


def _resolve_path(path: str | None) -> Path:
    return Path(path or get_settings().review_history_path)


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


def get_review_by_id(review_id: int, path: str | None = None) -> dict | None:
    """Look up a single review by its Supabase row id, enriched with per-agent results.

    Supabase's `reviews` table has no per-agent breakdown (see core/supabase_history.py) —
    only the local JSON ReviewRecord does. Joining the two here lets the API return full
    per-agent detail without a Supabase schema change. If the local store has no matching
    entry (different instance, or the review predates this join), the per-agent fields come
    back None rather than fabricated.

    Args:
        review_id: The Supabase `reviews.id` to look up.
        path: Override for the local JSON store's path. Falls back to
            ``settings.review_history_path`` when omitted.

    Returns:
        A dict with the flat Supabase fields plus security_result/quality_result/test_result
        (each a PersistedAgentResult or None), or None if no such review exists in Supabase.
    """
    row = supabase_history.get_review(review_id)
    if row is None:
        return None

    owner, _, repo = row["repo"].partition("/")
    local = load_review_record(owner, repo, row["pr_number"], path=path) if repo else None

    return {
        "id": row["id"],
        "repo": row["repo"],
        "pr_number": row["pr_number"],
        "head_sha": row["head_sha"],
        "verdict": row["verdict"],
        "summary": row["summary"],
        "issues": row["issues"],
        "suggestions": row["suggestions"],
        "created_at": row["created_at"],
        "security_result": local.security_result if local else None,
        "quality_result": local.quality_result if local else None,
        "test_result": local.test_result if local else None,
    }

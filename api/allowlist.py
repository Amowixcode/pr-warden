from __future__ import annotations

from fastapi import HTTPException

from config.settings import get_settings


def check_repo_allowed(owner: str, repo: str) -> None:
    """Reject a repo outside the configured allowlist, if one is configured.

    An unset REVIEW_ALLOWED_REPOS means no allowlist is enforced — matches this codebase's
    existing "unset = permissive" default for optional security knobs (see api/auth.py's
    API_SHARED_KEY). Set it in production to bound /review to known repos, so a caller can't
    request a review of an arbitrarily large diff on an arbitrary repository.
    """
    settings = get_settings()
    if not settings.review_allowed_repos:
        return
    allowed = {r.strip().lower() for r in settings.review_allowed_repos.split(",") if r.strip()}
    if f"{owner}/{repo}".lower() not in allowed:
        raise HTTPException(status_code=403, detail="repository not in the review allowlist")

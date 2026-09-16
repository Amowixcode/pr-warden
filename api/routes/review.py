from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from api.allowlist import check_repo_allowed
from api.models import ReviewRequest, ReviewResponse

if TYPE_CHECKING:
    from core.review_service import ReviewResult

router = APIRouter()


def _parse_repo(repo: str) -> tuple[str, str]:
    """Split 'owner/repo' into (owner, repo), raising a clean 400 otherwise."""
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(status_code=400, detail=f"expected 'owner/repo', got {repo!r}")
    return parts[0], parts[1]


async def review_pr(owner: str, repo: str, pr_number: int, full: bool = False) -> ReviewResult:
    """Lazily import core.review_service so it never joins api.main's module-scope imports."""
    from core.review_service import review_pr as _review_pr

    return await _review_pr(owner, repo, pr_number, full=full)


@router.post("/review", response_model=ReviewResponse)
async def review(request: ReviewRequest) -> ReviewResponse:
    """Review a pull request using historical repo context and OpenAI.

    `full=True` bypasses the incremental/cached review history — the only way the web UI can
    force a fresh review of a PR that's currently showing a stale cached verdict.
    """
    owner, name = _parse_repo(request.repo)
    check_repo_allowed(owner, name)
    result = await review_pr(owner, name, request.pr_number, full=request.full)
    return ReviewResponse.model_validate(result)

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models import ReviewRequest, ReviewResponse
from core.review_service import review_pr

router = APIRouter()


def _parse_repo(repo: str) -> tuple[str, str]:
    """Split 'owner/repo' into (owner, repo), raising a clean 400 otherwise."""
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(status_code=400, detail=f"expected 'owner/repo', got {repo!r}")
    return parts[0], parts[1]


@router.post("/review", response_model=ReviewResponse)
async def review(request: ReviewRequest) -> ReviewResponse:
    """Review a pull request using historical repo context and OpenAI."""
    owner, name = _parse_repo(request.repo)
    result = await review_pr(owner, name, request.pr_number)
    return ReviewResponse.model_validate(result)

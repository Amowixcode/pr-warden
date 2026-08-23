from __future__ import annotations

from fastapi import APIRouter

from api.models import OpenPRResponse
from core.pr_service import list_open_prs

router = APIRouter()


@router.get("/prs/{owner}/{repo}", response_model=list[OpenPRResponse])
async def list_prs(owner: str, repo: str) -> list[OpenPRResponse]:
    """List open pull requests for a repository."""
    prs = await list_open_prs(owner, repo)
    return [OpenPRResponse.model_validate(pr) for pr in prs]

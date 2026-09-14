from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from api.models import OpenPRResponse

if TYPE_CHECKING:
    from core.pr_service import OpenPR

router = APIRouter()


async def list_open_prs(owner: str, repo: str) -> list[OpenPR]:
    """Lazily import core.pr_service so it never joins api.main's module-scope imports."""
    from core.pr_service import list_open_prs as _list_open_prs

    return await _list_open_prs(owner, repo)


@router.get("/prs/{owner}/{repo}", response_model=list[OpenPRResponse])
async def list_prs(owner: str, repo: str) -> list[OpenPRResponse]:
    """List open pull requests for a repository."""
    prs = await list_open_prs(owner, repo)
    return [OpenPRResponse.model_validate(pr) for pr in prs]

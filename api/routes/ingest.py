from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from api.models import IngestRequest, IngestResponse

if TYPE_CHECKING:
    from core.ingest_service import IngestResult

router = APIRouter()


def _parse_repo(repo: str) -> tuple[str, str]:
    """Split 'owner/repo' into (owner, repo), raising a clean 400 otherwise."""
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(status_code=400, detail=f"expected 'owner/repo', got {repo!r}")
    return parts[0], parts[1]


async def ingest_repository(owner: str, repo: str) -> IngestResult:
    """Lazily import core.ingest_service so it never joins api.main's module-scope imports."""
    from core.ingest_service import ingest_repository as _ingest_repository

    return await _ingest_repository(owner, repo)


@router.post("/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest) -> IngestResponse:
    """Index a repository's issues, merged PRs, and commits into ChromaDB."""
    owner, name = _parse_repo(request.repo)
    result = await ingest_repository(owner, name)
    return IngestResponse.model_validate(result)

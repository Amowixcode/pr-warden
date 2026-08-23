from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models import IngestRequest, IngestResponse
from core.ingest_service import ingest_repository

router = APIRouter()


def _parse_repo(repo: str) -> tuple[str, str]:
    """Split 'owner/repo' into (owner, repo), raising a clean 400 otherwise."""
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(status_code=400, detail=f"expected 'owner/repo', got {repo!r}")
    return parts[0], parts[1]


@router.post("/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest) -> IngestResponse:
    """Index a repository's issues, merged PRs, and commits into ChromaDB."""
    owner, name = _parse_repo(request.repo)
    result = await ingest_repository(owner, name)
    return IngestResponse.model_validate(result)

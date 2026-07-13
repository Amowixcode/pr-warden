from __future__ import annotations

from fastapi import APIRouter

from api.models import HealthResponse
from core.doctor_service import run_doctor_checks

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Mirror `warden doctor`: report Settings, GitHub, OpenAI, and ChromaDB check results."""
    result = await run_doctor_checks()
    return HealthResponse.model_validate(result)

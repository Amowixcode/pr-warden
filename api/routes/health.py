from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from api.auth import require_api_key
from api.models import HealthResponse, LivenessResponse

if TYPE_CHECKING:
    from core.doctor_service import DoctorResult

router = APIRouter()


@router.get("/health", response_model=LivenessResponse)
async def health() -> LivenessResponse:
    """Liveness only — answers from process state, no network/disk/vector-store I/O.

    This is Render's healthCheckPath. It must stay cheap: Render polls it on every deploy
    and continuously afterwards, so any I/O here becomes an external-API dependency for
    whether the service is considered up.
    """
    return LivenessResponse()


async def run_doctor_checks() -> DoctorResult:
    """Lazily import the doctor service so it never joins api.main's module-scope imports."""
    from core.doctor_service import run_doctor_checks as _run_doctor_checks

    return await _run_doctor_checks()


@router.get("/health/deep", response_model=HealthResponse, dependencies=[Depends(require_api_key)])
async def health_deep() -> HealthResponse:
    """Mirror `warden doctor`: report Settings, GitHub, OpenAI, and ChromaDB check results.

    Behind require_api_key when API_SHARED_KEY is configured, since it reveals whether the
    GitHub and OpenAI credentials are valid. Not polled by Render — manual/monitoring use only.
    """
    result = await run_doctor_checks()
    return HealthResponse.model_validate(result)

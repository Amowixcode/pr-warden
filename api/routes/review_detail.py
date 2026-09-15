from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from api.models import ReviewDetailResponse

router = APIRouter()


def get_review_by_id(review_id: int) -> dict | None:
    """Lazily import core.review_history so it never joins api.main's module-scope imports."""
    from core.review_history import get_review_by_id as _get_review_by_id

    return _get_review_by_id(review_id)


@router.get("/reviews/{review_id}", response_model=ReviewDetailResponse)
async def review_detail(review_id: int) -> dict:
    """Return one full review, including per-agent results. No auth — see api/main.py."""
    result = await asyncio.to_thread(get_review_by_id, review_id)
    if result is None:
        raise HTTPException(status_code=404, detail="review not found")
    return result

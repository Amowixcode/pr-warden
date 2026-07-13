from __future__ import annotations

import asyncio

from fastapi import APIRouter

from api.models import ReviewHistoryItem
from core.supabase_history import list_reviews

router = APIRouter()


@router.get("/reviews", response_model=list[ReviewHistoryItem])
async def reviews() -> list[dict]:
    """List past reviews from Supabase. Returns [] if Supabase isn't configured."""
    return await asyncio.to_thread(list_reviews)

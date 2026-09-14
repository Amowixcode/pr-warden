from __future__ import annotations

import asyncio

from fastapi import APIRouter

from api.models import ReviewHistoryItem

router = APIRouter()


def list_reviews() -> list[dict]:
    """Lazily import core.supabase_history so it never joins api.main's module-scope imports."""
    from core.supabase_history import list_reviews as _list_reviews

    return _list_reviews()


@router.get("/reviews", response_model=list[ReviewHistoryItem])
async def reviews() -> list[dict]:
    """List past reviews from Supabase. Returns [] if Supabase isn't configured."""
    return await asyncio.to_thread(list_reviews)

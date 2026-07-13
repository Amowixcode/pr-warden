from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/reviews")
async def reviews() -> list[dict]:
    """List past reviews. Stubbed empty until Supabase-backed history lands in a later issue."""
    return []

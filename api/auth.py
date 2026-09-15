from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from config.settings import get_settings


async def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Enforce API_SHARED_KEY when configured; a no-op when it's unset (e.g. local dev/tests)."""
    settings = get_settings()
    if settings.api_shared_key and x_api_key != settings.api_shared_key:
        raise HTTPException(status_code=401, detail="invalid or missing API key")

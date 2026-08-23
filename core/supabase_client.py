from __future__ import annotations

from config.settings import settings
from supabase import Client, create_client


def get_supabase_client() -> Client | None:
    """Build a Supabase client from Settings, or None if Supabase isn't configured.

    Supabase history storage is optional and additive to the local JSON store — callers must
    degrade gracefully (no-op / empty result) when this returns None.
    """
    if not settings.supabase_url or not settings.supabase_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_key)

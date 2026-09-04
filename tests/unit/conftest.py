from __future__ import annotations

import pytest

from config.settings import get_settings


@pytest.fixture(autouse=True)
def _no_ambient_api_shared_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests assume API_SHARED_KEY is unset unless a test explicitly configures it —
    without this, a real API_SHARED_KEY in the developer's local .env leaks into every
    unauthenticated-route test and turns an expected 200 into a 401.
    """
    monkeypatch.setattr(get_settings(), "api_shared_key", None)

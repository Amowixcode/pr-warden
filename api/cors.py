from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from config.settings import get_settings

_ALLOW_METHODS = "GET, POST, OPTIONS"
_ALLOW_HEADERS = "Content-Type, X-API-Key"


class AllowedOriginMiddleware(BaseHTTPMiddleware):
    """CORS enforcement for a configurable allowlist of origins, not a wildcard.

    Reads settings.allowed_origins_set fresh on every request (rather than baking an origin
    list in at app-construction time, like Starlette's own CORSMiddleware) so it stays
    consistent with require_api_key's "read live settings" pattern and is monkeypatchable per
    test. Supports multiple origins (e.g. a production frontend plus per-branch Vercel preview
    URLs) since a single exact-match origin can't cover those.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        origin = request.headers.get("origin")
        if origin is None:
            # Not a browser cross-origin request (e.g. curl, server-to-server) — CORS is a
            # browser-enforced mechanism, so there's nothing to add or block here.
            return await call_next(request)

        settings = get_settings()
        allowed = origin in settings.allowed_origins_set

        if request.method == "OPTIONS":
            if not allowed:
                return PlainTextResponse("Disallowed CORS origin", status_code=400)
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": _ALLOW_METHODS,
                    "Access-Control-Allow-Headers": _ALLOW_HEADERS,
                    "Access-Control-Allow-Credentials": "true",
                    # Cloudflare sits in front of Render and can cache a response keyed only on
                    # URL — without this, one origin's preflight could be served back to a
                    # different origin from cache.
                    "Vary": "Origin",
                },
            )

        response = await call_next(request)
        apply_cors_headers(request, response)
        return response


def apply_cors_headers(request: Request, response: Response) -> None:
    """Add CORS headers to `response` for `request`'s Origin, if allowed.

    Shared with the catch-all exception handler in api/main.py: Starlette runs a handler
    registered for the literal `Exception` class inside ServerErrorMiddleware, which sits
    outside every user-added middleware (including AllowedOriginMiddleware), so that handler's
    response never passes through AllowedOriginMiddleware.dispatch.
    """
    origin = request.headers.get("origin")
    if origin is None:
        return
    # Cloudflare sits in front of Render and can cache a response keyed only on URL — without
    # this, one origin's response could be served back to a different origin from cache.
    response.headers["Vary"] = "Origin"
    if origin in get_settings().allowed_origins_set:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"

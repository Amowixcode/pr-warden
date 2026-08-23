from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from config.settings import settings

_ALLOW_METHODS = "GET, POST, OPTIONS"
_ALLOW_HEADERS = "Content-Type, X-API-Key"


class AllowedOriginMiddleware(BaseHTTPMiddleware):
    """CORS enforcement for exactly one configurable origin, not a wildcard.

    Reads settings.allowed_origin fresh on every request (rather than baking an origin list in
    at app-construction time, like Starlette's own CORSMiddleware) so it stays consistent with
    require_api_key's "read live settings" pattern and is monkeypatchable per-test.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        origin = request.headers.get("origin")
        if origin is None:
            # Not a browser cross-origin request (e.g. curl, server-to-server) — CORS is a
            # browser-enforced mechanism, so there's nothing to add or block here.
            return await call_next(request)

        allowed = origin == settings.allowed_origin and settings.allowed_origin is not None

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
                },
            )

        response = await call_next(request)
        if allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

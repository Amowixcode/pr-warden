from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from api.auth import require_api_key
from api.cors import AllowedOriginMiddleware
from api.rate_limiter import check_review_rate_limit
from api.routes.health import router as health_router
from api.routes.history import router as history_router
from api.routes.ingest import router as ingest_router
from api.routes.prs import router as prs_router
from api.routes.review import router as review_router
from core.exceptions import VectorStoreError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Warm the heavy stack (langgraph/llama_index/chromadb/github/openai) in the background.

    Fires and forgets: startup yields immediately so /health can answer right away, and the
    first real request doesn't pay the full import cost. A warm-up failure is logged and
    swallowed — it must never prevent startup or affect /health.
    """

    async def _warm_up() -> None:
        try:
            await asyncio.to_thread(importlib.import_module, "core.review_service")
        except Exception:
            logger.exception("background warm-up of core.review_service failed")

    task = asyncio.create_task(_warm_up())
    app.state.warmup_task = task
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


class _ExternalApiErrorMiddleware(BaseHTTPMiddleware):
    """Maps GitHub/OpenAI SDK errors to a response, without importing those SDKs.

    This has to be middleware rather than a typed `@app.exception_handler(...)`: Starlette
    special-cases a handler registered under the literal `Exception` class — it runs inside
    ServerErrorMiddleware, which re-raises the exception after sending the response. That's
    invisible with a real ASGI server (the client already has the response), but it makes
    TestClient's default `raise_server_exceptions=True` surface a raised exception instead of
    a normal response. Registering GithubException/OpenAIError as their own typed classes (the
    old behavior) avoids that, but requires importing `github`/`openai` just to reference the
    classes — exactly the module-scope cost this refactor removes. Dispatching on the
    exception's defining module name sidesteps both problems.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            module = type(exc).__module__

            if module.startswith("github"):
                data = getattr(exc, "data", None)
                detail = data.get("message", str(exc)) if isinstance(data, dict) else str(exc)
                status = getattr(exc, "status", None)
                if not isinstance(status, int) or not (400 <= status <= 599):
                    status = 502
                return JSONResponse(
                    status_code=status, content={"detail": f"GitHub API error: {detail}"}
                )

            if module.startswith("openai"):
                return JSONResponse(status_code=502, content={"detail": f"OpenAI API error: {exc}"})

            raise


app = FastAPI(title="pr-warden", description="Context-aware PR review API", lifespan=lifespan)

# Order matters: added first so it ends up closer to routing than CORS (see
# _ExternalApiErrorMiddleware's docstring on Starlette's middleware stack ordering) — that way
# CORS still post-processes a GitHub/OpenAI-mapped error response and adds its headers.
app.add_middleware(_ExternalApiErrorMiddleware)
app.add_middleware(AllowedOriginMiddleware)

app.include_router(
    review_router,
    dependencies=[Depends(require_api_key), Depends(check_review_rate_limit)],
)
app.include_router(ingest_router, dependencies=[Depends(require_api_key)])
app.include_router(history_router, dependencies=[Depends(require_api_key)])
app.include_router(prs_router, dependencies=[Depends(require_api_key)])
app.include_router(health_router)


@app.exception_handler(ValidationError)
async def _validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"invalid configuration: {exc}"})


@app.exception_handler(VectorStoreError)
async def _vector_store_error_handler(request: Request, exc: VectorStoreError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


async def _malformed_ai_response_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=502, content={"detail": f"failed to parse the AI review response: {exc}"}
    )


app.add_exception_handler(json.JSONDecodeError, _malformed_ai_response_handler)
app.add_exception_handler(KeyError, _malformed_ai_response_handler)


@app.exception_handler(Exception)
async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"unexpected error: {exc}"})

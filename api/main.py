from __future__ import annotations

import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from github import GithubException
from openai import OpenAIError
from pydantic import ValidationError

from api.routes.health import router as health_router
from api.routes.history import router as history_router
from api.routes.ingest import router as ingest_router
from api.routes.review import router as review_router
from core.exceptions import VectorStoreError

app = FastAPI(title="pr-warden", description="Context-aware PR review API")

app.include_router(review_router)
app.include_router(ingest_router)
app.include_router(history_router)
app.include_router(health_router)


@app.exception_handler(ValidationError)
async def _validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"invalid configuration: {exc}"})


@app.exception_handler(GithubException)
async def _github_exception_handler(request: Request, exc: GithubException) -> JSONResponse:
    detail = exc.data.get("message", str(exc)) if isinstance(exc.data, dict) else str(exc)
    return JSONResponse(status_code=exc.status, content={"detail": f"GitHub API error: {detail}"})


@app.exception_handler(OpenAIError)
async def _openai_error_handler(request: Request, exc: OpenAIError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": f"OpenAI API error: {exc}"})


async def _malformed_ai_response_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=502, content={"detail": f"failed to parse the AI review response: {exc}"}
    )


app.add_exception_handler(json.JSONDecodeError, _malformed_ai_response_handler)
app.add_exception_handler(KeyError, _malformed_ai_response_handler)


@app.exception_handler(VectorStoreError)
async def _vector_store_error_handler(request: Request, exc: VectorStoreError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"unexpected error: {exc}"})

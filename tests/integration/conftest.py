from __future__ import annotations

import http.server
import json
import threading
from dataclasses import dataclass, field
from typing import Any

import pytest


@pytest.fixture
def github_api(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], tuple[dict, Any]]:
    """Patch PyGithub's single HTTP choke point with a (verb, url) -> (headers, body) dispatch.

    Every read call in gh/ (get_repo, get_pull, get_issues, get_pulls, get_commits,
    get_files()) funnels through Requester.requestJsonAndCheck — patching only this one
    method lets PyGithub's real object model, attribute parsing, and pagination run
    untouched; only the literal wire call is faked. Unfixtured calls fail loudly instead
    of being silently 404'd, so a wiring bug surfaces as a clear assertion.
    """
    dispatch: dict[tuple[str, str], tuple[dict, Any]] = {}

    def fake_request_json_and_check(
        self: Any,
        verb: str,
        url: str,
        parameters: dict | None = None,
        headers: dict | None = None,
        input: Any = None,
        follow_302_redirect: bool = False,
    ) -> tuple[dict, Any]:
        key = (verb, url)
        if key not in dispatch:
            raise AssertionError(f"unfixtured GitHub call: {verb} {url} params={parameters}")
        return dispatch[key]

    monkeypatch.setattr(
        "github.Requester.Requester.requestJsonAndCheck", fake_request_json_and_check
    )
    return dispatch


@dataclass
class OpenAIMock:
    """Handle for the local OpenAI mock server — set canned responses, inspect real requests.

    responses_bodies routes by a substring of the incoming request's `instructions` field
    (each agent's system prompt has a unique scope marker, e.g. "SECURITY concerns") rather
    than by call order, since the security/quality/test agents run concurrently and which one
    reaches the mock server first isn't deterministic.
    """

    embedding: list[float] = field(default_factory=lambda: [0.1] * 8)
    responses_bodies: dict[str, dict] = field(default_factory=dict)
    responses_requests: list[dict] = field(default_factory=list)

    def set_responses_body_for(self, instructions_marker: str, body: dict) -> None:
        self.responses_bodies[instructions_marker] = body


class _OpenAIMockHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        body = json.loads(raw) if raw else {}
        state: OpenAIMock = self.server.state  # type: ignore[attr-defined]

        if self.path.endswith("/embeddings"):
            response = _embeddings_response(body, state.embedding)
        elif self.path.endswith("/responses"):
            state.responses_requests.append(body)
            response = _route_responses_body(body, state.responses_bodies)
        else:
            self.send_response(404)
            self.end_headers()
            return

        payload = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass


def _route_responses_body(request_body: dict, responses_bodies: dict[str, dict]) -> dict:
    instructions = request_body.get("instructions", "")
    for marker, body in responses_bodies.items():
        if marker in instructions:
            return body
    raise AssertionError(
        f"no canned /responses body registered for instructions: {instructions!r} "
        f"(registered markers: {list(responses_bodies)})"
    )


def _embeddings_response(request_body: dict, embedding: list[float]) -> dict:
    inputs = request_body.get("input", "")
    count = 1 if isinstance(inputs, str) else len(inputs)
    return {
        "object": "list",
        "data": [{"object": "embedding", "embedding": embedding, "index": i} for i in range(count)],
        "model": request_body.get("model", "text-embedding-3-small"),
        "usage": {"prompt_tokens": count, "total_tokens": count},
    }


class _OpenAIMockServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, *args: Any, state: OpenAIMock, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.state = state


@pytest.fixture
def openai_api(monkeypatch: pytest.MonkeyPatch):
    """Run a local HTTP server and route OpenAI + embedding traffic to it via env vars.

    Neither core/review_service.py::_call_openai nor ingestion/embedder.py::get_embed_model
    pass an explicit base url, so openai.OpenAI() reads OPENAI_BASE_URL and OpenAIEmbedding
    reads OPENAI_API_BASE at client-construction time — setting both here routes every real
    OpenAI call (chat + embeddings) to this server with zero production code changes.
    """
    state = OpenAIMock()
    server = _OpenAIMockServer(("127.0.0.1", 0), _OpenAIMockHandler, state=state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setenv("OPENAI_BASE_URL", base_url)
    monkeypatch.setenv("OPENAI_API_BASE", base_url)

    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def isolated_chroma(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Point Chroma at a tmp_path so the test never touches the real ./data/chroma."""
    from config.settings import settings

    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings, "chroma_collection_name", "integration_test")


@pytest.fixture
def isolated_ingest_history(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Point the ingest-history store at a tmp_path so the test never touches the real file
    (and never picks up a leftover record from a previous local test/dev run).
    """
    from config.settings import settings

    monkeypatch.setattr(settings, "ingest_history_path", str(tmp_path / "ingest_history.json"))


@pytest.fixture
def isolated_review_history(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Point the review-history store at a tmp_path so the test never touches the real file."""
    from config.settings import settings

    monkeypatch.setattr(settings, "review_history_path", str(tmp_path / "review_history.json"))


@pytest.fixture
def isolated_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset Supabase config so core.supabase_history's writes no-op instead of hitting a real
    Supabase project (get_supabase_client() returns None when unconfigured).
    """
    from config.settings import settings

    monkeypatch.setattr(settings, "supabase_url", None)
    monkeypatch.setattr(settings, "supabase_key", None)

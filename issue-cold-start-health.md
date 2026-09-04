## Description

The live deployment takes a very long time to become usable — long enough that demoing it is
not viable. Investigation found three separate defects in the startup path, all in `api/` and
`config/`. They compound: each one makes the others more expensive.

**1. `/health` performs live external API calls, and it is Render's health check path.**

`api/routes/health.py` calls `run_doctor_checks()`, which hits the GitHub API, the OpenAI API,
and ChromaDB. `render.yaml` sets `healthCheckPath: /health`. Render polls that endpoint on every
deploy and continuously afterwards, so:

- deploys do not start routing traffic until two external APIs have answered;
- a slow or rate-limited GitHub/OpenAI at that moment returns `all_passed: false` or times out,
  Render marks the deploy unhealthy and restarts it, and the restart pays the full import cost
  again — a loop that presents externally as "the server is slow";
- the `GITHUB_TOKEN` rate limit is consumed by health polling alone, with no user traffic.

A health check must answer from process state only.

**2. Importing `api.main` costs at least 13 s.**

Measured with `python -X importtime -c "import api.main"` (Windows, local venv):

| module | cumulative |
|---|---|
| `api.main` | 13027 ms |
| `openai` | 5381 ms (`openai.types` alone: 4371 ms) |
| `github` (PyGitHub) | 4525 ms (`github.Auth`: 4396 ms, pulling `requests`: 2438 ms) |
| `fastapi` | 2747 ms |

The measurement aborted at `api/main.py` line 12 (see defect 3), so `langgraph`, `llama_index`
and `chromadb` are **not** included in that 13 s. Windows inflates import time via Defender
scanning, so the number in `python:3.11-slim` will be lower — but it is paid on every cold start,
and it is paid before the health check can answer.

`openai` and `github` are imported at the top of `api/main.py` only to register exception
handlers. They also arrive indirectly through `api/routes/* -> core/*`, so deferring them in
`main.py` alone changes nothing; the route modules have to defer too.

**3. `config/settings.py` instantiates `Settings()` at module scope.**

Line 37 is `settings: Settings = Settings()`. Any missing or malformed environment variable is
therefore raised during *import*, before FastAPI exists — so no exception handler, no readable
message, no `warden doctor` output, just a traceback and a dead process. The registered
`ValidationError` handler in `api/main.py` can never fire for a config error, which is the
case it was written for.

Reproducible locally: `.env` contains `REVIEW_RATE_LIMIT_MAX_CALLS=` (empty), which fails
`int` parsing and aborts `import api.main`. `render.yaml` does not set that variable, so the
deployed service currently falls back to the default and is not affected — but any future env
var typo in the Render dashboard would take the service down with no diagnosable error.

## Scope

### 1. Split the health endpoint

- `GET /health` — liveness only. Returns `200` from process state, performs no network, disk or
  vector-store I/O, and imports nothing heavy. Remains unauthenticated. Stays as
  `healthCheckPath` in `render.yaml`.
- `GET /health/deep` — the current behaviour: full `run_doctor_checks()` result, `HealthResponse`
  model unchanged. Import `core.doctor_service` inside the handler, not at module scope.
- Decide and document whether `/health/deep` requires `X-API-Key`. It reveals whether GitHub and
  OpenAI credentials are valid, so it should sit behind `require_api_key` when one is configured.
- Repoint `.github/workflows/keep-alive.yml` at `/health/deep`. That ping currently does double
  duty: it wakes Render *and* stops Supabase pausing, because Supabase's free-tier pause timer
  only resets on real database activity, not on any HTTP request. A liveness-only `/health` runs
  no Supabase query, so leaving the cron aimed at it would let the database pause after a week of
  inactivity. Render's `healthCheckPath` stays on `/health`.

### 2. Defer heavy imports out of the module import path

- Each module in `api/routes/` imports its `core.*` dependency inside the route function rather
  than at module scope. `api/models.py` (Pydantic only) may stay at module scope.
- `api/main.py` no longer imports `github` or `openai` at module scope. Keep the exception
  handlers working — resolve the exception classes lazily, or register the handlers from within
  `lifespan` once the modules are loaded.
- Add a `lifespan` that warms the heavy stack in the background after startup, so the first real
  request does not pay the deferred cost:

  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      task = asyncio.create_task(
          asyncio.to_thread(importlib.import_module, "core.review_service")
      )
      yield
      task.cancel()
  ```

  A failing warm-up must be logged and swallowed — it must never prevent startup or affect
  `/health`.
- `cli/` is unaffected: startup latency does not matter there and the CLI already imports
  everything it needs.

### 3. Make settings lazy

- Replace module-scope `settings: Settings = Settings()` with a cached accessor:

  ```python
  @lru_cache(maxsize=1)
  def get_settings() -> Settings:
      return Settings()
  ```

- Update all call sites (`api/cors.py`, `api/rate_limiter.py`, `api/main.py`, `core/*`, `cli/*`).
  Note that `api/cors.py` deliberately reads settings fresh per request and is monkeypatched in
  tests — preserve that behaviour, and keep `lru_cache` clearable from tests.
- Give integer settings a `mode="before"` validator so an empty-string env var falls back to the
  field default instead of raising:

  ```python
  @field_validator("review_rate_limit_max_calls", "review_rate_limit_window_seconds",
                   mode="before")
  @classmethod
  def _blank_uses_default(cls, v: object, info: ValidationInfo) -> object:
      if isinstance(v, str) and not v.strip():
          return cls.model_fields[info.field_name].default
      return v
  ```

- A config error must now surface as a handled `500` with a readable message (the existing
  `ValidationError` handler), not as an import crash.

### Out of scope

- Migrating to a `src/pr_warden/` package layout — separate issue.
- Frontend "waking up the server" loading state — separate issue.
- Any change to agent, ingestion or retrieval logic.

## Acceptance Criteria

- [ ] `GET /health` returns `200` with no network, disk or vector-store I/O, verified by a test
      that asserts no GitHub/OpenAI client is constructed
- [ ] `GET /health/deep` returns the same `HealthResponse` payload `/health` returned before this
      change, verified by a test
- [ ] `render.yaml` `healthCheckPath` still points at `/health`, and `DEPLOY.md` documents both
      endpoints and which one Render polls
- [ ] `.github/workflows/keep-alive.yml` pings `/health/deep`, so the Supabase pause timer keeps
      being reset, and `DEPLOY.md` states why the cron and Render's health check deliberately
      target different endpoints
- [ ] `python -X importtime -c "import api.main"` shows `openai`, `github`, `langgraph`,
      `llama_index` and `chromadb` absent from the import tree
- [ ] Measured cold import of `api.main` inside `python:3.11-slim` is under 2 s, with the before
      and after numbers recorded in the PR description
- [ ] The heavy stack is warmed in the background at startup; a warm-up failure is logged and does
      not affect startup or `/health`
- [ ] `POST /review`, `POST /ingest`, `GET /reviews` and `GET /prs` behave identically — existing
      route tests pass unchanged
- [ ] `Settings()` is no longer instantiated at import; `import api.main` succeeds with a
      completely empty environment
- [ ] An empty-string value for `REVIEW_RATE_LIMIT_MAX_CALLS` or
      `REVIEW_RATE_LIMIT_WINDOW_SECONDS` falls back to the field default, covered by a test
- [ ] A genuinely invalid setting produces a handled `500` with a readable message rather than a
      traceback at import, covered by a test
- [ ] No secret value appears in any new log line or error message
- [ ] `uv run ruff check .`, `uv run ruff format .` and `uv run pytest` all exit clean

## Manual verification

Measure the real cold start in the environment that matters — the Linux container, not Windows:

```bash
docker build -t pw .
docker run --rm pw uv run --frozen --no-dev python -X importtime -c "import api.main"
docker run --rm -e GITHUB_TOKEN=x -e OPENAI_API_KEY=x -p 8000:8000 pw
# then: time curl -s localhost:8000/health
```

## Note — not a code change, verify separately

`render.yaml` declares a persistent disk at `/app/data`. Render's free instance types do not
support persistent disks. So the deployed service is either:

- on a paid instance, in which case it never spins down and this issue's import cost plus the
  health-check loop are the *entire* cause of the observed slowness; or
- on a free instance with the disk dropped, in which case `/app/data` is ephemeral and the
  ChromaDB collection, `ingest_history.json` and `review_history.json` are lost on every
  spin-down — meaning the app re-ingests from scratch after each wake, which would dominate
  everything described above.

Check the instance type in the Render dashboard before landing this issue, and run the
restart-survival check already documented in `DEPLOY.md`. If the second case holds, it needs its
own issue.

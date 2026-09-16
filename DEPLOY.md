# Deploying the API to Render

## Required environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | yes | GitHub API access for fetching PRs, issues, commits |
| `OPENAI_API_KEY` | yes | OpenAI access for the review agents |
| `SUPABASE_URL` | no | Supabase project URL — enables `GET /reviews` and history writes |
| `SUPABASE_KEY` | no | Supabase service/anon key, paired with `SUPABASE_URL` |
| `API_SHARED_KEY` | no | Shared secret required as the `X-API-Key` header on `/review` and `/health/deep`. `/health`, `/reviews`, `/prs`, and `/ingest` are always unauthenticated — see [Public vs. protected endpoints](#public-vs-protected-endpoints) below. Unset = no auth on any endpoint (local dev default) |
| `REVIEW_ALLOWED_REPOS` | no | Comma-separated `owner/repo` list. When set, `POST /review` rejects any other repo with `403`. Unset = any repo is reviewable (by anyone who has `API_SHARED_KEY`, or by anyone at all if that's also unset) |
| `ALLOWED_ORIGIN` | no | The deployed frontend's origin (e.g. `https://your-app.vercel.app`) allowed to call the API cross-origin. Unset = no origin is allowed (fail-closed, not a wildcard) |
| `REVIEW_RATE_LIMIT_MAX_CALLS` | no | Max `/review` calls per window before `429`. Default `20` |
| `REVIEW_RATE_LIMIT_WINDOW_SECONDS` | no | Rate-limit window length in seconds. Default `3600` (1 hour) |

`SUPABASE_URL`/`SUPABASE_KEY`, `API_SHARED_KEY`, `REVIEW_ALLOWED_REPOS`, and `ALLOWED_ORIGIN`
are optional — the API runs without them, just with reduced functionality or protection (no
review history persistence, no auth, no repo restriction, no browser access from a frontend).
Set all of them in production — see [Cost controls](#cost-controls) below for why
`REVIEW_ALLOWED_REPOS` in particular matters.

## Frontend (Vercel) environment variables

| Variable | Required | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | yes | This Render service's URL, e.g. `https://your-service.onrender.com` |
| `VITE_API_KEY` | no | Same value as this service's `API_SHARED_KEY`, if set. Baked into the frontend's JS bundle at build time and sent as `X-API-Key` on every request — **this is not a security boundary**. It's visible to anyone who opens the browser's network tab; it only deters opportunistic scanners. Real protection for `/review` is `REVIEW_ALLOWED_REPOS` above, not this key |

The frontend has no key-input field — visitors never see or type a key. `/reviews`, `/prs`,
and `/health` don't need one at all; `/review` needs `VITE_API_KEY` to match the backend's
`API_SHARED_KEY` only if that's configured.

## Public vs. protected endpoints

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /health` | none | Liveness only, no I/O — see below |
| `GET /reviews` | none | Powers the web app's History view and Home screen |
| `GET /reviews/{id}` | none | One full review, including per-agent findings |
| `GET /prs/{owner}/{repo}` | none | Read-only, cheap |
| `POST /review` | `X-API-Key` if `API_SHARED_KEY` set | Also checks `REVIEW_ALLOWED_REPOS` and the rate limit below — the one endpoint that spends OpenAI budget |
| `POST /ingest` | none | Exposed in the web UI's Ingest section, and also usable via `warden ingest` |
| `GET /health/deep` | `X-API-Key` if `API_SHARED_KEY` set | Reveals whether GitHub/OpenAI credentials are valid |

## Deploy via Blueprint (recommended)

`render.yaml` at the repo root defines the service, a persistent disk mounted at `/app/data`
(covers ChromaDB's collection plus the local ingest/review history JSON files — all three
default under `./data/` relative to the container's `/app` working directory), and a `/health`
health check.

## Health endpoints

| Endpoint | Purpose | Auth | I/O |
|---|---|---|---|
| `GET /health` | Liveness. Answers from process state only. This is Render's `healthCheckPath` — it's polled on every deploy and continuously afterwards, so it must stay cheap and never depend on GitHub/OpenAI/ChromaDB being reachable. | Never required | None |
| `GET /health/deep` | The full setup/health check (Settings, GitHub, OpenAI, ChromaDB, Supabase) — same payload `/health` used to return before the split. For manual verification or monitoring, not polled by Render. | `X-API-Key` required when `API_SHARED_KEY` is set (it reveals whether GitHub/OpenAI credentials are valid) | Live network calls to GitHub, OpenAI, ChromaDB, Supabase |

1. Push this branch (with `render.yaml` and `Dockerfile`) to GitHub.
2. In the Render dashboard: **New → Blueprint**, select this repo.
3. Render reads `render.yaml` and creates the web service + disk. You'll be prompted to fill in
   the env vars listed above (`sync: false` means Render asks rather than storing them in the
   file).
4. Deploy.

## Or configure manually via the dashboard

1. **New → Web Service** → connect this repo → Environment: **Docker** (uses the root
   `Dockerfile` automatically).
2. **Disks** tab → add a disk, mount path `/app/data`, size 1 GB (or more).
3. **Environment** tab → add the env vars above.
4. **Settings** tab → Health Check Path: `/health`.
5. Deploy.

## Cost controls

`/review` is the only endpoint that spends OpenAI budget, so it's the only one with layered
protection:

1. **`REVIEW_ALLOWED_REPOS`** — rejects any repo not on the list with a `403`, before any
   GitHub or OpenAI call is made. Bounds *what* can be reviewed.
2. **The rate limit** (`REVIEW_RATE_LIMIT_MAX_CALLS`/`_WINDOW_SECONDS`) — bounds *how often*.
   `check_review_rate_limit` (`api/rate_limiter.py`) is **per-process, in-memory state**: it
   resets on every restart/redeploy and is not shared across replicas. That's adequate for
   this project's single-instance Render deployment, but it is not a distributed rate limiter
   and would need to move to shared storage (Redis, Supabase, etc.) before running more than
   one instance.
3. **A hard monthly spending cap on the OpenAI project itself** — this is the only control
   here that reliably bounds the bill; the two above only reduce the chance of reaching it.
   Set one manually: OpenAI dashboard → the project this deployment's `OPENAI_API_KEY` belongs
   to → **Settings → Limits** → set a monthly budget. Do this before considering a public
   deployment done — it is not configurable from this repo's code or env vars.

## Verifying the deploy (manual — do this after deploying)

1. `curl https://<your-service>.onrender.com/health` → expect `200` and `{"status": "ok"}`
   immediately, regardless of GitHub/OpenAI/Chroma reachability.
   `curl https://<your-service>.onrender.com/health/deep` (add `-H "X-API-Key: ..."` if
   `API_SHARED_KEY` is set) → expect `200` and `{"checks": [...], "all_passed": true}`
   (assuming GitHub/OpenAI/Chroma are all reachable).
2. Ingest a small repo against the live URL, e.g.:
   ```bash
   curl -X POST https://<your-service>.onrender.com/ingest \
     -H "Content-Type: application/json" \
     -d '{"repo": "octocat/Hello-World"}'
   ```
3. **Restart-survival check**: in the Render dashboard, manually restart the service. Once it's
   back up, re-run the same `ingest` call (or hit `GET /reviews` if you'd reviewed a PR) and
   confirm it reflects the prior run's data (e.g. an incremental ingest reports fewer/zero newly
   indexed items instead of re-indexing everything) — this confirms the disk at `/app/data`
   actually persisted across the restart rather than resetting to an empty container filesystem.

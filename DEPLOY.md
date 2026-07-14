# Deploying the API to Render

## Required environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | yes | GitHub API access for fetching PRs, issues, commits |
| `OPENAI_API_KEY` | yes | OpenAI access for the review agents |
| `SUPABASE_URL` | no | Supabase project URL — enables `GET /reviews` and history writes |
| `SUPABASE_KEY` | no | Supabase service/anon key, paired with `SUPABASE_URL` |
| `API_SHARED_KEY` | no | Shared secret required as the `X-API-Key` header on `/review`, `/ingest`, `/reviews`. `/health` is always unauthenticated. Unset = no auth (local dev default) |
| `ALLOWED_ORIGIN` | no | The deployed frontend's origin (e.g. `https://your-app.vercel.app`) allowed to call the API cross-origin. Unset = no origin is allowed (fail-closed, not a wildcard) |
| `REVIEW_RATE_LIMIT_MAX_CALLS` | no | Max `/review` calls per window before `429`. Default `20` |
| `REVIEW_RATE_LIMIT_WINDOW_SECONDS` | no | Rate-limit window length in seconds. Default `3600` (1 hour) |

`SUPABASE_URL`/`SUPABASE_KEY`, `API_SHARED_KEY`, and `ALLOWED_ORIGIN` are optional — the API
runs without them, just with reduced functionality (no review history persistence, no auth, no
browser access from a frontend). Set all of them in production.

## Deploy via Blueprint (recommended)

`render.yaml` at the repo root defines the service, a persistent disk mounted at `/app/data`
(covers ChromaDB's collection plus the local ingest/review history JSON files — all three
default under `./data/` relative to the container's `/app` working directory), and a `/health`
health check.

1. Push this branch (with `render.yaml` and `Dockerfile`) to GitHub.
2. In the Render dashboard: **New → Blueprint**, select this repo.
3. Render reads `render.yaml` and creates the web service + disk. You'll be prompted to fill in
   the 5 env vars listed above (`sync: false` means Render asks rather than storing them in the
   file).
4. Deploy.

## Or configure manually via the dashboard

1. **New → Web Service** → connect this repo → Environment: **Docker** (uses the root
   `Dockerfile` automatically).
2. **Disks** tab → add a disk, mount path `/app/data`, size 1 GB (or more).
3. **Environment** tab → add the 5 env vars above.
4. **Settings** tab → Health Check Path: `/health`.
5. Deploy.

## Verifying the deploy (manual — do this after deploying)

1. `curl https://<your-service>.onrender.com/health` → expect `200` and
   `{"checks": [...], "all_passed": true}` (assuming GitHub/OpenAI/Chroma are all reachable).
2. Ingest a small repo against the live URL, e.g.:
   ```bash
   curl -X POST https://<your-service>.onrender.com/ingest \
     -H "Content-Type: application/json" \
     -H "X-API-Key: <API_SHARED_KEY, if set>" \
     -d '{"repo": "octocat/Hello-World"}'
   ```
3. **Restart-survival check**: in the Render dashboard, manually restart the service. Once it's
   back up, re-run the same `ingest` call (or hit `GET /reviews` if you'd reviewed a PR) and
   confirm it reflects the prior run's data (e.g. an incremental ingest reports fewer/zero newly
   indexed items instead of re-indexing everything) — this confirms the disk at `/app/data`
   actually persisted across the restart rather than resetting to an empty container filesystem.

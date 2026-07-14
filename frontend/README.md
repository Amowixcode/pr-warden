# pr-warden frontend

A React/Vite SPA for [pr-warden](../README.md)'s API: submit a review, browse review history,
and list a repo's open PRs.

## Development

```bash
npm install
cp .env.example .env   # set VITE_API_BASE_URL to your backend, e.g. http://localhost:8000
npm run dev
```

Requires the backend (`api/`) running and reachable at `VITE_API_BASE_URL`, with its
`ALLOWED_ORIGIN` env var set to this dev server's origin (`http://localhost:5173` by default)
— otherwise the browser's CORS preflight will be rejected. See the root [`DEPLOY.md`](../DEPLOY.md).

## API key

The API key field sends its value as the `X-API-Key` header on every request and is stored in
your browser's `localStorage` (`pr-warden-api-key`) so you don't have to re-enter it each visit.

**This is a demo convenience, not real security.** Anyone with access to your browser's local
storage (or a XSS on this page) can read it back out. Don't reuse a key you care about
protecting, and don't treat this as an access-control mechanism for anything sensitive.

## Build

```bash
npm run build   # type-checks then bundles to dist/
```

## Deploying to Vercel

1. Push this branch to GitHub.
2. In the Vercel dashboard: **New Project** → import this repo → set the project's **Root
   Directory** to `frontend` (Vercel auto-detects the Vite framework preset from there).
3. Set the `VITE_API_BASE_URL` environment variable to your deployed Render API's URL
   (e.g. `https://pr-warden-api.onrender.com`).
4. Deploy.
5. Once you have the Vercel URL, set it as `ALLOWED_ORIGIN` on the Render backend (see the root
   [`DEPLOY.md`](../DEPLOY.md)) and redeploy the backend — otherwise the browser will block
   every request due to CORS.
6. Verify: open the deployed Vercel URL, enter your `API_SHARED_KEY` (if the backend has one
   configured), and submit a review for a real PR — confirm the Final Verdict renders and the
   History/Open PRs tabs load real data.

# pr-warden frontend

React and Vite frontend for the [pr-warden](../README.md) API.

```bash
npm install
cp .env.example .env   # set VITE_API_BASE_URL, e.g. http://localhost:8000
npm run dev
```

The backend must be running and must list this dev server's origin
(`http://localhost:5173`) in `ALLOWED_ORIGINS`, or the browser will block the
requests. See [DEPLOY.md](../DEPLOY.md).
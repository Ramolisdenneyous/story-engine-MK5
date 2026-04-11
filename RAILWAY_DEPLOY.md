Railway deployment plan for Story Engine MK2

Services
- `backend`: Docker build from repo root using `backend/Dockerfile`
- `frontend`: Docker build from `frontend/Dockerfile`
- `postgres`: Railway PostgreSQL service

Backend variables
- `DATABASE_URL`: reference Railway Postgres connection string
- `LLM_PROVIDER=openai`
- `LLM_EXTERNAL_ENABLED=true`
- `OPENAI_API_KEY=...`
- `OPENAI_BASE_URL=https://api.openai.com/v1`
- `LLM_MODEL_CHARACTER=gpt-4o-mini`
- `LLM_MODEL_SUMMARY=gpt-4o-mini`
- `LLM_MODEL_NARRATIVE=gpt-4o`

Frontend variables
- `VITE_API_BASE=https://<your-backend-public-domain>`

Notes
- Backend now listens on Railway `PORT`.
- Frontend now builds a production bundle and serves it with `vite preview`.
- Frontend API base is injected at build time through `VITE_API_BASE`.

Release workflow
- Make code or asset changes locally.
- Validate locally with Docker when the change is non-trivial.
- Commit and push to GitHub.
- Redeploy the affected Railway service.

Which service to redeploy
- Redeploy `backend` when changing FastAPI code, database behavior, backend Docker config, or backend-served static files such as images or music in `docs/`.
- Redeploy `frontend` when changing React UI code, frontend Docker config, or frontend environment variables such as `VITE_API_BASE`.
- Redeploy both when a change touches both codepaths or when frontend references new backend-served assets.

Railway service settings
- `backend`
  - Root Directory: blank
  - Dockerfile Path: `backend/Dockerfile`
- `frontend`
  - Root Directory: `frontend`
  - Dockerfile Path: `Dockerfile`
  - Build Command: blank
  - Start Command: blank

Operational notes
- The backend root URL `/` returns `{"detail":"Not Found"}` by design. Use `/health` and `/catalog` to verify the API is reachable.
- `VITE_API_BASE` must include the full protocol, for example `https://story-engine-mk2-production.up.railway.app`
- Changing `VITE_API_BASE` requires a frontend redeploy because it is baked into the build.
- The current app creates a fresh session on page load. Refreshing the browser intentionally starts over rather than resuming a prior session.

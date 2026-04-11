# MK3 Handoff

## Project status
Story Engine MK3 is intended to be the next iteration of Story Engine MK2, not a fresh unrelated product. MK2 is currently a working deployed alpha on Railway with a local Docker workflow and a GitHub-backed release process. The app is a GM-first AI tabletop adventure tool with a React/TypeScript frontend, a FastAPI backend, and PostgreSQL persistence.

## Current deployment status
MK2 is deployed on Railway as three services:
- `frontend`
- `backend`
- `postgres`

The GitHub repo for the deployed version is:
- `https://github.com/Ramolisdenneyous/story-engine-MK2`

The release loop has been proven:
1. make changes locally
2. commit and push to GitHub
3. redeploy affected Railway service(s)
4. test on the live URL

## Current architecture
- Frontend: React + TypeScript + Vite
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL
- Local runtime: Docker Compose
- Deployment: Railway
- LLM provider: OpenAI via environment variables

High-level production flow:
- Frontend talks to Backend over public HTTPS
- Backend talks to Postgres
- Backend also serves static images/music from `docs/`

## Important product decisions carried from MK2
- The human user is the GM. The AI does not replace the GM.
- The app is structured around three tabs:
  - Tab1: setup
  - Tab2: live adventure loop
  - Tab3: story chronicle / narrative output
- The system intentionally creates a fresh session on page load. Refreshing the page starts over instead of resuming an old session. This is current intended behavior unless MK3 changes it.
- Monsters are GM-driven in MK2 and are not part of automated initiative.
- Structured memory is append-only.
- Summarization is chunked and triggered at multiples of 7 prompts.

## Major MK2 features already in place
- Valaska preset-driven setup flow
- Player/class/adventure selection
- Live GM prompting loop
- Initiative scaffolding for PCs
- Dice rolling tools for agents and GM
- Structured memory view
- Narrative draft generation
- Downloadable chapter export
- Scene image generation
- Music playback in frontend
- Splash/password gate for testing access
- Railway deployment notes and working deploy configuration

## Known implementation details that matter for MK3
- Frontend boot creates a new session automatically.
- Frontend uses `VITE_API_BASE` and this value is baked at build time. Frontend must be redeployed when that variable changes.
- Backend root route `/` is intentionally not defined. Use `/health` and `/catalog` when testing backend reachability.
- Railway frontend service must use:
  - Root Directory: `frontend`
  - Dockerfile Path: `Dockerfile`
- Railway backend service must use:
  - Root Directory: blank
  - Dockerfile Path: `backend/Dockerfile`
- Backend now listens on Railway `PORT`.
- Frontend runtime image must include `vite.config.ts` so Railway-hosted preview does not block the public hostname.
- Backend normalizes Railway-style `postgresql://` URLs into SQLAlchemy `postgresql+psycopg://` URLs.

## Recent fixes from late MK2 work
- Railway deployment was prepared and documented.
- Frontend Railway runtime was corrected to use preview properly.
- Vite preview host blocking was fixed for Railway.
- Licensed music was switched to the new `docs/music` folder and wired into the app.
- GitHub -> Railway release workflow is now working.

## Current repository docs worth reading first
In the MK2 repo, read these first before starting MK3 planning or coding:
- `RAILWAY_DEPLOY.md`
- `PROJECT_TESTING_LOG.txt`
- `story-engine-prototype-SPEC (5).txt`
- `MK2-Tab1 Ajustments (2).txt`
- `MK2-Tab2 Ajustments (2).txt`
- `MK2-Tab3 Ajustments (1).txt`
- `More MK2 Ajustments (1).txt`

## Known limitations / unresolved rough edges
- OpenAI rate limits can still cause slow paths on summarization, narrative generation, or image generation.
- Narrative generation has a fallback path, but the fallback prose is less polished than the model-generated result.
- Player tool-use reliability for dice/state updates is improved but still probabilistic.
- The app is alpha quality, not yet hardened for broad public use.
- Authentication is only a frontend splash/password gate, not real backend auth.

## Intended direction for MK3
Based on user guidance, MK3 is expected to focus on:
- improving UI polish and usability for non-dev users
- simplifying setup and offering prebuilt settings/premade characters
- improving onboarding so users can get into the Tab2 loop quickly
- adding more explicit game elements and mechanics
- iterating on the previous application, not replacing it entirely

## Likely good MK3 goals
- reduce friction in Tab1 setup
- improve persistence/resume behavior if desired
- improve reliability of state tracking and tool-use
- tighten hosted-environment stability and observability
- make the product more suitable for outside testers

## Things to avoid changing casually
- do not break the GM-first design
- do not remove append-only event/memory behavior without a clear migration plan
- do not break Railway deployment settings unless replacing them with a documented alternative
- do not assume refresh persistence exists unless intentionally added

## First recommended tasks for a new MK3 chat
1. Confirm the MK3 repo path and whether it was cloned from MK2.
2. Read the handoff and deployment docs.
3. Define the specific MK3 goals before coding.
4. Decide whether MK3 should preserve the current fresh-session-on-refresh behavior.
5. Decide whether hosting remains on Railway.

## Recommended opening prompt for the next chat
Use something like:

"Read `MK3_HANDOFF.md` first. MK3 is an iteration of MK2. The repo path is `<path>`. Railway deployment exists already in MK2. Start by reviewing the handoff, identifying what carries forward unchanged, and then help plan the first MK3 implementation steps."

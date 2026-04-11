# MK4 Bootstrap

This folder is the MK4 starting point, copied from the MK3 codebase.

## Baseline
- Source project copied from: `story-engine-MK3`
- MK3 baseline commit: `91a61c4`
- Commit message: `Add opposition audit logging and remove splash gate`

This means MK4 starts from the latest tested MK3 state, including:
- deterministic combat resolution via backend `resolve_action`
- Opposition agent + spawn/dismiss system
- long rest button
- prompt modularization
- TTS support
- password splash gate removed
- added backend Opposition audit logging

## Project Identity
Story Engine is a GM-first AI tabletop adventure simulator set in Valaska.

The core experience is:
1. prepare a party and mission
2. run the live adventure as GM
3. let AI-controlled party members respond in character using real backend mechanics

MK1 -> MK3 focused on making the system function.
MK4 is intended to focus primarily on the UI and product presentation.

## Current Architecture

### Frontend
- React + TypeScript + Vite
- Main files:
  - `frontend/src/App.tsx`
  - `frontend/src/styles.css`
  - `frontend/src/api.ts`

### Backend
- FastAPI + SQLAlchemy
- Main files:
  - `backend/app/main.py`
  - `backend/app/services.py`
  - `backend/app/llm.py`
  - `backend/app/game_data.py`
  - `backend/app/models.py`
  - `backend/app/schemas.py`

### Prompt System
Prompts were modularized in MK3.

Important prompt locations:
- `backend/app/prompts/system/player_base.md`
- `backend/app/prompts/system/opposition_agent.md`
- `backend/app/prompts/system/world_lock_agent.md`
- `backend/app/prompts/system/summary_agent.md`
- `backend/app/prompts/system/narrative_base.md`
- `backend/app/prompts/system/image_agent.md`
- `backend/app/prompts/players/`
- `backend/app/prompts/narrative_lenses/`
- loader: `backend/app/prompt_loader.py`

## Current MK3 Feature State Carried Into MK4

### Tab 1
- adventure selection
- player selection
- class assignment
- Start Chapter flow

### Tab 2
- Adventure Log
- GM Prompting
- music controls
- TTS playback + autoplay
- travel via interactive adventure maps
- encounter spawning / dismissal
- initiative system
- player status and combat state
- long rest

### Combat
- deterministic backend action resolution
- real audit trail for rolls and HP changes
- Opposition uses backend mechanics instead of invented numbers
- player agents and Opposition call backend tools through native tool calling

### Tab 3
- still present, but likely to be deprecated or repurposed in MK4

## Known Product Direction For MK4
From planning discussions, MK4 is expected to focus on:
- UI simplification
- higher clarity
- better information density without clutter
- more engaging interaction design
- possible animation system later
- likely de-emphasis or removal of older writing-oriented Wrap Up goals

Planned phases discussed:
1. UI simplification
2. interaction clarity
3. layout + density optimization
4. low-risk visual feedback
5. unified location cell/map system
6. animation system
7. onboarding / splash / tutorial
8. mobile adaptation

## Important Constraints

### 1. Do not accidentally remove structured memory
Even if Tab 3 is deprecated, structured memory is still important to system behavior and lives in the backend flow.

### 2. Animation should not own gameplay
If MK4 adds avatar/video animation, gameplay must still function without it.
Animation should enhance state, not become the state system.

### 3. Mobile is not the identity by default
There was a mobile optimization experiment late in MK3 and it was rolled back.
The current carried-forward UI is desktop-first.
Future mobile work should be deliberate, not accidental.

### 4. Current scene image generation is a weak feature
There was active discussion about removing or de-emphasizing generated scene images because they were expensive, slow, and brittle.
Do not assume image generation is part of MK4 unless explicitly kept.

### 5. Heavier UI changes should not break combat
Combat stability was hard won in MK3. UI overhaul work must preserve backend mechanics.

## Operational Notes

### Local Docker
- frontend: `http://localhost:5175`
- backend: `http://localhost:8002`
- postgres: local docker service

### Railway
MK3 was successfully deployed to Railway from GitHub.
The project structure is already compatible with:
- backend service using `backend/Dockerfile`
- frontend service using `frontend/Dockerfile`
- Railway Postgres

### Backend Logging
Opposition audit logging was added in the last MK3 pass to help trace:
- monster HP before/after updates
- failed target lookups
- dismissal decisions

## Suggested First Step For The Next Chat
Before implementing MK4 changes:
1. read `MK4 Planning (2).txt`
2. inspect current `frontend/src/App.tsx` and `frontend/src/styles.css`
3. identify what UI can be simplified without touching backend mechanics
4. preserve all working combat/tool systems unless explicitly changing them

## Practical Summary
MK4 should be treated as:
- same core product
- same backend mechanics
- same Valaska adventure engine
- new UX layer and interface identity

The safest approach is to build MK4 as a UI-first refactor on top of a working gameplay core, not as a full system rewrite.

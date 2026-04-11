# Story Engine Prototype

Story Engine Prototype is a web-based AI storytelling framework where the human user acts as the Game Master and AI-controlled character agents inhabit the party. The system is built around structured turns, aggressive memory summarization, and end-of-chapter narrative generation.

This repository currently contains a working Phase 1 MVP based on the original product specification in `story-engine-prototype-SPEC (5).txt`.

## Core Idea

The project is intentionally not an AI GM.

The design goal is:
- the user directs the scene as GM
- AI agents respond as defined characters
- session history is compressed into structured memory
- the accumulated chapter can be rewritten into a narrative draft

## Current MVP Scope

The implemented MVP includes:
- Tab1 chapter setup
  - world and tone input
  - chapter/scene input
  - 1 to 7 configurable agents
  - per-agent identity text
- Tab2 GM prompting loop
  - one user prompt per turn
  - one selected agent response per prompt
  - transcript rendering from structured events
  - automatic summarization at prompt multiples of 7
  - manual `End Chapter` flow
- Tab3 output workflow
  - append-only structured memory view
  - narrative-agent definition input
  - chapter draft generation
  - downloaded `.txt` export of the generated chapter
- Backend state machine and persistence
- Docker-based local development environment
- Minimal unit test coverage for key MVP behaviors

## Screenshots

### Tab1 Setup

![Tab1 setup](docs/images/Tab1-setup.png)

Defines the world, current chapter, and the active character roster for the session.

### Tab2 Play Loop

![Tab2 play loop](docs/images/Tab2-play-loop.png)

Shows the GM-driven interaction loop, color-coded agent transcript, and active prompt panel.

### Tab3 Memory and Draft Output

![Tab3 memory and draft](docs/images/Tab3-memory-draft.png)

Displays append-only structured memory, narrative-agent controls, and generated chapter output.

## Architecture

This project follows the monorepo structure defined in the spec:
- `frontend/` - React + TypeScript UI
- `backend/` - FastAPI API, state machine, orchestration, persistence
- `shared/` - shared type definitions

Technical stack:
- Frontend: React, TypeScript, Vite
- Backend: Python, FastAPI, SQLAlchemy
- Database: Postgres
- Local runtime: Docker Compose
- LLM integration: provider abstraction with OpenAI support and mock fallback

## Repository Layout

```text
story-engine/
  backend/
    app/
    migrations/
    tests/
  docs/
    images/
  frontend/
    src/
  shared/
  docker-compose.yml
  story-engine-prototype-SPEC (5).txt
  PROJECT_TESTING_LOG.txt
```

## Local Setup

### Prerequisites

- Docker Desktop
- WSL2 enabled on Windows if using Linux containers

### Environment

Create a local `.env` file in the project root.

Minimum configuration:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Optional overrides:

```env
LLM_PROVIDER=openai
LLM_EXTERNAL_ENABLED=true
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL_CHARACTER=gpt-4o-mini
LLM_MODEL_SUMMARY=gpt-4o-mini
LLM_MODEL_NARRATIVE=gpt-4o
```

A template is included in `.env.example`.

### Start the Project

From the project root:

```powershell
cd "C:\Users\Raymond\Desktop\Test File\hello.js\story-engine"
& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' compose up --build -d
```

### Access the App

- Frontend: `http://localhost:5174`
- Backend health check: `http://localhost:8001/health`

## How to Test the MVP

1. Open the frontend.
2. In Tab1:
   - define the world and tone
   - define the chapter scene
   - choose the number of agents
   - add agent names and identity text
3. Lock Tab1 and move to Tab2.
4. Prompt agents turn by turn.
5. Verify transcript growth and summarization behavior.
6. Use `End Chapter`.
7. In Tab3:
   - review structured memory
   - define the narrative agent
   - build the narrative draft
   - download the resulting chapter text file

## Testing

Backend unit tests currently verify:
- prompt index increment behavior
- summarization trigger at multiples of 7
- append-only memory blocks
- session state transitions

Run tests from `backend/`:

```powershell
python -m pytest -q
```

## Notable Work Completed

The current repository includes work completed after the original spec review:
- full MVP scaffold from spec
- Docker bring-up and validation
- frontend runtime fixes
- OpenAI provider integration via environment variables
- UI fixes discovered during live testing
- character prompt plumbing improvements so agents receive:
  - agent identity
  - structured memory
  - recent transcript context
  - current user prompt

A more detailed implementation and testing trail is recorded in `PROJECT_TESTING_LOG.txt`.

## Current Limitations

This is still a prototype MVP.

Known constraints include:
- quality tuning is still in progress
- narrative drift and character fidelity need continued iteration
- no multi-user auth
- no collaborative editing
- no advanced exports beyond text download
- no Phase 2 features from the original roadmap

## License

This project is distributed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.

See:
- `story-engine-license.md`
- https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode

Attribution reference:

`story-engine-prototype by Ramolis Systems (https://github.com/Ramolisdenneyous), licensed under CC BY-NC-SA 4.0`

## Specification Reference

The original source specification used for this prototype is included here:
- `story-engine-prototype-SPEC (5).txt`


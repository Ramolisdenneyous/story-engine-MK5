# Story Engine MK5

Story Engine MK5 is the current development branch of the Story Engine project: a local-first, Game-Master-led adventure engine where AI agents play the party and opposition inside a backend-authoritative rules loop.

MK5 starts from the stable MK4 live baseline, but the direction has shifted from prototype flow-building into a fuller adventure system. The goal is no longer just "can agents respond in character?" The goal is "can a human GM run a structured adventure with AI party members while the backend keeps the rules honest?"

## Project Direction

Story Engine is not an AI GM.

The human user remains the Game Master. The AI agents are characters inside the world: party members, opposition, and support agents that respond to the GM's prompts. The backend owns mechanical truth so the model's prose cannot quietly rewrite HP, inventory, quest progress, combat state, or travel rules.

MK5 is focused on:

- six structured Valaska adventures with location-based encounters
- party agents with assigned classes, inventories, HP, MP, and class features
- backend-resolved attacks, spells, skill checks, hazards, traps, loot, and quest progress
- combat initiative with locked turn order and frontend turn gating
- adventure-log feedback that explains important mechanical events to the user
- backend context notices that tell player agents what encounter state they are in
- a local Docker test loop that mirrors the live MK5 GitHub branch

## Current MK5 Systems

### Adventure Content

MK5 now contains six playable adventures:

- To Follow the King's Way
- Nightmares of the Thawed
- The Dead Remember
- Collecting What's Owed
- Memories of the Witch King
- Blood at Midnight

Adventure locations can define combat encounters, traps, hazards, stealth infiltration checks, search loot, quest-gated travel, and mission-completion conditions.

### Backend-Authoritative Mechanics

The backend resolves mechanical actions through tool calls such as `resolve_action`.

The intended turn flow is:

1. The GM prompts an agent.
2. The agent calls a backend tool for uncertain mechanics.
3. The backend rolls dice, resolves results, applies state changes, and emits system events.
4. The frontend displays those events and animations.
5. The agent narrates only what the backend result supports.

This protects the game from model-invented hits, misses, healing, loot, or quest progress.

### Combat

Combat supports:

- initiative order for player agents and opposition
- turn-locked prompting during combat
- automatic encounter starts on travel
- skipped turns for downed agents
- restored turn participation after healing
- combat-end cleanup and return to free agent selection
- flee attempts
- long rest outside active combat
- frontend attack and death animations driven by backend events

Recent MK5 work hardened named multiattack features so malformed model calls still resolve correctly:

- Fighter `CLEAVE` resolves up to two attacks against different living targets.
- Ranger `DOUBLE_NOCK` resolves two attacks against the same target.
- The backend canonicalizes malformed feature calls such as `action_type: "CLEAVE"` or `action_type: "DOUBLE_NOCK"`.
- Multiattack animations are grouped so leftover attack events do not replay or lock the UI.

### Classes And Resources

Player agents can be assigned classes with class-specific mechanics:

- Fighter: Cleave
- Barbarian: Rage
- Rogue: Skill Expert and Sneak Attack
- Ranger: Double Nock
- Paladin: Smite and Lay on Hands
- Cleric: Bless and Cure Wounds
- Druid: Thunderwave and Cure Wounds
- Wizard: Firebolt, Burning Hands, Magic Missile, and scroll support

MK5 also includes MP, spell-restoration potions, healing potions, stacked inventory items, and backend-protected item consumption.

### Hazards, Traps, And Skill Checks

Hazards and traps are now part of the adventure loop instead of being separate UI-only interactions.

The Adventure Log gives the user a narrated description of what is happening. Backend context gives the player agents explicit mechanical instructions, such as which skill check is needed and what failure means. The user prompts agents to engage with hazards naturally rather than pressing a special challenge button.

### Quest Progress And Loot

Mission objectives now update from backend-resolved events rather than narration. Combat kills, search rewards, gold drops, boss defeats, and location-specific items are tracked through backend state and Adventure Log entries.

Loot and inventory changes are also fed back into backend context so agents can reason about what they actually have.

## UI Direction

MK5 keeps the three-tab structure:

### Tab 1: Preparation

- choose an adventure
- select four player agents
- assign classes
- start and lock the chapter

### Tab 2: Adventure

The main play surface includes:

- Adventure Log
- world map, adventure map, and encounter location view
- party and opposition cards
- GM prompting panel
- combat turn gating
- travel, search, flee, long rest, and end-chapter controls
- backend-driven attack overlays and monster death animations

### Tab 3: Feedback

The feedback tab remains part of the playtest loop for capturing observations while the system is evolving.

## Repository Layout

```text
story-engine-MK5/
  backend/
    app/
    migrations/
    tests/
  docs/
    images/
    music/
  frontend/
    src/
  shared/
  tools/
  docker-compose.yml
  MK5_SYSTEMS_PLAN.md
  README.md
```

## Technical Stack

- Frontend: React, TypeScript, Vite
- Backend: Python, FastAPI, SQLAlchemy
- Database: Postgres
- Local runtime: Docker Compose
- LLM integration: provider abstraction with OpenAI support and mock fallback

## Local Docker Setup

### Prerequisites

- Docker Desktop
- Windows with Linux containers enabled
- an OpenAI API key for live agent testing

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

### Start MK5 Locally

From the project root:

```powershell
cd "C:\Users\Raymond\Desktop\Test File\hello.js\story-engine-MK5"
docker compose up --build -d
```

### Local URLs

- Frontend: `http://localhost:5175`
- Backend: `http://localhost:8002`
- Backend health check: `http://localhost:8002/health`
- Postgres: `localhost:5434`

### Useful Checks

Run backend tests locally:

```powershell
$env:PYTHONPATH='backend'
python -m pytest backend/tests/test_mvp.py -q
```

Run the frontend build:

```powershell
cd frontend
npm run build
```

Run focused backend tests inside Docker:

```powershell
docker exec -e PYTHONPATH=/app story-engine-mk5-backend-1 pytest tests/test_mvp.py -q
```

## Current Testing Priorities

Current MK5 testing is focused on:

- full playthroughs of all six adventures
- class feature reliability
- backend tool-call guardrails
- combat turn order and downed-agent recovery
- objective completion from backend events
- hazard/trap feedback clarity
- local/live parity after GitHub pushes
- reducing latency without removing necessary gameplay context

## Known Constraints

MK5 is still moving quickly.

Known constraints include:

- model behavior still needs backend guardrails
- UI feedback for hazards and puzzles can be clearer
- response latency is mostly driven by LLM generation time
- context size has grown because the game state is richer
- some assets and old planning files remain from earlier MK versions

## License

This project is distributed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.

See:

- `story-engine-license.md`
- https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode

Attribution reference:

`story-engine-prototype by Ramolis Systems (https://github.com/Ramolisdenneyous), licensed under CC BY-NC-SA 4.0`

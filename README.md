# Story Engine MK5

Story Engine MK5 is the next local-first evolution of the Story Engine project. It starts from the stable MK4 live version and preserves the same GM-first gameplay core while creating room for the next round of product, UI, and engine improvements.

The project is still centered on one core idea: the human user is the Game Master, and AI-controlled agents inhabit the party and respond inside a structured game loop. MK5 continues the work of making that loop feel clearer, faster, and more dependable in actual play.

## What MK5 Is Trying To Do

MK5 is not an AI GM.

The design goal is:
- the user directs the world as Game Master
- AI agents respond as party members or as the opposition
- game state is stored and resolved in the backend, not inferred from narrative prose
- the frontend presents the active mission, location, party state, combat state, and transcript in a compact play surface
- the chapter can still be summarized and rewritten into a narrative draft at the end

## Current MK5 Focus

This repository now reflects the current MK5 direction, starting from the MK4 guided-onboarding baseline.

The inherited MK4 baseline pushed the project toward:
- backend-authoritative combat resolution
- two-phase prompt flow for faster combat feel
- improved local docker hosting for MK4 only
- a reorganized frontend with split adventure components instead of one oversized `App.tsx`
- mission preview and location-image support across the UI
- card-based party and opposition presentation in the Encounter Location view
- frontend combat overlays and death animation support driven by backend events
- stronger guardrails around invalid tool calls and stale combat targets
- opposition batch-action stability improvements (deduped action and event handling)
- completed Phase 7 mission-objective integration across all six adventures

## Major Architecture Changes

### Backend-Authoritative Resolution

One of the biggest architectural changes in MK4 is that combat and healing state are now resolved from backend tool results, not scraped or reconstructed from the model's visible narration.

The intended order is:
1. GM sends a prompt
2. backend calls the LLM
3. LLM uses tool calls such as `resolve_action`
4. backend rolls dice, resolves hit or miss, applies HP changes, updates combat state, and emits system events
5. frontend can begin animation from those backend events
6. the LLM produces visible narration after tool resolution

This keeps the game state authoritative and reduces a whole class of sync bugs that come from trusting prose.

### Two-Phase Prompt Flow

Prompts now have two possible modes:

- simple single-phase mode:
  - used when no gameplay tool call is needed
  - the prompt returns normally with no animation trigger
- two-phase mode:
  - used when the LLM makes a gameplay tool call
  - the backend immediately returns updated `system_events`
  - the frontend starts combat animation right away
  - the final narration is persisted afterward through a continuation pass

This change was made specifically to reduce the lag between action resolution and visible combat motion in the UI.

### Safer Tool Retry Behavior

The backend now does more than simply accept tool arguments at face value.

It currently:
- forces player actions to originate from the actually prompted player
- canonicalizes fuzzy or slightly malformed target references where possible
- rejects invalid actor or target references before applying state
- returns viable live targets to the LLM when a target is invalid
- allows the model to retry the tool call instead of narrating a broken action
- rejects an entire invalid batch rather than partially applying half a turn
- canonicalizes opposition attack abilities to real monster profiles to prevent false no-roll misses
- deduplicates repeated action/state emissions before event persistence

This is especially important for multi-monster combat and stale target references.

### Frontend Sync Hardening

Combat overlays are now protected against replay loops and stale backlog replays:

- only the newest unresolved attack prompt group is animated
- stale unresolved attack events are marked handled without replaying history
- duplicate attack entries in the same prompt group are filtered before render
- post-animation refresh remains backend-truth-first

TTS playback also includes timeout and abort recovery behavior so rapid prompting cannot wedge autoplay in a loading state.

## Current UI Structure

MK4 uses a three-tab flow:

### Tab 1: Preparation

Used to set up the adventure before play begins.

Current preparation flow includes:
- Valaska preset boot data
- adventure selection
- four-player selection
- class assignment
- chapter start and tab lock

### Tab 2: Adventure

This is the main play surface.

The current layout is built around:
- `AdventureLog`
  - transcript display
  - TTS playback controls
- `LocationCell`
  - world map
  - adventure map
  - encounter location image
  - party card stack
  - opposition card display
  - combat overlay animations
- `GmPromptPanel`
  - active agent selection
  - GM prompt input
  - enter-to-send support
  - encounter trigger and flee controls
  - long rest and end chapter controls

### Tab 3: Feedback

The feedback tab is used to collect testing notes and preserve observations from playthroughs. It remains part of the longer-term loop for refining the system.

## Frontend Notes

The frontend has been actively refactored to reduce weight in `App.tsx` and make the interface easier to evolve.

Important recent UI improvements include:
- dedicated adventure subcomponents split out from `App.tsx`
- improved loading state when entering the chapter
- deferred work so Tab 2 appears faster
- location image support for the encounter location cell
- preview art support for mission popovers
- player cards displayed as a visible stack in initiative order
- opposition cards shown consistently in the location cell
- automatic shift to Encounter Location after travel and when encounters begin
- attack, hit, shake, and death overlay animations
- death fade-out for defeated monsters

The current animation strategy is intentionally more stateless than earlier attempts:
- the real cards render from live backend state
- animations use temporary overlay cards
- after animation completes, the UI refreshes from backend truth

## Combat and State Model

Combat now revolves around event-driven state updates.

Important event categories include:
- transcript events
- dice roll events
- `attack_resolved`
- HP change events
- monster death events
- opposition spawn and dismissal events
- turn end events

This event trail allows the frontend to:
- animate attacks from backend-resolved outcomes
- refresh against the latest session state after animation settles
- keep the real UI anchored to persisted state instead of transient frontend guesses
- avoid replaying old encounters after travel, spawn, or dismissal transitions

## Local Assets

MK4 now includes a larger image set than earlier versions.

Current local assets include:
- location artwork for encounter locations
- six adventure preview images
- player portraits
- monster images
- world and adventure maps
- local music tracks

Many of the location and preview images have been converted to lighter `.webp` assets to keep the UI responsive while still preserving decent display quality.

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
  docker-compose.yml
  MK4_BOOTSTRAP.md
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

### Start MK4 Locally

From the project root:

```powershell
cd "C:\Users\Raymond\Desktop\Test File\hello.js\story-engine-MK4"
docker compose up --build -d
```

### Local URLs

- Frontend: `http://localhost:5175`
- Backend: `http://localhost:8002`
- Backend health check: `http://localhost:8002/health`
- Postgres: `localhost:5434`

## Development Notes

Some important practical notes for current MK4 work:

- local testing is done through Docker
- only the active MK4 stack should be hosted locally during work
- the frontend and backend are being tuned together based on repeated live playtests
- combat, healing, target resolution, and UI sync are currently higher priority than adding larger feature scope such as RAG

## Current Testing Priorities

Recent testing has focused heavily on:
- single-monster and multi-monster combat
- initiative and turn rotation
- healing and knockout recovery
- monster death and dismissal timing
- animation timing and responsiveness
- frontend/backend sync after attack sequences
- invalid target handling in tool calls

Phase 7 validation now includes full quest-line playthrough checks for:
- To Follow the King's Way
- Nightmares of the Thawed
- The Dead Remember
- Collecting What's Owed
- Memories of the Witch King
- Blood at Midnight

## Known Constraints

MK4 is still an active development branch of the project.

Known constraints include:
- animation polish is still iterative
- model behavior still needs guardrails for tool accuracy
- the README reflects the current architecture, but the project is still evolving quickly
- RAG, vector search, and larger rules-database support are not part of the current MK4 scope

## License

This project is distributed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.

See:
- `story-engine-license.md`
- https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode

Attribution reference:

`story-engine-prototype by Ramolis Systems (https://github.com/Ramolisdenneyous), licensed under CC BY-NC-SA 4.0`

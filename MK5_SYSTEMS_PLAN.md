# Story Engine MK5 Systems Plan

MK5 shifts Story Engine from a GM training and adventure-assist tool toward a more structured, user-facing adventure game system. The human remains the Game Master, and AI agents remain player characters or opposition voices, but more of the game loop should be prebuilt, backend-resolved, and visible to the user as clear game state.

## Core Direction

- Preserve the GM-first identity: MK5 is still not an AI GM.
- Keep backend authority over mechanics, resources, combat, traps, hazards, loot, and objectives.
- Treat LLM narration as a response to resolved state, not the source of truth for resolved state.
- Build systems incrementally so MK4's stable combat and onboarding loop remain usable throughout MK5.

## Non-Goals

- Full D&D 5e rules implementation.
- Freeform LLM-generated encounter generation.
- Unlimited autonomous agent chaining.
- Multiplayer, accounts, or long-term campaign persistence.
- A finished external song-generation pipeline.
- Replacing the existing Valaska adventure structure.

## Phase 1: Encounter Data Model

Goal: define structured encounter content for each adventure location.

Initial encounter types:
- `combat`: preselected monster group and optional loot.
- `trap`: surprise backend resolution, usually party-wide.
- `hazard`: visible blocker with progress state and player choices.
- `story`: non-combat narrative/location beat.
- `none`: safe or objective-only location.

Recommended first implementation:
- Add encounter definitions in backend data next to adventure/location data.
- Add session-level encounter state as JSON, matching the existing `combat_state`, `opposition_state`, and `mission_objective_state` pattern.
- Have travel load or trigger the location encounter.
- Keep manual Trigger Encounter available as a fallback during early MK5.

Acceptance criteria:
- Every location can report a predefined encounter type.
- Encounter content is deterministic backend data, not LLM-generated.
- Travel can trigger the proper encounter.
- Encounter state appears in session detail for frontend display.

## Phase 2: Combat Initiative Lock

Goal: make combat turn order behave like a game system.

Target rules:
- Combat rolls initiative on encounter start.
- Initiative order is locked while combat is active.
- Only the active combatant can take a mechanical combat action.
- Each combatant gets one action per round.
- Opposition acts once per round as its own slot.
- Round advances after all living combatants in the order have acted.

Likely state addition:

```text
CombatState {
  in_combat: boolean
  round: number
  turn_index: number
  initiative_order: CombatantId[]
  initiative_values: Record<CombatantId, number>
  acted_this_round: Record<CombatantId, boolean>
}
```

Concern:
This will change the feel of GM prompting. The UI must make the active combatant obvious and explain why other agents are unavailable. An explicit GM override can come later if needed.

## Phase 3: Traps and Hazards

Goal: add non-combat pressure that is mechanically resolved by the backend.

Trap model:
- Backend rolls perception for all active party members.
- Failed perception checks become affected targets.
- Affected targets each roll the trap's required check.
- Damage/status is rolled and applied independently per affected target.
- Result is logged as a backend event.
- Opposition can narrate the resolved trap, but trap mechanics must complete even if narration fails.

Hazard model:
- Hazards start as `blocking`.
- Hazards may track party-global progress, per-player progress, or both.
- Leaving and returning before clear resets temporary progress unless the hazard definition says otherwise.
- Clearing a hazard unlocks forward travel or marks a route as passable.

Important distinction:
- Steep Cliffside and Swimming likely need per-player progress.
- Puzzle Door likely needs party/global progress and escalating failure damage.
- Stealth Infiltration and Staged Distraction may trigger a combat encounter on failure.

## Phase 4: MP Resource System

Goal: limit spellcasting without implementing full spell slots.

Initial MP classes:
- Cleric: 3 MP
- Druid: 3 MP
- Wizard: 3 MP

Rules:
- MP is tracked per party member.
- MP cannot exceed max MP.
- MP-consuming actions fail gracefully when insufficient.
- MP changes create backend events.
- MP potions restore MP.

Frontend:
- Show MP only for classes that have MP.
- Add MP to hover/status areas before adding deeper item use.

## Phase 5: Class Features and Spells

Goal: make classes mechanically distinct.

Suggested first pass:
- Fighter: Second Wind, limited heal.
- Barbarian: Rage, temporary combat modifier.
- Rogue: Skill Expert, advantage on skill checks.
- Ranger: Tracker, advantage on exploration/search checks.
- Paladin: Smite, bonus damage with limited use.
- Cleric: MP-based Cure Wounds.
- Druid: Nature's Aid or hazard/nature advantage.
- Wizard: expanded MP spells and scroll use.

Implementation rule:
All features should resolve through backend action logic. Agents may choose features, but they should not invent feature results.

## Phase 6: Loot, Search, and Usable Items

Goal: reward exploration and create resource recovery.

Initial item types:
- HP Potion
- MP Potion
- Fireball Scroll
- Gold
- Quest Item

Search model:
- Locations can define searchable items.
- Search items have a DC, skill, found-once behavior, and reward.
- Search checks should use backend rolls.

Usable item model:
- Inventory needs a stricter item registry.
- Agents can request item use, but backend validates ownership, target, class restrictions, and effect.
- Existing inventory tooling should be extended carefully so agents cannot create or consume impossible items.

## Phase 7: Limited AI-to-AI Prompting

Goal: allow controlled character interaction without autonomous spirals.

Rules:
- One agent may ask one other agent a question.
- The target agent responds once.
- Chain ends automatically.
- Max chain depth is two messages total.
- User can interrupt or override.
- In combat, AI-to-AI interaction should either count as the active character's action or be explicitly marked as free dialogue.

Risk:
This should come after initiative and action accounting exist, because agent-to-agent dialogue can otherwise blur turn ownership.

## Phase 8: Music System Pass

Goal: make music reflect game state.

Cue types:
- default
- exploration
- combat
- danger
- victory
- defeat
- celebration

Rules:
- Music can be requested on by default, but browser autoplay limits still apply.
- If autoplay is blocked, show a simple Enable Music control.
- Music cues should not drown out TTS.
- Encounter definitions may include `music_cue`.

## Phase 9: Ending Celebration Prototype

Goal: create a testbed for adventure-completion song drafts.

Flow:
- Backend confirms adventure objective success.
- Frontend opens celebration state/panel.
- Backend gathers structured session summary.
- Stronger model generates a tavern-ballad style song draft.
- Draft appears in the app.
- External song generation remains optional future work.

Suggested output:

```text
CelebrationSongDraft {
  title: string
  style_prompt: string
  lyrics: string
}
```

## First Vertical Slice

Before filling all 36 encounters, prove the system with a small slice:

1. Add encounter definitions for one adventure.
2. Auto-trigger one combat encounter on travel.
3. Auto-resolve one trap encounter on travel.
4. Log structured encounter results in Adventure Log.
5. Keep current manual encounter controls available.
6. Confirm the existing MK4 prompt/combat loop still works.

This gives MK5 a stable skeleton before content volume and resource systems increase complexity.

# Changelog

All notable changes to Story Engine MK5 are documented in this file.

## [Unreleased] - 2026-05-04

### Changed
- Started MK5 from the stable MK4 guided-onboarding baseline.
- Updated local project identity and Git remote for the new MK5 repository.

## [Unreleased] - 2026-04-24

### Added
- Phase 7 mission-objective support for all six Valaska adventures, including objective progress/completion events and return-to-Moosehearth flow.
- Encounter-location image pipeline updates, including endgame Antlers' Rest Inn artwork integration.
- Frontend Docker build context guard via `frontend/.dockerignore` to avoid local `node_modules` build-context failures.

### Changed
- Combat flow reinforced as backend-authoritative: tool calls resolve hit/miss/damage/healing first, then frontend animation, then narration continuation.
- Prompt handling now supports two-phase resolution for tool-driven turns to reduce perceived combat latency.
- Adventure UI sync strategy hardened around backend event truth after animation settlement.

### Fixed
- Prevented animation replay loops caused by stale/unbounded attack-event reprocessing.
- Added de-duplication safeguards for repeated attack and state-change emissions in a single turn.
- Improved opposition action reliability by canonicalizing monster attack abilities to valid backend profiles.
- Improved TTS autoplay recovery with timeout/abort handling to avoid stuck loading states.
- Corrected combat target payload consistency for player HP fields used by backend tool resolution.

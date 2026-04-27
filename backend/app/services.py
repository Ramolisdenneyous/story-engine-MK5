import copy
import difflib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from secrets import randbelow
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .game_data import (
    ADVENTURES,
    CLASSES,
    DEFAULT_IMAGE_FILE,
    MONSTERS,
    MONSTER_CATALOG,
    PLAYER_NARRATIVE_LENSES,
    PLAYERS,
    VALASKA_PRESET_ID,
    VALASKA_SYSTEM_PROMPT,
)
from .llm import GenerationResult, get_provider, log_artifact, tts_voice_alias_for_player
from .models import Event, EventKind, EventRole, FeedbackSubmission, MemoryBlock, MemoryBlockType, NarrativeDraft, Session as SessionModel, SessionState, Tab1Inputs

DICE_RE = re.compile(r"^\s*(\d{1,3})\s*d\s*(4|6|8|10|12|20)\s*([+-]\s*\d+)?\s*$", re.IGNORECASE)
VALID_DICE_SIDES = {4, 6, 8, 10, 12, 20}
SLOT_COLORS = {1: "red", 2: "orange", 3: "yellow", 4: "green"}
ASSET_DIR = Path("/app/docs/images")
OPPOSITION_AGENT_SLOT = 12
OPPOSITION_INITIATIVE_ID = "opp:12"
OPPOSITION_DISPLAY_NAME = "Opposition"
OPPOSITION_CLEANUP_DELAY_SECONDS = 5
MONSTER_INSTANCE_LABELS = ["Monster-One", "Monster-Two", "Monster-Three", "Monster-Four"]
logger = logging.getLogger(__name__)
RETURN_TO_MOOSEHEARTH_TEXT = "The objective is complete. Return to Moosehearth to report your success."
MISSION_OBJECTIVE_CONFIG = {
    "icebane-castle": {
        "title": "Recover the Witch-King Crown",
        "public_goal": "Recover the Witch-King Crown from the ruins of Icebane Castle.",
        "progress_label": "Witch-King Crown not yet recovered.",
        "secret": "The crown drops only when the last monster in The Fractured Throne Room dies.",
        "target_location_id": "loc-6",
        "target_location_name": "The Fractured Throne Room",
        "item_name": "Witch-King Crown",
    },
    "east-marsh-raid": {
        "title": "Kill the Warchief",
        "public_goal": "Find and defeat the East Marsh war leader.",
        "progress_label": "The war leader is still at large.",
        "secret": "Traveling to The War Leader's Tent triggers the warchief encounter.",
        "target_location_id": "loc-5",
        "target_location_name": "The War Leader's Tent",
        "required_monsters": ["Bandit Captain", "Giant Boar"],
    },
    "telas-wagons": {
        "title": "Escort the Wagon Train to Glockstead",
        "public_goal": "Escort the supply wagons along the King's Way to Glockstead.",
        "progress_label": "Wagons are waiting to depart.",
        "travel_sequence": ["loc-1", "loc-2", "loc-3", "loc-4", "loc-5", "loc-6"],
    },
    "old-people-barrow": {
        "title": "Recover the Lost Relic",
        "public_goal": "Recover the lost relic from the Old-People's Barrow.",
        "progress_label": "The lost relic has not been recovered.",
        "secret": "A successful search check in The Burial Vault reveals The Befouled Urn.",
        "target_location_id": "loc-5",
        "target_location_name": "The Burial Vault",
        "item_name": "The Befouled Urn",
    },
    "endless-glacier-undead": {
        "title": "Kill 10 Undead",
        "public_goal": "Destroy ten undead threats along the Endless Glacier.",
        "progress_label": "Undead defeated: 0/10.",
        "target_kills": 10,
    },
    "collecting-taxes": {
        "title": "Collect 400gp",
        "public_goal": "Collect 400 gold pieces along the King's Road.",
        "progress_label": "Gold collected: 0/400gp.",
        "target_gold": 400,
    },
}
OPENING_TRANSCRIPT = (
    "Welcome to Valaska, the bitter north at the very edge of the known world. Endless forests of black pine stretch beneath "
    "iron-gray skies, and the wind carries the bite of distant glaciers.\n\n"
    "Your party of four adventurers has gathered in the frontier town of Moosehearth, a stubborn settlement of timber lodges "
    "and smoking chimneys clinging to survival against the cold. Tonight you sit inside the Antlers' Rest Inn, a warm refuge "
    "of firelight, rough laughter, and the smell of spiced ale.\n\n"
    "Just moments ago, one of you returned from the town square carrying a freshly pulled notice from the jobs board. The "
    "parchment is still stiff from the cold, promising coin, danger, and opportunity somewhere out in the frozen wilds.\n\n"
    "Adventure calls."
)
LONG_REST_TRANSCRIPT = (
    "[SYSTEM EVENT: LONG REST - 8 HOURS]\n"
    "Time passes, and the party manages 8 hours of rest.\n"
    "The immediate danger has faded, and the party is given a rare chance to recover. "
    "The hours stretch on. Armor is loosened. Weapons are cleaned. Breath slows. Thoughts settle.\n"
    "By the end of the rest:\n"
    "Your body has recovered\n"
    "Your strength has returned\n"
    "You are ready to continue"
)

logger = logging.getLogger("uvicorn.error")


def _empty_combat_state() -> dict:
    return {
        "in_combat": False,
        "round": 1,
        "turn_index": 0,
        "initiative_order": [],
        "initiative_values": {},
    }


def _empty_opposition_state() -> dict:
    return {
        "active": False,
        "group_id": "",
        "initiative_id": OPPOSITION_INITIATIVE_ID,
        "monster_type": "",
        "monster_stats": {},
        "instances": [],
        "cleanup_after": "",
    }


def _empty_mission_objective_state(adventure_id: str = "") -> dict:
    config = MISSION_OBJECTIVE_CONFIG.get(adventure_id, {})
    state = {
        "adventure_id": adventure_id,
        "title": config.get("title", ""),
        "public_goal": config.get("public_goal", ""),
        "progress_label": config.get("progress_label", ""),
        "status": "inactive" if not adventure_id else "in_progress",
        "complete": False,
        "return_available": False,
        "updates": [],
    }
    if adventure_id == "telas-wagons":
        state.update({"current_step": 0, "allowed_location_ids": ["loc-1"], "visited_location_ids": []})
    elif adventure_id == "endless-glacier-undead":
        state.update({"undead_kills": 0, "target_kills": 10})
    elif adventure_id == "collecting-taxes":
        state.update({"gold_collected": 0, "target_gold": 400})
    elif adventure_id == "icebane-castle":
        state.update({"item_awarded": False, "item_name": config.get("item_name", "")})
    elif adventure_id == "old-people-barrow":
        state.update({"item_awarded": False, "item_name": config.get("item_name", "")})
    elif adventure_id == "east-marsh-raid":
        state.update({"boss_encounter_spawned": False, "boss_encounter_group_id": "", "boss_defeated": False})
    return state


def _mission_state(session: SessionModel) -> dict:
    tab1_adventure_id = ""
    current_state = copy.deepcopy(session.mission_objective_state or {})
    adventure_id = str(current_state.get("adventure_id", "") or tab1_adventure_id)
    if not current_state or adventure_id not in MISSION_OBJECTIVE_CONFIG:
        return current_state
    return current_state


def _mission_context_for_agents(session: SessionModel) -> dict:
    state = copy.deepcopy(session.mission_objective_state or {})
    adventure_id = str(state.get("adventure_id", "") or "")
    config = MISSION_OBJECTIVE_CONFIG.get(adventure_id, {})
    if not config:
        return {}
    context = {
        "title": state.get("title", config.get("title", "")),
        "goal": state.get("public_goal", config.get("public_goal", "")),
        "progress": state.get("progress_label", config.get("progress_label", "")),
        "complete": bool(state.get("complete", False)),
        "current_location": session.current_location_name or "",
    }
    if adventure_id == "telas-wagons":
        context["allowed_next_locations"] = state.get("allowed_location_ids", [])
    return context


def _set_mission_complete(db: Session, session: SessionModel, prompt_index: int, state: dict, note: str, payload: dict | None = None) -> dict:
    if state.get("complete"):
        return state
    state["complete"] = True
    state["status"] = "complete"
    state["return_available"] = True
    state["progress_label"] = note
    state.setdefault("updates", []).append({"prompt_index": prompt_index, "text": note})
    session.mission_objective_state = state
    _append_system_event(
        db,
        session.session_id,
        prompt_index,
        EventKind.OBJECTIVE_UPDATED,
        f"Objective complete: {note}",
        {"objective_complete": True, **(payload or {})},
    )
    return state


def _update_mission_progress(db: Session, session: SessionModel, prompt_index: int, note: str, payload: dict | None = None) -> None:
    state = copy.deepcopy(session.mission_objective_state or {})
    if not state:
        return
    state["progress_label"] = note
    state.setdefault("updates", []).append({"prompt_index": prompt_index, "text": note})
    session.mission_objective_state = state
    _append_system_event(
        db,
        session.session_id,
        prompt_index,
        EventKind.OBJECTIVE_UPDATED,
        f"Objective progress: {note}",
        payload or {},
    )


def _monster_template(monster_type: str) -> dict:
    monster = MONSTER_CATALOG.get(monster_type)
    if not monster:
        raise ValueError("Unknown monster_type")
    return copy.deepcopy(monster)


def _living_opposition_instances(opposition_state: dict | None) -> list[dict]:
    state = opposition_state or _empty_opposition_state()
    return [instance for instance in state.get("instances", []) if not instance.get("is_dead")]


def _arm_opposition_cleanup(opposition_state: dict) -> dict:
    state = copy.deepcopy(opposition_state or _empty_opposition_state())
    if not state.get("cleanup_after"):
        state["cleanup_after"] = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
        )
    return state


def _maybe_finalize_opposition_cleanup(db: Session, session: SessionModel) -> bool:
    opposition_state = copy.deepcopy(session.opposition_state or _empty_opposition_state())
    cleanup_after = str(opposition_state.get("cleanup_after", "") or "")
    if not opposition_state.get("active") or not cleanup_after:
        return False
    try:
        cleanup_started = datetime.fromisoformat(cleanup_after)
    except ValueError:
        return False
    if cleanup_started.tzinfo is None:
        cleanup_started = cleanup_started.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - cleanup_started).total_seconds()
    if elapsed < OPPOSITION_CLEANUP_DELAY_SECONDS:
        return False
    _dismiss_opposition_state(db, session, session.prompt_index, reason="all_dead")
    return True


def _ensure_nonblocking_opposition_state(db: Session, session: SessionModel) -> None:
    opposition_state = copy.deepcopy(session.opposition_state or _empty_opposition_state())
    if not opposition_state.get("active"):
        return
    if _living_opposition_instances(opposition_state):
        return
    if _maybe_finalize_opposition_cleanup(db, session):
        db.flush()
        return
    # If the UI has already reached the point where the user is trying to
    # continue play, do not let a dead-only cleanup hold block long rest or a
    # new encounter. Finalize immediately and clear combat state.
    _dismiss_opposition_state(db, session, session.prompt_index, reason="cleanup_forced")
    db.flush()


def _default_generated_image() -> dict:
    return {
        "image_url": asset_url(DEFAULT_IMAGE_FILE),
        "prompt_text": "",
        "last_actor_slot": None,
    }


def asset_url(filename: str) -> str:
    return f"/assets/{filename}"


def serialize_adventure(adventure_id: str | None) -> dict | None:
    if not adventure_id:
        return None
    adventure = ADVENTURES.get(adventure_id)
    if not adventure:
        return None
    return {
        **adventure,
        "map_image_url": asset_url(adventure["map_image_file"]),
    }


def serialize_adventure_summary(adventure_id: str) -> dict:
    adventure = ADVENTURES[adventure_id]
    return {
        "adventure_id": adventure["adventure_id"],
        "title": adventure["title"],
        "description": adventure["description"],
    }


def serialize_monster_reference(monster_id: str) -> dict:
    monster = MONSTERS[monster_id]
    return {
        **monster,
        "image_url": asset_url(monster["image_file"]),
    }


def serialize_player_summary(player_id: str) -> dict:
    player = PLAYERS[player_id]
    return {
        "player_id": player["player_id"],
        "name": player["name"],
        "archetype": player["archetype"],
        "gender": player["gender"],
        "race": player["race"],
        "keywords": player["keywords"],
        "image_url": asset_url(f"Player-{player['player_id']}.jpg"),
    }


def serialize_player_detail(player_id: str) -> dict:
    player = PLAYERS[player_id]
    return {
        **serialize_player_summary(player_id),
        "irl_job": player["irl_job"],
        "keywords": player["keywords"],
        "display_text": player["display_text"],
    }


def serialize_class_summary(class_id: str) -> dict:
    class_data = CLASSES[class_id]
    return {
        "class_id": class_data["class_id"],
        "name": class_data["name"],
        "role": class_data["role"],
        "armor_class": class_data["armor_class"],
        "hp_max": class_data["hp_max"],
    }


def create_feedback_submission(db: Session, session_id: str, feedback_text: str) -> FeedbackSubmission:
    session = get_session_or_404(db, session_id)
    tab1 = get_tab1_or_create(db, session_id)
    party = derive_party_state(db, session_id)
    adventure = serialize_adventure(tab1.adventure_id)
    now = datetime.utcnow()
    submission = FeedbackSubmission(
        session_id=session.session_id,
        adventure_id=tab1.adventure_id or "",
        adventure_title=adventure["title"] if adventure else "",
        selected_party=[
            {
                "slot": slot,
                "player_id": player_id,
                "player_name": PLAYERS[player_id]["name"],
                "class_id": class_id,
                "hp_current": int((party.get(str(slot), {}) or {}).get("hp_current", CLASSES[class_id]["hp_max"])),
                "hp_max": CLASSES[class_id]["hp_max"],
            }
            for slot in range(1, 5)
            for player_id, class_id in [(_player_for_slot(tab1, slot), _class_assignment_for_slot(tab1, slot))]
            if player_id and class_id
        ],
        prompt_count=session.prompt_index,
        session_duration_seconds=max(0, int((now - session.created_at).total_seconds())),
        feedback_text=feedback_text.strip(),
        created_at=now,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def _portrait_filename(player_id: str, class_id: str | None = None) -> str:
    if not class_id:
        return f"Player-{player_id}.jpg"
    candidates = [
        f"{player_id}-{class_id}.jpg",
        f"{player_id}-{class_id.lower()}.jpg",
        f"{player_id}-{class_id.capitalize()}.jpg",
    ]
    for candidate in candidates:
        if (ASSET_DIR / candidate).exists():
            return candidate
    return f"Player-{player_id}.jpg"


def _default_name(slot: int) -> str:
    color = SLOT_COLORS.get(slot)
    return f"Agent {color.title() if color else slot}"


def _class_assignment_for_slot(tab1: Tab1Inputs, slot: int) -> str:
    value = tab1.class_assignments.get(str(slot), tab1.class_assignments.get(slot, ""))
    return value if value in CLASSES else ""


def _player_for_slot(tab1: Tab1Inputs, slot: int) -> str:
    if slot - 1 < len(tab1.selected_player_ids):
        return tab1.selected_player_ids[slot - 1]
    return ""


def _ability_modifiers(scores: dict[str, int]) -> dict[str, int]:
    return {key: (value - 10) // 2 for key, value in scores.items()}


def _party_member(slot: int, player_id: str, class_id: str, state: dict | None = None) -> dict:
    player = PLAYERS[player_id]
    class_data = CLASSES[class_id]
    member_state = state or {}
    return {
        "slot": slot,
        "player_id": player_id,
        "player_name": player["name"],
        "class_id": class_id,
        "portrait_url": asset_url(_portrait_filename(player_id, class_id)),
        "base_portrait_url": asset_url(_portrait_filename(player_id)),
        "race": player["race"],
        "archetype": player["archetype"],
        "keywords": player["keywords"],
        "armor_class": class_data["armor_class"],
        "hp_max": class_data["hp_max"],
        "hp_current": member_state.get("hp_current", class_data["hp_max"]),
        "status_effects": member_state.get("status_effects", []),
        "inventory": member_state.get("inventory", list(class_data["inventory"])),
        "initiative": member_state.get("initiative"),
    }


def create_session(db: Session) -> SessionModel:
    session = SessionModel(
        state=SessionState.DRAFT_TAB1,
        prompt_index=0,
        last_summarized_prompt_index=0,
        selected_agent_slots=[1, 2, 3, 4],
        agent_names={str(slot): _default_name(slot) for slot in range(1, 5)},
        combat_state=_empty_combat_state(),
        opposition_state=_empty_opposition_state(),
        generated_image=_default_generated_image(),
    )
    db.add(session)
    db.flush()
    db.add(
        Tab1Inputs(
            session_id=session.session_id,
            world_text=VALASKA_SYSTEM_PROMPT,
            chapter_text="",
            agent_identity_text_by_slot={},
            preset_id=VALASKA_PRESET_ID,
            adventure_id="",
            selected_player_ids=[],
            class_assignments={},
        )
    )
    db.commit()
    db.refresh(session)
    return session


def get_session_or_404(db: Session, session_id: str) -> SessionModel:
    session = db.get(SessionModel, session_id)
    if not session:
        raise ValueError("Session not found")
    return session


def get_tab1_or_create(db: Session, session_id: str) -> Tab1Inputs:
    tab1 = db.get(Tab1Inputs, session_id)
    if not tab1:
        tab1 = Tab1Inputs(
            session_id=session_id,
            world_text=VALASKA_SYSTEM_PROMPT,
            chapter_text="",
            agent_identity_text_by_slot={},
            preset_id=VALASKA_PRESET_ID,
            adventure_id="",
            selected_player_ids=[],
            class_assignments={},
        )
        db.add(tab1)
        db.flush()
    return tab1


def save_tab1(db: Session, session_id: str, payload: dict) -> tuple[SessionModel, Tab1Inputs]:
    session = get_session_or_404(db, session_id)
    if session.tab1_locked:
        raise ValueError("Tab1 is locked")
    if session.state != SessionState.DRAFT_TAB1:
        raise ValueError("Tab1 edits allowed only in DRAFT_TAB1")

    tab1 = get_tab1_or_create(db, session_id)
    tab1.preset_id = VALASKA_PRESET_ID
    adventure_id = payload.get("adventure_id", "")
    if adventure_id and adventure_id not in ADVENTURES:
        raise ValueError("Unknown adventure_id")
    tab1.adventure_id = adventure_id
    tab1.chapter_text = adventure_id

    selected_player_ids = payload.get("selected_player_ids", [])
    if len(selected_player_ids) != len(set(selected_player_ids)):
        raise ValueError("Players must be unique")
    if len(selected_player_ids) > 4:
        raise ValueError("Exactly four players maximum")
    for player_id in selected_player_ids:
        if player_id not in PLAYERS:
            raise ValueError("Unknown player_id")
    tab1.selected_player_ids = selected_player_ids[:4]

    raw_assignments = payload.get("class_assignments", {})
    class_assignments: dict[str, str] = {}
    for slot in range(1, min(len(tab1.selected_player_ids), 4) + 1):
        class_id = raw_assignments.get(str(slot), raw_assignments.get(slot, ""))
        if class_id:
            if class_id not in CLASSES:
                raise ValueError("Unknown class_id")
            class_assignments[str(slot)] = class_id
    tab1.class_assignments = class_assignments

    session.selected_agent_slots = [1, 2, 3, 4]
    session.agent_names = {str(slot): _default_name(slot) for slot in range(1, 5)}
    for slot in range(1, len(tab1.selected_player_ids) + 1):
        session.agent_names[str(slot)] = PLAYERS[tab1.selected_player_ids[slot - 1]]["name"]

    db.commit()
    db.refresh(session)
    db.refresh(tab1)
    return session, tab1


def _validate_start_ready(tab1: Tab1Inputs) -> None:
    if not tab1.adventure_id:
        raise ValueError("adventure_id is required")
    if len(tab1.selected_player_ids) != 4:
        raise ValueError("Exactly 4 players must be selected")
    for slot in range(1, 5):
        if _class_assignment_for_slot(tab1, slot) not in CLASSES:
            raise ValueError("All 4 classes must be selected")


def _current_memory_blocks(db: Session, session_id: str) -> list[MemoryBlock]:
    return db.execute(
        select(MemoryBlock).where(MemoryBlock.session_id == session_id).order_by(MemoryBlock.created_at.asc())
    ).scalars().all()


def _recent_events(db: Session, session: SessionModel) -> list[Event]:
    from_prompt = max(1, session.prompt_index - 7)
    to_prompt = max(0, session.prompt_index - 1)
    if to_prompt < from_prompt:
        return []
    return db.execute(
        select(Event)
        .where(
            Event.session_id == session.session_id,
            Event.prompt_index >= from_prompt,
            Event.prompt_index <= to_prompt,
            Event.kind == EventKind.TRANSCRIPT,
        )
        .order_by(Event.prompt_index.asc(), Event.created_at.asc())
    ).scalars().all()


def _build_character_payload(db: Session, session: SessionModel, agent_slot: int, user_text: str) -> dict:
    tab1 = get_tab1_or_create(db, session.session_id)
    player_id = _player_for_slot(tab1, agent_slot)
    class_id = _class_assignment_for_slot(tab1, agent_slot)
    player = PLAYERS[player_id]
    class_data = CLASSES[class_id]
    memory_blocks = _current_memory_blocks(db, session.session_id)
    recent_events = _recent_events(db, session)
    return {
        "agent_identity": {
            "slot": agent_slot,
            "name": player["name"],
            "player_prompt": player["display_text"],
            "archetype": player["archetype"],
            "gender": player["gender"],
            "race": player["race"],
        },
        "class_sheet": {
            **class_data,
            "proficiency_bonus": 2,
            "ability_modifiers": _ability_modifiers(class_data["ability_scores"]),
        },
        "structured_memory": [
            {
                "type": block.type.value,
                "from_prompt_index": block.from_prompt_index,
                "to_prompt_index": block.to_prompt_index,
                "json_payload": block.json_payload,
            }
            for block in memory_blocks
        ],
        "recent_context": [
            {
                "prompt_index": event.prompt_index,
                "role": event.role.value,
                "agent_slot": event.agent_slot,
                "agent_name": session.agent_names.get(str(event.agent_slot), None) if event.agent_slot else None,
                "text": event.text,
            }
            for event in recent_events
        ],
        "current_location": session.current_location_text,
        "mission_objective": _mission_context_for_agents(session),
        "opposition_state": copy.deepcopy(session.opposition_state or _empty_opposition_state()),
        "mechanical_resolution_hint": _build_player_mechanical_hint(db, session, agent_slot, class_data, user_text),
        "user_prompt": user_text,
    }


def _build_party_combat_state(db: Session, session: SessionModel) -> list[dict]:
    tab1 = get_tab1_or_create(db, session.session_id)
    party_state = derive_party_state(db, session.session_id)
    party = []
    for slot in range(1, 5):
        player_id = _player_for_slot(tab1, slot)
        class_id = _class_assignment_for_slot(tab1, slot)
        if not player_id or not class_id:
            continue
        class_data = CLASSES[class_id]
        state = party_state.get(str(slot), {})
        party.append(
            {
                "target_id": _player_actor_id(slot),
                "target_type": "player",
                "slot": slot,
                "player_id": player_id,
                "player_name": PLAYERS[player_id]["name"],
                "class_id": class_id,
                "armor_class": class_data["armor_class"],
                "hp_current": state.get("hp_current", class_data["hp_max"]),
                # Keep both keys so downstream tool-resolution code can read a
                # consistent `current_hp` field for players and monsters.
                "current_hp": state.get("hp_current", class_data["hp_max"]),
                "hp_max": class_data["hp_max"],
                "status_effects": state.get("status_effects", []),
                "initiative": session.combat_state.get("initiative_values", {}).get(f"pc:{slot}"),
            }
            )
    return party


def _build_visible_monster_targets(session: SessionModel) -> list[dict]:
    opposition_state = copy.deepcopy(session.opposition_state or _empty_opposition_state())
    if not opposition_state.get("active"):
        return []
    monster_stats = opposition_state.get("monster_stats", {})
    targets: list[dict] = []
    for instance in opposition_state.get("instances", []):
        if instance.get("is_dead"):
            continue
        instance_type = instance.get("monster_type") or opposition_state.get("monster_type", "")
        instance_stats = instance.get("monster_stats") or monster_stats
        targets.append(
            {
                "target_id": instance.get("monster_id", ""),
                "target_type": "monster",
                "name": instance.get("display_name", "Monster"),
                "monster_type": instance_type,
                "armor_class": instance_stats.get("ac"),
                "current_hp": instance.get("current_hp", 0),
                "hp_max": instance.get("hp_max", 0),
                "status_effects": instance.get("status_effects", []),
            }
        )
    return targets


def _extract_requested_check_type(user_text: str) -> str:
    lowered = (user_text or "").lower()
    match = re.search(r"\b([a-z]+(?:\s+[a-z]+){0,2})\s+check\b", lowered)
    if match:
        return match.group(1).strip()
    if "saving throw" in lowered:
        return "saving throw"
    if re.search(r"\bsave\b", lowered):
        return "save"
    if "initiative" in lowered:
        return "initiative"
    return ""


def _build_player_mechanical_hint(db: Session, session: SessionModel, agent_slot: int, class_data: dict, user_text: str) -> dict:
    visible_targets = _build_visible_monster_targets(session)
    requested_check_type = _extract_requested_check_type(user_text)
    injured_ally_targets = _build_injured_ally_targets(db, session)
    return {
        "tool_first_required": True,
        "actor_id": _player_actor_id(agent_slot),
        "requested_check_type": requested_check_type,
        "required_tool_for_check": "resolve_action" if requested_check_type else "",
        "in_combat": bool(session.combat_state.get("in_combat")) and bool(visible_targets),
        "ally_targets": _build_ally_targets(db, session),
        "injured_allies_present": bool(injured_ally_targets),
        "injured_ally_targets": injured_ally_targets,
        "visible_monster_targets": visible_targets,
        "available_actions": _build_player_action_catalog(class_data),
        "required_action_tool": "resolve_action",
        "default_action_sequence": [
            "choose_target",
            "choose_ability",
            "call_resolve_action",
            "read_resolution",
            "then_narrate",
        ],
        "rules": {
            "all_mechanics_resolve_in_backend": True,
            "llm_must_not_roll_or_apply_hp": True,
            "never_narrate_roll_before_tool": True,
        },
    }


def _extract_monster_damage_formula(monster_stats: dict) -> str:
    attack_text = str(monster_stats.get("attack_text", ""))
    match = re.search(r"(\d+d\d+(?:\+\d+)?)", attack_text.replace(" ", ""))
    return match.group(1) if match else ""


def _build_opposition_mechanical_hint(db: Session, session: SessionModel) -> dict:
    opposition_state = copy.deepcopy(session.opposition_state or _empty_opposition_state())
    monster_stats = opposition_state.get("monster_stats", {})
    attack_bonus = int(monster_stats.get("attack_bonus", 0) or 0)
    attack_formula = f"1d20+{attack_bonus}" if attack_bonus >= 0 else f"1d20{attack_bonus}"
    damage_formula = _extract_monster_damage_formula(monster_stats)
    return {
        "tool_first_required": True,
        "living_monster_count": len(_living_opposition_instances(opposition_state)),
        "party_targets": _build_party_combat_state(db, session),
        "living_monster_actors": _build_monster_actor_catalog(session),
        "required_action_tool": "resolve_action",
        "default_action_sequence": [
            "choose_living_monster",
            "choose_party_target",
            "call_resolve_action",
            "read_resolution",
            "then_narrate",
        ],
        "rules": {
            "all_mechanics_resolve_in_backend": True,
            "llm_must_not_roll_or_apply_hp": True,
            "never_narrate_roll_before_tool": True,
        },
    }


def _normalize_ability_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", (value or "").strip().upper()).strip("_")


def _player_actor_id(slot: int) -> str:
    return f"pc:{slot}"


def _build_ally_targets(db: Session, session: SessionModel) -> list[dict]:
    return [
        {
            "target_id": _player_actor_id(member["slot"]),
            "target_type": "player",
            "slot": member["slot"],
            "name": member["player_name"],
            "armor_class": member["armor_class"],
            "current_hp": member["hp_current"],
            "hp_max": member["hp_max"],
            "status_effects": member["status_effects"],
        }
        for member in _build_party_combat_state(db, session)
    ]


def _build_injured_ally_targets(db: Session, session: SessionModel) -> list[dict]:
    injured_targets: list[dict] = []
    for member in _build_party_combat_state(db, session):
        hp_current = int(member["hp_current"])
        hp_max = int(member["hp_max"])
        if hp_current < hp_max:
            injured_targets.append(
                {
                    "target_id": _player_actor_id(member["slot"]),
                    "target_type": "player",
                    "slot": member["slot"],
                    "name": member["player_name"],
                    "current_hp": hp_current,
                    "hp_max": hp_max,
                    "below_half_hp": hp_current < (hp_max / 2),
                }
            )
    return injured_targets


def _build_player_action_catalog(class_data: dict) -> list[dict]:
    actions: list[dict] = []
    for profile in class_data.get("attack_profiles", []):
        actions.append(
            {
                "action_type": "ATTACK",
                "ability": _normalize_ability_name(profile.get("name", "")),
                "display_name": profile.get("name", ""),
                "attack_formula": profile.get("attack_formula", ""),
                "damage_formula": profile.get("damage_formula", ""),
                "damage_type": profile.get("damage_type", ""),
            }
        )
    features = set(class_data.get("features", []))
    if "Spellcasting" in features:
        if class_data.get("class_id") in {"Wizard"}:
            actions.append({"action_type": "SPELL", "ability": "MAGIC_MISSILE", "display_name": "Magic Missile"})
        if class_data.get("class_id") in {"Cleric", "Druid"}:
            actions.append({"action_type": "SPELL", "ability": "CURE_WOUNDS", "display_name": "Cure Wounds"})
    actions.extend(
        [
            {"action_type": "SKILL", "ability": "ATHLETICS", "display_name": "Athletics"},
            {"action_type": "SKILL", "ability": "PERCEPTION", "display_name": "Perception"},
            {"action_type": "SKILL", "ability": "INVESTIGATION", "display_name": "Investigation"},
            {"action_type": "SKILL", "ability": "SEARCH", "display_name": "Search"},
        ]
    )
    return actions


def _normalize_inventory_item_text(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9\s]", " ", (value or "").lower())
    return " ".join(lowered.split())


def _inventory_items_overlap(left: str, right: str) -> bool:
    left_norm = _normalize_inventory_item_text(left)
    right_norm = _normalize_inventory_item_text(right)
    if not left_norm or not right_norm:
        return False
    return (
        left_norm == right_norm
        or left_norm in right_norm
        or right_norm in left_norm
    )


def _build_monster_actor_catalog(session: SessionModel) -> list[dict]:
    opposition_state = copy.deepcopy(session.opposition_state or _empty_opposition_state())
    group_stats = opposition_state.get("monster_stats", {})
    actors: list[dict] = []
    for instance in opposition_state.get("instances", []):
        if instance.get("is_dead"):
            continue
        monster_stats = instance.get("monster_stats") or group_stats
        damage_formula = _extract_monster_damage_formula(monster_stats)
        attack_bonus = int(monster_stats.get("attack_bonus", 0) or 0)
        attack_formula = f"1d20+{attack_bonus}" if attack_bonus >= 0 else f"1d20{attack_bonus}"
        actors.append(
            {
                "actor_id": instance.get("monster_id", ""),
                "name": instance.get("display_name", "Monster"),
                "action_type": "ATTACK",
                "ability": _normalize_ability_name(monster_stats.get("monster_id", "ATTACK")),
                "attack_formula": attack_formula,
                "damage_formula": damage_formula,
                "attack_text": monster_stats.get("attack_text", ""),
            }
        )
    return actors


def _normalize_action_reference(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _register_action_reference(alias_map: dict[str, set[str]], canonical_id: str, *values: str) -> None:
    for value in values:
        normalized = _normalize_action_reference(value)
        if not normalized:
            continue
        alias_map.setdefault(normalized, set()).add(canonical_id)


def _canonicalize_action_reference(
    value: str,
    exact_map: dict[str, dict],
    alias_map: dict[str, set[str]],
) -> str:
    raw_value = str(value or "")
    if not raw_value:
        return ""
    if raw_value in exact_map:
        return raw_value

    normalized = _normalize_action_reference(raw_value)
    aliases = sorted(alias_map.get(normalized, set()))
    if len(aliases) == 1:
        return aliases[0]

    close_matches = difflib.get_close_matches(raw_value, list(exact_map.keys()), n=1, cutoff=0.85)
    if close_matches:
        return close_matches[0]

    return raw_value


def _resolve_payload_context(payload: dict) -> dict:
    player_identity = payload.get("agent_identity", {})
    class_sheet = payload.get("class_sheet", {})
    opposition_state = payload.get("opposition_state", {}) or payload.get("monster_group_state", {})
    mechanical_hint = copy.deepcopy(payload.get("mechanical_resolution_hint", {}))
    actor_map: dict[str, dict] = {}
    target_map: dict[str, dict] = {}
    actor_alias_map: dict[str, set[str]] = {}
    target_alias_map: dict[str, set[str]] = {}
    action_map: dict[tuple[str, str], dict] = {}

    for target in mechanical_hint.get("ally_targets", []):
        target_id = str(target.get("target_id", "") or "")
        target_map[target_id] = target
        _register_action_reference(target_alias_map, target_id, target_id, str(target.get("name", "") or ""))
    for target in mechanical_hint.get("visible_monster_targets", []):
        target_id = str(target.get("target_id", "") or "")
        target_map[target_id] = target
        _register_action_reference(target_alias_map, target_id, target_id, str(target.get("name", "") or ""))
    for target in mechanical_hint.get("party_targets", []):
        actor_id = str(target.get("target_id", "") or "")
        target_map[actor_id] = target
        actor_map[actor_id] = target
        _register_action_reference(target_alias_map, actor_id, actor_id, str(target.get("name", "") or ""), str(target.get("player_name", "") or ""))
        _register_action_reference(actor_alias_map, actor_id, actor_id, str(target.get("name", "") or ""), str(target.get("player_name", "") or ""))
    for actor in mechanical_hint.get("living_monster_actors", []):
        actor_id = str(actor.get("actor_id", "") or "")
        actor_map[actor_id] = actor
        action_map[(actor_id, actor.get("ability", ""))] = actor
        _register_action_reference(actor_alias_map, actor_id, actor_id, str(actor.get("name", "") or ""))

    actor_id = mechanical_hint.get("actor_id", "")
    if actor_id:
        canonical_actor_id = str(actor_id or "")
        actor_map[canonical_actor_id] = {
            "actor_id": actor_id,
            "slot": player_identity.get("slot"),
            "name": player_identity.get("name", ""),
            "class_id": class_sheet.get("class_id", ""),
            "armor_class": class_sheet.get("armor_class"),
            "hp_max": class_sheet.get("hp_max"),
        }
        _register_action_reference(actor_alias_map, canonical_actor_id, canonical_actor_id, str(player_identity.get("name", "") or ""))
    for action in mechanical_hint.get("available_actions", []):
        action_map[(actor_id, action.get("ability", ""))] = action

    return {
        "actor_map": actor_map,
        "actor_alias_map": actor_alias_map,
        "target_map": target_map,
        "target_alias_map": target_alias_map,
        "action_map": action_map,
        "mechanical_hint": mechanical_hint,
        "opposition_state": opposition_state,
        "class_sheet": class_sheet,
    }


def _list_viable_targets(context: dict) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for target_id, target in context["target_map"].items():
        targets.append(
            {
                "target_id": target_id,
                "name": str(target.get("name", "") or target.get("player_name", "") or target_id),
                "target_type": str(target.get("target_type", "") or ""),
                "current_hp": target.get("current_hp"),
                "hp_max": target.get("hp_max"),
            }
        )
    return sorted(targets, key=lambda item: (str(item["target_type"]), str(item["name"])))


def _is_living_target(target: dict[str, Any]) -> bool:
    try:
        return int(target.get("current_hp", 0) or 0) > 0
    except (TypeError, ValueError):
        return False


def resolve_actions_for_payload(payload: dict, args: dict[str, Any]) -> dict[str, Any]:
    context = _resolve_payload_context(payload)
    actions = args.get("actions", [])
    normalized_actions: list[dict[str, Any]] = []
    validation_errors: list[dict[str, Any]] = []
    viable_targets = _list_viable_targets(context)
    opposition_actor_ids = {
        str(item.get("actor_id", "") or "")
        for item in context["mechanical_hint"].get("living_monster_actors", [])
        if str(item.get("actor_id", "") or "")
    }
    is_opposition_turn = bool(opposition_actor_ids) and not str(context["mechanical_hint"].get("actor_id", "") or "")

    for index, action in enumerate(actions):
        raw_actor_id = str(action.get("actor_id", "") or "")
        action_type = str(action.get("action_type", "") or "").upper()
        ability = _normalize_ability_name(str(action.get("ability", "") or ""))
        raw_target_id = str(action.get("target_id", "") or "")
        forced_actor_id = str(context["mechanical_hint"].get("actor_id", "") or "")
        if forced_actor_id:
            actor_id = forced_actor_id
        else:
            actor_id = _canonicalize_action_reference(raw_actor_id, context["actor_map"], context["actor_alias_map"])
        target_id = _canonicalize_action_reference(raw_target_id, context["target_map"], context["target_alias_map"])
        actor = context["actor_map"].get(actor_id, {})
        target = context["target_map"].get(target_id, {})

        if not actor:
            validation_errors.append(
                {
                    "action_index": index,
                    "kind": "unknown_actor",
                    "provided_actor_id": raw_actor_id,
                    "resolved_actor_id": actor_id,
                    "reason": f"Unknown actor reference: {raw_actor_id}",
                }
            )
            continue

        if not target:
            validation_errors.append(
                {
                    "action_index": index,
                    "kind": "unknown_target",
                    "provided_target_id": raw_target_id,
                    "resolved_target_id": target_id,
                    "reason": f"Unknown target reference: {raw_target_id}",
                    "viable_targets": viable_targets,
                }
            )
            continue

        if is_opposition_turn and actor_id not in opposition_actor_ids:
            validation_errors.append(
                {
                    "action_index": index,
                    "kind": "invalid_actor_for_opposition",
                    "provided_actor_id": raw_actor_id,
                    "resolved_actor_id": actor_id,
                    "reason": "Opposition may only act with currently living monster actors.",
                }
            )
            continue

        if action_type == "ATTACK" and actor_id in opposition_actor_ids:
            # Monster actors only have one mechanical attack profile in this system.
            # Canonicalize ability to that profile so wording differences from the
            # model do not degrade into synthetic auto-misses.
            canonical_ability = _normalize_ability_name(str(actor.get("ability", "") or ""))
            if canonical_ability:
                ability = canonical_ability

        target_type = str(target.get("target_type", "") or "")
        if action_type == "ATTACK" or (action_type == "SPELL" and ability == "MAGIC_MISSILE"):
            # Keep monster-target guard to prevent replay/phantom damage against dead monsters.
            # Do not block player targets at 0 HP; opposition may intentionally target downed PCs.
            if target_type == "monster" and not _is_living_target(target):
                validation_errors.append(
                    {
                        "action_index": index,
                        "kind": "invalid_target_state",
                        "provided_target_id": raw_target_id,
                        "resolved_target_id": target_id,
                        "reason": "Attack target must be a living creature.",
                        "viable_targets": [
                            item
                            for item in viable_targets
                            if int(item.get("current_hp", 0) or 0) > 0
                        ],
                    }
                )
                continue

        if action_type == "SPELL" and ability == "CURE_WOUNDS":
            hp_current = int(target.get("current_hp", 0) or 0)
            hp_max = int(target.get("hp_max", 0) or 0)
            if target_type != "player" or hp_current >= hp_max:
                validation_errors.append(
                    {
                        "action_index": index,
                        "kind": "invalid_heal_target",
                        "provided_target_id": raw_target_id,
                        "resolved_target_id": target_id,
                        "reason": "Cure Wounds requires an injured ally target.",
                        "viable_targets": [
                            item
                            for item in viable_targets
                            if str(item.get("target_type", "") or "") == "player"
                            and int(item.get("current_hp", 0) or 0) < int(item.get("hp_max", 0) or 0)
                        ],
                    }
                )
                continue

        normalized_actions.append(
            {
                "actor_id": actor_id,
                "action_type": action_type,
                "ability": ability,
                "target_id": target_id,
            }
        )

    if is_opposition_turn and normalized_actions:
        deduped_actions: list[dict[str, Any]] = []
        seen_actor_ids: set[str] = set()
        for action in normalized_actions:
            action_actor_id = str(action.get("actor_id", "") or "")
            if not action_actor_id or action_actor_id in seen_actor_ids:
                continue
            seen_actor_ids.add(action_actor_id)
            deduped_actions.append(action)
        normalized_actions = deduped_actions

    if validation_errors:
        return {
            "results": [],
            "rolls": [],
            "state_changes": [],
            "retry_required": True,
            "errors": validation_errors,
            "viable_targets": viable_targets,
        }

    results: list[dict[str, Any]] = []
    rolls: list[dict[str, Any]] = []
    state_targets: list[dict[str, Any]] = []

    for action in normalized_actions:
        actor_id = str(action.get("actor_id", "") or "")
        action_type = str(action.get("action_type", "") or "").upper()
        ability = _normalize_ability_name(str(action.get("ability", "") or ""))
        target_id = str(action.get("target_id", "") or "")
        actor = context["actor_map"].get(actor_id, {})
        target = context["target_map"].get(target_id, {})
        actor_class_id = str(actor.get("class_id", "") or "")
        target_type = str(target.get("target_type", "") or "")
        target_slot = int(target.get("slot", 0) or 0)
        result: dict[str, Any] = {
            "actor_id": actor_id,
            "target_id": target_id,
            "action_type": action_type,
            "ability": ability,
            "hit": False,
            "attack_total": 0,
            "target_ac": target.get("armor_class"),
            "damage": 0,
            "damage_type": "",
            "healing": 0,
            "target_hp_after": target.get("current_hp"),
            "success": False,
            "reason": "",
        }

        if action_type == "ATTACK":
            attack_profile = context["action_map"].get((actor_id, ability), {})
            if not attack_profile and actor_id in opposition_actor_ids:
                attack_profile = context["actor_map"].get(actor_id, {})
            if not attack_profile:
                fallback_profile = next(
                    (profile for (profile_actor_id, _), profile in context["action_map"].items() if profile_actor_id == actor_id),
                    {},
                )
                attack_profile = fallback_profile
            attack_formula = attack_profile.get("attack_formula", "")
            damage_formula = attack_profile.get("damage_formula", "")
            damage_type = attack_profile.get("damage_type", "")
            if attack_formula and damage_formula and target_id:
                attack_roll = perform_dice_roll(attack_formula, "attack roll", actor_id)
                rolls.append(attack_roll)
                result["attack_total"] = int(attack_roll.get("total", 0) or 0)
                result["target_ac"] = int(target.get("armor_class", 0) or 0)
                result["damage_type"] = damage_type
                hit = result["attack_total"] >= result["target_ac"]
                result["hit"] = hit
                result["success"] = hit
                if hit:
                    damage_roll = perform_dice_roll(damage_formula, "damage roll", actor_id)
                    rolls.append(damage_roll)
                    damage = int(damage_roll.get("total", 0) or 0)
                    result["damage"] = damage
                    result["target_hp_after"] = max(0, int(target.get("current_hp", 0) or 0) - damage)
                    state_targets.append(
                        {
                            "target_type": target_type or "monster",
                            "target_slot": target_slot,
                            "target_id": target_id,
                            "actor_id": actor_id,
                            "ability": ability,
                            "changes": [{"kind": "damage", "amount": damage, "value": ""}],
                        }
                    )
            else:
                result["reason"] = "No valid attack profile found."
            results.append(result)
            continue

        if action_type == "SPELL":
            if ability == "MAGIC_MISSILE" and target_id:
                damage_roll = perform_dice_roll("3d4+3", "spell damage", actor_id)
                rolls.append(damage_roll)
                damage = int(damage_roll.get("total", 0) or 0)
                result.update({"hit": True, "success": True, "attack_total": 100, "damage": damage, "damage_type": "force"})
                result["target_hp_after"] = max(0, int(target.get("current_hp", 0) or 0) - damage)
                state_targets.append(
                    {
                        "target_type": target_type or "monster",
                        "target_slot": target_slot,
                        "target_id": target_id,
                        "actor_id": actor_id,
                        "ability": ability,
                        "changes": [{"kind": "damage", "amount": damage, "value": ""}],
                    }
                )
            elif ability == "CURE_WOUNDS" and target_id:
                if actor_class_id not in {"Cleric", "Druid"}:
                    result.update(
                        {
                            "success": False,
                            "reason": "Your current class is unable to cast healing magic.",
                        }
                    )
                    results.append(result)
                    continue
                heal_roll = perform_dice_roll("1d8+2", "healing roll", actor_id)
                rolls.append(heal_roll)
                healing = int(heal_roll.get("total", 0) or 0)
                result.update({"hit": True, "success": True, "attack_total": 100, "healing": healing})
                result["target_hp_after"] = min(int(target.get("hp_max", 0) or 0), int(target.get("current_hp", 0) or 0) + healing)
                state_targets.append(
                    {
                        "target_type": target_type or "player",
                        "target_slot": target_slot,
                        "target_id": target_id,
                        "actor_id": actor_id,
                        "ability": ability,
                        "changes": [{"kind": "healing", "amount": healing, "value": ""}],
                    }
                )
            results.append(result)
            continue

        if action_type == "SKILL":
            skill_roll = perform_dice_roll("1d20+2", "skill check", actor_id)
            rolls.append(skill_roll)
            total = int(skill_roll.get("total", 0) or 0)
            result.update(
                {
                    "success": total >= 13,
                    "hit": total >= 13,
                    "attack_total": total,
                    "target_ac": 13,
                    "target_hp_after": None,
                }
            )
            results.append(result)
            continue

        results.append(result)

    return {
        "results": results,
        "rolls": rolls,
        "state_changes": [{"targets": state_targets, "source": "resolve_action"}] if state_targets else [],
        "retry_required": False,
        "errors": [],
        "viable_targets": viable_targets,
    }


def _build_opposition_payload(db: Session, session: SessionModel, user_text: str) -> dict:
    memory_blocks = _current_memory_blocks(db, session.session_id)
    recent_events = _recent_events(db, session)
    opposition_state = copy.deepcopy(session.opposition_state or _empty_opposition_state())
    return {
        "monster_group_state": opposition_state,
        "party_combat_state": _build_party_combat_state(db, session),
        "mechanical_resolution_hint": _build_opposition_mechanical_hint(db, session),
        "structured_memory": [
            {
                "type": block.type.value,
                "from_prompt_index": block.from_prompt_index,
                "to_prompt_index": block.to_prompt_index,
                "json_payload": block.json_payload,
            }
            for block in memory_blocks
        ],
        "recent_context": [
            {
                "prompt_index": event.prompt_index,
                "role": event.role.value,
                "agent_slot": event.agent_slot,
                "agent_name": session.agent_names.get(str(event.agent_slot), None) if event.agent_slot else None,
                "text": event.text,
            }
            for event in recent_events
        ],
        "current_location": session.current_location_text,
        "mission_objective": _mission_context_for_agents(session),
        "user_prompt": user_text,
    }


def lock_tab1(db: Session, session_id: str) -> SessionModel:
    provider = get_provider()
    session = get_session_or_404(db, session_id)
    if session.state != SessionState.DRAFT_TAB1:
        raise ValueError("Session cannot be locked from current state")
    tab1 = get_tab1_or_create(db, session_id)
    _validate_start_ready(tab1)

    session.state = SessionState.LOCKING
    db.flush()

    party = []
    for slot in range(1, 5):
        player_id = _player_for_slot(tab1, slot)
        class_id = _class_assignment_for_slot(tab1, slot)
        party.append({"slot": slot, "player_id": player_id, "player_name": PLAYERS[player_id]["name"], "class_id": class_id})

    payload = {
        "setting": VALASKA_SYSTEM_PROMPT,
        "adventure": ADVENTURES[tab1.adventure_id],
        "players": [PLAYERS[player_id] for player_id in tab1.selected_player_ids],
        "party": party,
    }
    text = provider.generate("agent0", settings.llm_model_summary, payload)
    log_artifact(db, session_id, "agent0", settings.llm_model_summary, payload, text, provider.provider_name)
    db.add(
        MemoryBlock(
            session_id=session_id,
            type=MemoryBlockType.WORLD_CHAPTER_LOCK,
            from_prompt_index=0,
            to_prompt_index=0,
            json_payload={
                "summary": text,
                "preset_id": VALASKA_PRESET_ID,
                "world_text": VALASKA_SYSTEM_PROMPT,
                "adventure": ADVENTURES[tab1.adventure_id],
                "agent_names": session.agent_names,
                "party": party,
            },
        )
    )

    session.tab1_locked = True
    session.prompt_index = 0
    session.last_summarized_prompt_index = 0
    session.state = SessionState.ACTIVE
    session.combat_state = _empty_combat_state()
    session.opposition_state = _empty_opposition_state()
    session.current_location_id = ""
    session.current_location_name = "Antlers Rest Inn"
    session.generated_image = _default_generated_image()
    session.mission_objective_state = _empty_mission_objective_state(tab1.adventure_id)
    session.selected_narrative_player_id = tab1.selected_player_ids[0]
    db.add(
        Event(
            session_id=session_id,
            prompt_index=0,
            role=EventRole.SYSTEM,
            kind=EventKind.TRANSCRIPT,
            agent_slot=None,
            text=OPENING_TRANSCRIPT,
            json_payload={"source": "opening_transcript"},
        )
    )

    db.commit()
    db.refresh(session)
    return session


def _run_summarization(db: Session, session: SessionModel, to_prompt_index: int) -> bool:
    if to_prompt_index <= session.last_summarized_prompt_index:
        return False
    provider = get_provider()
    from_idx = session.last_summarized_prompt_index + 1
    events = db.execute(
        select(Event)
        .where(
            Event.session_id == session.session_id,
            Event.prompt_index >= from_idx,
            Event.prompt_index <= to_prompt_index,
        )
        .order_by(Event.prompt_index.asc(), Event.created_at.asc())
    ).scalars().all()
    payload = {
        "from_prompt_index": from_idx,
        "to_prompt_index": to_prompt_index,
        "events": [
            {
                "prompt_index": event.prompt_index,
                "role": event.role.value,
                "kind": event.kind.value,
                "agent_slot": event.agent_slot,
                "text": event.text,
                "json_payload": event.json_payload,
            }
            for event in events
        ],
        "combat_state": session.combat_state,
    }
    try:
        output = provider.generate("agent8", settings.llm_model_summary, payload)
        log_artifact(db, session.session_id, "agent8", settings.llm_model_summary, payload, output, provider.provider_name)
        db.add(
            MemoryBlock(
                session_id=session.session_id,
                type=MemoryBlockType.TURN_DELTA,
                from_prompt_index=from_idx,
                to_prompt_index=to_prompt_index,
                json_payload={"summary": output, "event_count": len(events), "combat_state": copy.deepcopy(session.combat_state)},
            )
        )
        session.last_summarized_prompt_index = to_prompt_index
        return True
    except Exception as exc:
        fallback_summary = (
            f"Fallback summary for prompts {from_idx}-{to_prompt_index}. "
            f"Captured {len(events)} events while remote summarization was unavailable ({type(exc).__name__})."
        )
        db.add(
            MemoryBlock(
                session_id=session.session_id,
                type=MemoryBlockType.TURN_DELTA,
                from_prompt_index=from_idx,
                to_prompt_index=to_prompt_index,
                json_payload={
                    "summary": fallback_summary,
                    "event_count": len(events),
                    "combat_state": copy.deepcopy(session.combat_state),
                    "summary_source": "fallback",
                },
            )
        )
        session.last_summarized_prompt_index = to_prompt_index
        return True


def _append_system_event(db: Session, session_id: str, prompt_index: int, kind: EventKind, text: str, payload: dict) -> None:
    db.add(
        Event(
            session_id=session_id,
            prompt_index=prompt_index,
            role=EventRole.SYSTEM,
            kind=kind,
            agent_slot=None,
            text=text,
            json_payload=payload,
        )
    )


def _slot_from_actor_id(actor_id: str) -> int:
    if actor_id.startswith("pc:"):
        try:
            return int(actor_id.replace("pc:", ""))
        except ValueError:
            return 0
    return 0


def _apply_action_objective_updates(db: Session, session: SessionModel, agent_slot: int, prompt_index: int, result: dict[str, Any]) -> None:
    state = copy.deepcopy(session.mission_objective_state or {})
    adventure_id = state.get("adventure_id", "")
    if not adventure_id or state.get("complete"):
        return
    action_type = str(result.get("action_type", "") or "").upper()
    ability = str(result.get("ability", "") or "").upper()
    success = bool(result.get("success", False))
    actor_id = str(result.get("actor_id", "") or "")
    actor_slot = _slot_from_actor_id(actor_id) or agent_slot

    if adventure_id == "old-people-barrow" and action_type == "SKILL" and success:
        config = MISSION_OBJECTIVE_CONFIG[adventure_id]
        if session.current_location_id != config["target_location_id"] or state.get("item_awarded"):
            return
        item_name = config["item_name"]
        _append_state_change(
            db,
            session,
            prompt_index,
            target_type="player",
            target_slot=actor_slot,
            kind="inventory_add",
            value=item_name,
            source="mission_objective",
            actor_id=actor_id,
        )
        state["item_awarded"] = True
        state["awarded_to_slot"] = actor_slot
        _set_mission_complete(
            db,
            session,
            prompt_index,
            state,
            f"{item_name} recovered from The Burial Vault.",
            {"adventure_id": adventure_id, "item": item_name, "awarded_to_slot": actor_slot, "ability": ability},
        )


def _apply_monster_death_objective_updates(
    db: Session,
    session: SessionModel,
    prompt_index: int,
    opposition_state: dict,
    killed_instance: dict,
    living_instances: list[dict],
    actor_id: str = "",
) -> None:
    state = copy.deepcopy(session.mission_objective_state or {})
    adventure_id = state.get("adventure_id", "")
    if not adventure_id or state.get("complete"):
        return
    actor_slot = _slot_from_actor_id(actor_id)

    if adventure_id == "icebane-castle":
        config = MISSION_OBJECTIVE_CONFIG[adventure_id]
        if session.current_location_id != config["target_location_id"] or living_instances or state.get("item_awarded"):
            return
        item_name = config["item_name"]
        if actor_slot:
            _append_state_change(
                db,
                session,
                prompt_index,
                target_type="player",
                target_slot=actor_slot,
                kind="inventory_add",
                value=item_name,
                source="mission_objective",
                actor_id=actor_id,
            )
        state["item_awarded"] = True
        state["awarded_to_slot"] = actor_slot
        _set_mission_complete(
            db,
            session,
            prompt_index,
            state,
            f"{item_name} recovered from The Fractured Throne Room.",
            {"adventure_id": adventure_id, "item": item_name, "awarded_to_slot": actor_slot},
        )
        return

    if adventure_id == "east-marsh-raid":
        if not state.get("boss_encounter_spawned"):
            return
        if opposition_state.get("group_id") != state.get("boss_encounter_group_id"):
            return
        if living_instances:
            return
        state["boss_defeated"] = True
        _set_mission_complete(
            db,
            session,
            prompt_index,
            state,
            "The war leader and his beast have been defeated.",
            {"adventure_id": adventure_id, "group_id": opposition_state.get("group_id", "")},
        )
        return

    if adventure_id == "endless-glacier-undead":
        target_kills = int(state.get("target_kills", MISSION_OBJECTIVE_CONFIG[adventure_id]["target_kills"]))
        current = int(state.get("undead_kills", 0)) + 1
        state["undead_kills"] = current
        if current >= target_kills:
            _set_mission_complete(
                db,
                session,
                prompt_index,
                state,
                f"Undead defeated: {target_kills}/{target_kills}.",
                {"adventure_id": adventure_id, "undead_kills": current, "target_kills": target_kills},
            )
            return
        note = f"Undead defeated: {current}/{target_kills}."
        state["progress_label"] = note
        state.setdefault("updates", []).append({"prompt_index": prompt_index, "text": note})
        session.mission_objective_state = state
        _append_system_event(
            db,
            session.session_id,
            prompt_index,
            EventKind.OBJECTIVE_UPDATED,
            f"Objective progress: {note}",
            {"adventure_id": adventure_id, "undead_kills": current, "target_kills": target_kills},
        )
        return

    if adventure_id == "collecting-taxes" and not living_instances:
        target_gold = int(state.get("target_gold", MISSION_OBJECTIVE_CONFIG[adventure_id]["target_gold"]))
        gold_awarded = 50 + randbelow(76)
        current_gold = int(state.get("gold_collected", 0)) + gold_awarded
        state["gold_collected"] = current_gold
        if actor_slot:
            _append_state_change(
                db,
                session,
                prompt_index,
                target_type="player",
                target_slot=actor_slot,
                kind="inventory_add",
                value=f"{gold_awarded}gp",
                source="mission_objective",
                actor_id=actor_id,
            )
        if current_gold >= target_gold:
            _set_mission_complete(
                db,
                session,
                prompt_index,
                state,
                f"Gold collected: {current_gold}/{target_gold}gp.",
                {"adventure_id": adventure_id, "gold_awarded": gold_awarded, "gold_collected": current_gold, "target_gold": target_gold},
            )
            return
        note = f"Gold collected: {current_gold}/{target_gold}gp. {gold_awarded}gp recovered from the encounter."
        state["progress_label"] = note
        state.setdefault("updates", []).append({"prompt_index": prompt_index, "text": note})
        session.mission_objective_state = state
        _append_system_event(
            db,
            session.session_id,
            prompt_index,
            EventKind.OBJECTIVE_UPDATED,
            f"Objective progress: {note}",
            {"adventure_id": adventure_id, "gold_awarded": gold_awarded, "gold_collected": current_gold, "target_gold": target_gold},
        )


def _apply_generation_result(db: Session, session: SessionModel, agent_slot: int, prompt_index: int, generation: GenerationResult) -> None:
    for result in generation.pending_roll_results:
        label = str(result.get("label", "") or result.get("formula", "Dice Roll"))
        total = int(result.get("total", 0) or 0)
        db.add(
            Event(
                session_id=session.session_id,
                prompt_index=prompt_index,
                role=EventRole.SYSTEM,
                kind=EventKind.DICE_ROLL,
                agent_slot=agent_slot,
                text=f"{label}: {total}",
                json_payload=result,
            )
        )

    seen_attack_keys: set[tuple[str, str, str, str, bool, int, int, int]] = set()
    for result in generation.pending_action_results:
        action_type = str(result.get("action_type", "")).upper()
        ability = str(result.get("ability", "")).upper()
        attack_key = (
            str(result.get("actor_id", "") or ""),
            str(result.get("target_id", "") or ""),
            action_type,
            ability,
            bool(result.get("hit", False)),
            int(result.get("damage", 0) or 0),
            int(result.get("healing", 0) or 0),
            int(result.get("target_hp_after", 0) or 0),
        )
        if attack_key in seen_attack_keys:
            continue
        seen_attack_keys.add(attack_key)
        _apply_action_objective_updates(db, session, agent_slot, prompt_index, result)
        if action_type != "ATTACK" and not (action_type == "SPELL" and ability == "MAGIC_MISSILE"):
            continue
        db.add(
            Event(
                session_id=session.session_id,
                prompt_index=prompt_index,
                role=EventRole.SYSTEM,
                kind=EventKind.ATTACK_RESOLVED,
                agent_slot=agent_slot,
                text="Attack resolved.",
                json_payload={
                    "actor_id": result.get("actor_id", ""),
                    "target_id": result.get("target_id", ""),
                    "hit": bool(result.get("hit", False)),
                    "damage": int(result.get("damage", 0) or 0),
                    "target_hp_after": int(result.get("target_hp_after", 0) or 0),
                },
            )
        )

    seen_state_change_keys: set[tuple[str, str, int, str, int, str]] = set()
    for payload in generation.pending_state_changes:
        source = payload.get("source", "tool")
        for target in payload.get("targets", []):
            target_type = str(target.get("target_type", "player") or "player")
            for change in target.get("changes", []):
                kind = str(change.get("kind", "") or "")
                amount = int(change.get("amount", 0) or 0)
                value = str(change.get("value", "") or "")
                state_key = (
                    target_type,
                    str(target.get("target_id", "") or ""),
                    int(target.get("target_slot", 0) or 0),
                    kind,
                    amount,
                    value,
                )
                if state_key in seen_state_change_keys:
                    continue
                seen_state_change_keys.add(state_key)
                if target_type == "monster":
                    _append_state_change(
                        db,
                        session,
                        prompt_index,
                        target_type="monster",
                        target_id=str(target.get("target_id", "") or ""),
                        kind=kind,
                        amount=amount,
                        value=value,
                        source=source,
                        actor_id=str(target.get("actor_id", "") or ""),
                    )
                else:
                    _append_state_change(
                        db,
                        session,
                        prompt_index,
                        target_type="player",
                        target_slot=int(target.get("target_slot", agent_slot) or agent_slot),
                        kind=kind,
                        amount=amount,
                        value=value,
                        source=source,
                        actor_id=str(target.get("actor_id", "") or ""),
                    )


def _append_state_change(
    db: Session,
    session: SessionModel,
    prompt_index: int,
    target_type: str,
    kind: str,
    target_slot: int = 0,
    target_id: str = "",
    amount: int = 0,
    value: str = "",
    source: str = "unknown",
    actor_id: str = "",
) -> None:
    if target_type == "monster":
        opposition_state = copy.deepcopy(session.opposition_state or _empty_opposition_state())
        instance = next((item for item in opposition_state.get("instances", []) if item.get("monster_id") == target_id), None)
        if not instance:
            logger.warning(
                "Opposition state update skipped: session=%s prompt=%s target_id=%s kind=%s amount=%s source=%s active=%s instances=%s",
                session.session_id,
                prompt_index,
                target_id,
                kind,
                amount,
                source,
                opposition_state.get("active"),
                [item.get("monster_id") for item in opposition_state.get("instances", [])],
            )
            return
        name = instance.get("display_name") or target_id
        hp_before = int(instance.get("current_hp", 0) or 0)
        if kind == "damage" and amount > 0:
            instance["current_hp"] = max(0, int(instance.get("current_hp", 0)) - amount)
            _append_system_event(
                db,
                session.session_id,
                prompt_index,
                EventKind.HP_CHANGED,
                f"{name} takes {amount} damage.",
                {"target_type": "monster", "target_id": target_id, "amount": amount, "source": source},
            )
        elif kind == "healing" and amount > 0:
            instance["current_hp"] = min(int(instance.get("hp_max", 0)), int(instance.get("current_hp", 0)) + amount)
            _append_system_event(
                db,
                session.session_id,
                prompt_index,
                EventKind.HP_CHANGED,
                f"{name} heals {amount} HP.",
                {"target_type": "monster", "target_id": target_id, "amount": -amount, "source": source},
            )
        elif kind == "status_add" and value:
            statuses = list(instance.get("status_effects", []))
            if value not in statuses:
                statuses.append(value)
                instance["status_effects"] = statuses
            _append_system_event(
                db,
                session.session_id,
                prompt_index,
                EventKind.CONDITION_ADDED,
                f"{name} gains status: {value}.",
                {"target_type": "monster", "target_id": target_id, "status": value, "source": source},
            )
        elif kind == "status_remove" and value:
            instance["status_effects"] = [item for item in instance.get("status_effects", []) if item != value]
            _append_system_event(
                db,
                session.session_id,
                prompt_index,
                EventKind.CONDITION_REMOVED,
                f"{name} loses status: {value}.",
                {"target_type": "monster", "target_id": target_id, "status": value, "source": source},
            )
        hp_after = int(instance.get("current_hp", 0) or 0)
        logger.info(
            "Opposition state update: session=%s prompt=%s monster=%s target_id=%s kind=%s amount=%s hp_before=%s hp_after=%s is_dead=%s source=%s",
            session.session_id,
            prompt_index,
            name,
            target_id,
            kind,
            amount,
            hp_before,
            hp_after,
            instance.get("is_dead", False),
            source,
        )
        if int(instance.get("current_hp", 0)) <= 0 and not instance.get("is_dead"):
            instance["current_hp"] = 0
            instance["is_dead"] = True
            _append_system_event(
                db,
                session.session_id,
                prompt_index,
                EventKind.MONSTER_DIED,
                f"{name} is dead.",
                {"target_type": "monster", "target_id": target_id, "source": source},
            )
        session.opposition_state = opposition_state
        living_instances = _living_opposition_instances(opposition_state)
        if instance.get("is_dead") and hp_before > 0:
            _apply_monster_death_objective_updates(
                db,
                session,
                prompt_index,
                opposition_state,
                instance,
                living_instances,
                actor_id=actor_id,
            )
        logger.info(
            "Opposition audit: session=%s prompt=%s active=%s living_count=%s instances=%s",
            session.session_id,
            prompt_index,
            opposition_state.get("active"),
            len(living_instances),
            [
                {
                    "monster_id": item.get("monster_id"),
                    "display_name": item.get("display_name"),
                    "current_hp": item.get("current_hp"),
                    "hp_max": item.get("hp_max"),
                    "is_dead": item.get("is_dead"),
                }
                for item in opposition_state.get("instances", [])
            ],
        )
        if opposition_state.get("active") and not living_instances:
            session.opposition_state = _arm_opposition_cleanup(opposition_state)
        return

    slot = int(target_slot)
    name = session.agent_names.get(str(slot), _default_name(slot))
    if kind == "damage" and amount > 0:
        _append_system_event(db, session.session_id, prompt_index, EventKind.DAMAGE_APPLIED, f"{name} takes {amount} damage.", {"target_type": "player", "target_slot": slot, "amount": amount, "source": source})
    elif kind == "healing" and amount > 0:
        _append_system_event(db, session.session_id, prompt_index, EventKind.DAMAGE_APPLIED, f"{name} heals {amount} HP.", {"target_type": "player", "target_slot": slot, "amount": -amount, "source": source})
    elif kind == "status_add" and value:
        _append_system_event(db, session.session_id, prompt_index, EventKind.CONDITION_ADDED, f"{name} gains status: {value}.", {"target_type": "player", "target_slot": slot, "status": value, "source": source})
    elif kind == "status_remove" and value:
        _append_system_event(db, session.session_id, prompt_index, EventKind.CONDITION_REMOVED, f"{name} loses status: {value}.", {"target_type": "player", "target_slot": slot, "status": value, "source": source})
    elif kind == "inventory_add" and value:
        current_inventory = derive_party_state(db, session.session_id).get(str(slot), {}).get("inventory", [])
        if any(_inventory_items_overlap(existing, value) for existing in current_inventory):
            return
        _append_system_event(db, session.session_id, prompt_index, EventKind.INVENTORY_GAINED, f"{name} gains {value}.", {"target_type": "player", "target_slot": slot, "item": value, "source": source})
    elif kind == "inventory_remove" and value:
        _append_system_event(db, session.session_id, prompt_index, EventKind.INVENTORY_LOST, f"{name} loses {value}.", {"target_type": "player", "target_slot": slot, "item": value, "source": source})


def _dismiss_opposition_state(db: Session, session: SessionModel, prompt_index: int, reason: str) -> None:
    opposition_state = copy.deepcopy(session.opposition_state or _empty_opposition_state())
    if not opposition_state.get("active"):
        logger.info(
            "Opposition dismiss skipped: session=%s prompt=%s reason=%s active=%s",
            session.session_id,
            prompt_index,
            reason,
            opposition_state.get("active"),
        )
        return
    logger.info(
        "Opposition dismissing: session=%s prompt=%s reason=%s instances=%s",
        session.session_id,
        prompt_index,
        reason,
        [
            {
                "monster_id": item.get("monster_id"),
                "display_name": item.get("display_name"),
                "current_hp": item.get("current_hp"),
                "hp_max": item.get("hp_max"),
                "is_dead": item.get("is_dead"),
            }
            for item in opposition_state.get("instances", [])
        ],
    )
    session.opposition_state = _empty_opposition_state()
    session.selected_agent_slots = [slot for slot in session.selected_agent_slots if slot != OPPOSITION_AGENT_SLOT]
    session.agent_names.pop(str(OPPOSITION_AGENT_SLOT), None)
    session.combat_state = _empty_combat_state()
    _append_system_event(
        db,
        session.session_id,
        prompt_index,
        EventKind.OPPOSITION_DISMISSED,
        "Opposition dismissed.",
        {"reason": reason},
    )


def _collect_target_slots(session: SessionModel, agent_slot: int, lowered: str) -> set[int]:
    named_slots = {
        int(slot_text)
        for slot_text, name in session.agent_names.items()
        if name and re.search(rf"\b{re.escape(name.lower())}\b", lowered)
    }
    if re.search(r"\b(?:everyone|everybody|all of you|you all|the group of you|each of you|all take)\b", lowered):
        return named_slots or {int(slot_text) for slot_text in session.agent_names.keys()}
    if named_slots:
        return named_slots
    if re.search(r"\byou\b", lowered):
        return {agent_slot}
    return set()


def _extract_gm_state_events(db: Session, session: SessionModel, agent_slot: int, prompt_index: int, user_text: str) -> None:
    lowered = user_text.lower()
    targets = _collect_target_slots(session, agent_slot, lowered)

    damage_match = re.search(r"\b(?:take|takes|suffer|suffers|for|deals?)\s+(\d+)\s+(?:points?\s+of\s+)?damage\b", lowered)
    if damage_match and targets:
        amount = int(damage_match.group(1))
        for slot in sorted(targets):
            _append_state_change(db, session, prompt_index, target_type="player", target_slot=slot, kind="damage", amount=amount, source="gm_parser")

    heal_match = re.search(r"\b(?:heal|heals|recover|recovers|regain|regains)\s+(\d+)\s*(?:hp|hit points)?\b", lowered)
    if heal_match and targets:
        amount = int(heal_match.group(1))
        for slot in sorted(targets):
            _append_state_change(db, session, prompt_index, target_type="player", target_slot=slot, kind="healing", amount=amount, source="gm_parser")

    gain_match = re.search(
        r"\b(?:gifted|gets?|finds?|receives?|gains?|given)(?:\s+\w+){0,6}\s+(?:an?|one|1)\s+([a-z][a-z\s'-]+?)(?:[,.!]|$)",
        lowered,
    )
    if gain_match and targets:
        item = gain_match.group(1).strip().title()
        for slot in sorted(targets):
            _append_state_change(db, session, prompt_index, target_type="player", target_slot=slot, kind="inventory_add", value=item, source="gm_parser")

    lose_match = re.search(r"\b(?:loses?|drop|drops|spends?)\s+(?:an?|one|1)\s+([a-z][a-z\s'-]+?)(?:[,.!]|$)", lowered)
    if lose_match and targets:
        item = lose_match.group(1).strip().title()
        for slot in sorted(targets):
            _append_state_change(db, session, prompt_index, target_type="player", target_slot=slot, kind="inventory_remove", value=item, source="gm_parser")


def _advance_turn_if_in_combat(session: SessionModel) -> None:
    combat = copy.deepcopy(session.combat_state or _empty_combat_state())
    if not combat.get("in_combat") or not combat.get("initiative_order"):
        session.combat_state = combat
        return
    combat["turn_index"] += 1
    if combat["turn_index"] >= len(combat["initiative_order"]):
        combat["round"] += 1
        combat["turn_index"] = 0
    session.combat_state = combat


def _prompt_system_events(db: Session, session_id: str, prompt_index: int) -> list[Event]:
    return db.execute(
        select(Event)
        .where(Event.session_id == session_id, Event.prompt_index == prompt_index, Event.role == EventRole.SYSTEM)
        .order_by(Event.created_at.asc())
    ).scalars().all()


def _create_agent_transcript_event(
    db: Session,
    session_id: str,
    prompt_index: int,
    agent_slot: int,
    text: str,
) -> Event:
    agent_event = Event(
        session_id=session_id,
        prompt_index=prompt_index,
        role=EventRole.AGENT,
        kind=EventKind.TRANSCRIPT,
        agent_slot=agent_slot,
        text=text,
        json_payload={},
    )
    db.add(agent_event)
    db.flush()
    return agent_event


def finalize_prompt_narration(
    session_id: str,
    prompt_index: int,
    agent_slot: int,
    agent_id: str,
    model: str,
    agent_payload: dict[str, Any],
    continuation: dict[str, Any],
) -> None:
    db = SessionLocal()
    try:
        existing_event = db.execute(
            select(Event).where(
                Event.session_id == session_id,
                Event.prompt_index == prompt_index,
                Event.role == EventRole.AGENT,
                Event.agent_slot == agent_slot,
                Event.kind == EventKind.TRANSCRIPT,
            )
        ).scalar_one_or_none()
        if existing_event:
            return

        provider = get_provider()
        content = provider.continue_generation(continuation).strip()
        if not content:
            content = "The action resolves as described."

        _create_agent_transcript_event(db, session_id, prompt_index, agent_slot, content)
        log_artifact(
            db,
            session_id,
            f"{agent_id}_continuation",
            model,
            agent_payload,
            content,
            provider.provider_name,
        )

        session = get_session_or_404(db, session_id)
        if prompt_index % settings.chunk_size_prompts == 0 and session.last_summarized_prompt_index < prompt_index:
            session.state = SessionState.SUMMARIZING
            _run_summarization(db, session, prompt_index)
            session.state = SessionState.ACTIVE

        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Prompt narration continuation failed: session=%s prompt=%s agent_slot=%s",
            session_id,
            prompt_index,
            agent_slot,
        )
    finally:
        db.close()


def prompt_agent(
    db: Session,
    session_id: str,
    agent_slot: int,
    user_text: str,
) -> tuple[SessionModel, Event, Event | None, bool, list[Event], dict[str, Any] | None]:
    provider = get_provider()
    session = get_session_or_404(db, session_id)
    if session.state != SessionState.ACTIVE:
        raise ValueError("Session is not ACTIVE")
    if agent_slot not in session.selected_agent_slots:
        raise ValueError("Agent slot not selected for this session")
    if agent_slot == OPPOSITION_AGENT_SLOT and not _living_opposition_instances(session.opposition_state):
        raise ValueError("Opposition is not active")

    session.prompt_index += 1
    user_event = Event(
        session_id=session_id,
        prompt_index=session.prompt_index,
        role=EventRole.USER,
        kind=EventKind.TRANSCRIPT,
        agent_slot=None,
        text=f"GM: {user_text}",
        json_payload={},
    )
    db.add(user_event)
    db.flush()
    if agent_slot != OPPOSITION_AGENT_SLOT:
        _extract_gm_state_events(db, session, agent_slot, session.prompt_index, user_text)

    if agent_slot == OPPOSITION_AGENT_SLOT:
        agent_payload = _build_opposition_payload(db, session, user_text)
        agent_id = "agent12"
        agent_model = settings.llm_model_opposition
        generation = provider.generate_action_response("agent12", settings.llm_model_opposition, agent_payload)
        log_artifact(
            db,
            session_id,
            agent_id,
            agent_model,
            agent_payload,
            json.dumps(
                {
                    "content": generation.content,
                    "rolls": generation.pending_roll_results,
                    "actions": generation.pending_action_results,
                    "state_changes": generation.pending_state_changes,
                    "narration_pending": generation.narration_pending,
                },
                ensure_ascii=True,
            ),
            provider.provider_name,
        )
    else:
        agent_payload = _build_character_payload(db, session, agent_slot, user_text)
        agent_id = "agent_character"
        agent_model = settings.llm_model_character
        generation = provider.generate_action_response("agent_character", settings.llm_model_character, agent_payload)
        log_artifact(
            db,
            session_id,
            agent_id,
            agent_model,
            agent_payload,
            json.dumps(
                {
                    "content": generation.content,
                    "rolls": generation.pending_roll_results,
                    "actions": generation.pending_action_results,
                    "state_changes": generation.pending_state_changes,
                    "narration_pending": generation.narration_pending,
                },
                ensure_ascii=True,
            ),
            provider.provider_name,
        )

    agent_event: Event | None = None
    continuation_job: dict[str, Any] | None = None
    if generation.narration_pending:
        continuation_job = {
            "session_id": session_id,
            "prompt_index": session.prompt_index,
            "agent_slot": agent_slot,
            "agent_id": agent_id,
            "model": agent_model,
            "agent_payload": agent_payload,
            "continuation": generation.continuation,
        }
    else:
        agent_event = _create_agent_transcript_event(db, session_id, session.prompt_index, agent_slot, generation.content)

    _apply_generation_result(db, session, agent_slot, session.prompt_index, generation)
    _append_system_event(db, session_id, session.prompt_index, EventKind.TURN_ENDED, f"Turn ended for {session.agent_names.get(str(agent_slot), _default_name(agent_slot))}.", {"agent_slot": agent_slot})
    _advance_turn_if_in_combat(session)

    summary_triggered = False
    if not generation.narration_pending and session.prompt_index % settings.chunk_size_prompts == 0:
        session.state = SessionState.SUMMARIZING
        summary_triggered = _run_summarization(db, session, session.prompt_index)
        session.state = SessionState.ACTIVE

    session.generated_image = {**session.generated_image, "last_actor_slot": agent_slot}
    db.commit()
    db.refresh(session)
    db.refresh(user_event)
    if agent_event is not None:
        db.refresh(agent_event)
    prompt_events = _prompt_system_events(db, session_id, session.prompt_index)
    return session, user_event, agent_event, summary_triggered, prompt_events, continuation_job


def end_chapter(db: Session, session_id: str) -> SessionModel:
    session = get_session_or_404(db, session_id)
    if session.state != SessionState.ACTIVE:
        raise ValueError("End chapter allowed only from ACTIVE")
    if session.last_summarized_prompt_index < session.prompt_index:
        session.state = SessionState.SUMMARIZING
        _run_summarization(db, session, session.prompt_index)
    session.state = SessionState.ENDED
    db.commit()
    db.refresh(session)
    return session


def _validate_mission_travel(session: SessionModel, location_id: str) -> None:
    state = session.mission_objective_state or {}
    if state.get("adventure_id") != "telas-wagons" or state.get("complete"):
        return
    allowed = set(state.get("allowed_location_ids", []))
    if allowed and location_id not in allowed:
        raise ValueError("The wagon train cannot travel there yet. Follow the King's Way route in order.")


def _apply_travel_objective_updates(db: Session, session: SessionModel, prompt_index: int, location_id: str) -> None:
    state = copy.deepcopy(session.mission_objective_state or {})
    adventure_id = state.get("adventure_id", "")
    if not adventure_id or state.get("complete"):
        return

    if adventure_id == "telas-wagons":
        sequence = MISSION_OBJECTIVE_CONFIG[adventure_id]["travel_sequence"]
        if location_id not in sequence:
            return
        step_index = sequence.index(location_id)
        state["visited_location_ids"] = list(dict.fromkeys([*state.get("visited_location_ids", []), location_id]))
        state["current_step"] = step_index + 1
        if location_id == sequence[-1]:
            _set_mission_complete(
                db,
                session,
                prompt_index,
                state,
                (
                    "The convoy of tradesmen thanks the party for their efforts providing much needed safety "
                    "along the King's Way. You are paid for your efforts and free to return to Moosehearth."
                ),
                {"adventure_id": adventure_id, "location_id": location_id},
            )
            return
        state["allowed_location_ids"] = [sequence[step_index + 1]]
        note = f"Wagon route progress: location {step_index + 1}/6 reached. Next stop unlocked."
        state["progress_label"] = note
        state.setdefault("updates", []).append({"prompt_index": prompt_index, "text": note})
        session.mission_objective_state = state
        _append_system_event(
            db,
            session.session_id,
            prompt_index,
            EventKind.OBJECTIVE_UPDATED,
            f"Objective progress: {note}",
            {"adventure_id": adventure_id, "location_id": location_id, "next_location_id": sequence[step_index + 1]},
        )
        return

    if adventure_id == "east-marsh-raid" and location_id == MISSION_OBJECTIVE_CONFIG[adventure_id]["target_location_id"]:
        if state.get("boss_encounter_spawned") or (session.opposition_state or {}).get("active"):
            return
        _spawn_opposition_group(db, session, ["Bandit Captain", "Giant Boar"], prompt_index, source="mission_objective")
        state["boss_encounter_spawned"] = True
        state["boss_encounter_group_id"] = session.opposition_state.get("group_id", "")
        state["progress_label"] = "The war leader has been found. Defeat the Bandit Captain and Giant Boar."
        state.setdefault("updates", []).append({"prompt_index": prompt_index, "text": state["progress_label"]})
        session.mission_objective_state = state
        _append_system_event(
            db,
            session.session_id,
            prompt_index,
            EventKind.OBJECTIVE_UPDATED,
            f"Objective progress: {state['progress_label']}",
            {"adventure_id": adventure_id, "location_id": location_id, "boss_encounter_spawned": True},
        )


def travel_to_location(db: Session, session_id: str, location_id: str, location_name: str, location_description: str) -> SessionModel:
    session = get_session_or_404(db, session_id)
    if session.state != SessionState.ACTIVE:
        raise ValueError("Travel is allowed only in ACTIVE state")

    clean_name = (location_name or "").strip()
    clean_description = (location_description or "").strip()
    if not clean_name or not clean_description:
        raise ValueError("Location name and description are required")
    _validate_mission_travel(session, location_id)

    travel_intro = ""
    mission_state = session.mission_objective_state or {}
    if mission_state.get("adventure_id") == "telas-wagons" and location_id == "loc-1":
        travel_intro = (
            "The party meets up with the wagon train just outside of town. Speaking with the tradesmen, "
            "the party is directed to take the lead as the wagons begin their slow crawl along the King's Way.\n\n"
        )
    travel_text = f"{travel_intro}The party ventures to, {clean_name}, surveying the area you see {clean_description}."
    session.current_location_id = location_id
    session.current_location_name = clean_name
    session.current_location_text = travel_text
    db.add(
        Event(
            session_id=session_id,
            prompt_index=session.prompt_index,
            role=EventRole.SYSTEM,
            kind=EventKind.TRANSCRIPT,
            agent_slot=None,
            text=travel_text,
            json_payload={"location_id": location_id, "location_name": clean_name, "source": "travel_button"},
        )
    )
    _apply_travel_objective_updates(db, session, session.prompt_index, location_id)
    db.commit()
    db.refresh(session)
    return session


def return_to_moosehearth(db: Session, session_id: str) -> SessionModel:
    session = get_session_or_404(db, session_id)
    if session.state != SessionState.ACTIVE:
        raise ValueError("Return to Moosehearth is allowed only during ACTIVE play")
    objective_state = session.mission_objective_state or {}
    if not objective_state.get("complete"):
        raise ValueError("Complete the current mission objective before returning to Moosehearth")
    if (session.opposition_state or {}).get("active"):
        raise ValueError("Resolve or flee the active encounter before returning to Moosehearth")

    return_text = "The party returns to Moosehearth to report their success and recover at the Antlers' Rest Inn."
    session.current_location_id = ""
    session.current_location_name = "Antlers Rest Inn"
    session.current_location_text = return_text
    objective_state = copy.deepcopy(objective_state)
    objective_state["returned_to_moosehearth"] = True
    session.mission_objective_state = objective_state
    db.add(
        Event(
            session_id=session_id,
            prompt_index=session.prompt_index,
            role=EventRole.SYSTEM,
            kind=EventKind.TRANSCRIPT,
            agent_slot=None,
            text=return_text,
            json_payload={"source": "return_to_moosehearth"},
        )
    )
    db.commit()
    db.refresh(session)
    return session


def take_long_rest(db: Session, session_id: str) -> SessionModel:
    session = get_session_or_404(db, session_id)
    _ensure_nonblocking_opposition_state(db, session)
    if session.state != SessionState.ACTIVE:
        raise ValueError("Long rest is allowed only in ACTIVE state")
    if (session.opposition_state or {}).get("active"):
        raise ValueError("You cannot take a long rest while Opposition is active")

    tab1 = get_tab1_or_create(db, session_id)
    current_party_state = derive_party_state(db, session_id)
    session.prompt_index += 1
    prompt_index = session.prompt_index

    db.add(
        Event(
            session_id=session_id,
            prompt_index=prompt_index,
            role=EventRole.SYSTEM,
            kind=EventKind.TRANSCRIPT,
            agent_slot=None,
            text=LONG_REST_TRANSCRIPT,
            json_payload={"source": "long_rest", "hours": 8},
        )
    )

    for slot in range(1, 5):
        player_id = _player_for_slot(tab1, slot)
        class_id = _class_assignment_for_slot(tab1, slot)
        if not player_id or not class_id:
            continue
        hp_max = int(CLASSES[class_id]["hp_max"])
        hp_current = int(current_party_state.get(str(slot), {}).get("hp_current", hp_max))
        healing = max(0, hp_max - hp_current)
        if healing > 0:
            _append_state_change(
                db,
                session,
                prompt_index,
                target_type="player",
                target_slot=slot,
                kind="healing",
                amount=healing,
                source="long_rest",
            )

    session.combat_state = _empty_combat_state()
    db.commit()
    db.refresh(session)
    return session


def _spawn_opposition_group(
    db: Session,
    session: SessionModel,
    monster_types: list[str],
    prompt_index: int,
    source: str = "manual",
) -> SessionModel:
    if not monster_types or len(monster_types) > 4:
        raise ValueError("Opposition group must contain between 1 and 4 monsters")
    instances = []
    for index, instance_type in enumerate(monster_types):
        template = _monster_template(instance_type)
        instances.append(
            {
                "monster_id": str(uuid.uuid4()),
                "display_name": MONSTER_INSTANCE_LABELS[index],
                "monster_type": instance_type,
                "monster_stats": template,
                "current_hp": template["hp"],
                "hp_max": template["hp"],
                "is_dead": False,
                "status_effects": [],
            }
        )
    group_type = monster_types[0] if len(set(monster_types)) == 1 else "Mixed"
    group_stats = _monster_template(monster_types[0])
    session.opposition_state = {
        "active": True,
        "group_id": str(uuid.uuid4()),
        "initiative_id": OPPOSITION_INITIATIVE_ID,
        "monster_type": group_type,
        "monster_stats": group_stats,
        "instances": instances,
        "cleanup_after": "",
        "source": source,
    }
    if OPPOSITION_AGENT_SLOT not in session.selected_agent_slots:
        session.selected_agent_slots = [*session.selected_agent_slots, OPPOSITION_AGENT_SLOT]
    session.agent_names[str(OPPOSITION_AGENT_SLOT)] = OPPOSITION_DISPLAY_NAME
    summary = ", ".join(monster_types)
    _append_system_event(
        db,
        session.session_id,
        prompt_index,
        EventKind.OPPOSITION_SPAWNED,
        f"Opposition spawned: {summary}.",
        {"monster_types": monster_types, "quantity": len(monster_types), "source": source},
    )
    roll_initiative(db, session.session_id)
    return session


def spawn_opposition(db: Session, session_id: str, monster_type: str, quantity: int) -> SessionModel:
    session = get_session_or_404(db, session_id)
    tab1 = get_tab1_or_create(db, session_id)
    _ensure_nonblocking_opposition_state(db, session)
    if session.state != SessionState.ACTIVE:
        raise ValueError("Opposition can only be spawned during ACTIVE play")
    if (session.opposition_state or {}).get("active"):
        raise ValueError("Dismiss the current Opposition group before spawning a new one")
    if quantity < 1 or quantity > 4:
        raise ValueError("Quantity must be between 1 and 4")
    if monster_type not in ADVENTURES.get(tab1.adventure_id, {}).get("monsters", []):
        raise ValueError("That monster is not assigned to the selected adventure")

    _spawn_opposition_group(db, session, [monster_type for _ in range(quantity)], session.prompt_index, source="manual")
    db.commit()
    db.refresh(session)
    return session


def dismiss_opposition(db: Session, session_id: str) -> SessionModel:
    session = get_session_or_404(db, session_id)
    _ensure_nonblocking_opposition_state(db, session)
    if not (session.opposition_state or {}).get("active"):
        raise ValueError("No active Opposition to dismiss")
    _dismiss_opposition_state(db, session, session.prompt_index, reason="manual")
    db.commit()
    db.refresh(session)
    return session


def save_narrative_agent(db: Session, session_id: str, selected_player_id: str) -> SessionModel:
    session = get_session_or_404(db, session_id)
    tab1 = get_tab1_or_create(db, session_id)
    if selected_player_id not in tab1.selected_player_ids:
        raise ValueError("Narrative player must be one of the selected players")
    session.selected_narrative_player_id = selected_player_id
    session.narrative_agent_definition_text = PLAYER_NARRATIVE_LENSES[selected_player_id]
    db.commit()
    db.refresh(session)
    return session


def build_narrative(db: Session, session_id: str) -> NarrativeDraft:
    provider = get_provider()
    session = get_session_or_404(db, session_id)
    tab1 = get_tab1_or_create(db, session_id)
    if session.state != SessionState.ENDED:
        raise ValueError("Build narrative allowed only in ENDED state")
    if session.selected_narrative_player_id not in tab1.selected_player_ids:
        raise ValueError("Select a narrative player first")

    session.state = SessionState.NARRATING
    events = db.execute(select(Event).where(Event.session_id == session_id).order_by(Event.prompt_index.asc(), Event.created_at.asc())).scalars().all()
    blocks = _current_memory_blocks(db, session_id)
    payload = {
        "selected_player_id": session.selected_narrative_player_id,
        "memory_blocks": [
            {
                "block_id": block.block_id,
                "type": block.type.value,
                "from_prompt_index": block.from_prompt_index,
                "to_prompt_index": block.to_prompt_index,
                "json_payload": block.json_payload,
            }
            for block in blocks
        ],
        "events": [
            {
                "prompt_index": event.prompt_index,
                "role": event.role.value,
                "kind": event.kind.value,
                "agent_slot": event.agent_slot,
                "text": event.text,
                "json_payload": event.json_payload,
            }
            for event in events
        ],
        "adventure": ADVENTURES.get(tab1.adventure_id),
    }
    try:
        output = provider.generate("agent9", settings.llm_model_narrative, payload)
        narrative_source = provider.provider_name
        log_artifact(db, session_id, "agent9", settings.llm_model_narrative, payload, output, provider.provider_name)
    except httpx.HTTPStatusError:
        output = _build_narrative_fallback(session, tab1, events, blocks)
        narrative_source = "fallback"
    draft = NarrativeDraft(
        session_id=session_id,
        narrative_agent_definition_text=session.narrative_agent_definition_text,
        source_snapshot={
            "max_prompt_index_used": session.prompt_index,
            "memory_block_ids_used": [block.block_id for block in blocks],
            "narrative_source": narrative_source,
        },
        chapter_text=output,
    )
    db.add(draft)
    session.state = SessionState.ENDED
    db.commit()
    db.refresh(draft)
    return draft


def _build_narrative_fallback(
    session: SessionModel,
    tab1: Tab1Inputs,
    events: list[Event],
    blocks: list[MemoryBlock],
) -> str:
    selected_player_id = session.selected_narrative_player_id
    adventure = ADVENTURES.get(tab1.adventure_id) or {}
    class_name = (tab1.class_assignments or {}).get(selected_player_id, "adventurer")
    recent_turns = [event for event in events if event.role in {EventRole.USER, EventRole.AGENT}][-10:]
    transcript_lines: list[str] = []
    for event in recent_turns:
        if event.role == EventRole.USER:
            transcript_lines.append(f"GM: {event.text}")
        elif event.role == EventRole.AGENT:
            transcript_lines.append(event.text.strip())

    summary_lines: list[str] = []
    for block in blocks[-3:]:
        payload = block.json_payload or {}
        summary = payload.get("summary")
        if isinstance(summary, str) and summary.strip():
            summary_lines.append(summary.strip())

    parts = [
        f"Adventure recap from {selected_player_id}'s point of view.",
        f"{selected_player_id} traveled as the party's {class_name} on {adventure.get('title', 'their Valaska mission')}.",
    ]
    if summary_lines:
        parts.append("Structured memory highlights:")
        parts.extend(summary_lines)
    if transcript_lines:
        parts.append("Recent key moments:")
        parts.extend(transcript_lines)
    parts.append(
        "This fallback chapter was assembled locally because the narrative model was temporarily unavailable."
    )
    return "\n\n".join(parts)


def reset_session(db: Session, session_id: str) -> SessionModel:
    session = get_session_or_404(db, session_id)
    session.state = SessionState.RESETTING
    db.flush()
    db.execute(delete(Event).where(Event.session_id == session_id))
    db.execute(delete(MemoryBlock).where(MemoryBlock.session_id == session_id))
    db.execute(delete(NarrativeDraft).where(NarrativeDraft.session_id == session_id))

    tab1 = get_tab1_or_create(db, session_id)
    tab1.world_text = VALASKA_SYSTEM_PROMPT
    tab1.chapter_text = ""
    tab1.agent_identity_text_by_slot = {}
    tab1.preset_id = VALASKA_PRESET_ID
    tab1.adventure_id = ""
    tab1.selected_player_ids = []
    tab1.class_assignments = {}

    session.state = SessionState.DRAFT_TAB1
    session.prompt_index = 0
    session.last_summarized_prompt_index = 0
    session.tab1_locked = False
    session.selected_agent_slots = [1, 2, 3, 4]
    session.agent_names = {str(slot): _default_name(slot) for slot in range(1, 5)}
    session.narrative_agent_definition_text = ""
    session.current_location_text = ""
    session.current_location_id = ""
    session.current_location_name = ""
    session.selected_narrative_player_id = ""
    session.combat_state = _empty_combat_state()
    session.opposition_state = _empty_opposition_state()
    session.mission_objective_state = _empty_mission_objective_state()
    session.generated_image = _default_generated_image()

    db.commit()
    db.refresh(session)
    return session


def perform_dice_roll(formula: str, label: str = "", roller_id: str = "unknown") -> dict:
    match = DICE_RE.match(formula or "")
    if not match:
        return {"error": {"code": "invalid_formula", "message": "Formula must look like NdM+K using d4/d6/d8/d10/d12/d20."}}
    dice_count = int(match.group(1))
    dice_sides = int(match.group(2))
    modifier_raw = match.group(3) or ""
    modifier = int(modifier_raw.replace(" ", "")) if modifier_raw else 0
    if dice_count < 1 or dice_count > 100 or dice_sides not in VALID_DICE_SIDES:
        return {"error": {"code": "invalid_formula", "message": "Dice count or sides are out of bounds."}}
    rolls = [randbelow(dice_sides) + 1 for _ in range(dice_count)]
    timestamp = datetime.now(timezone.utc)
    return {
        "formula": formula.replace(" ", ""),
        "dice_count": dice_count,
        "dice_sides": dice_sides,
        "rolls": rolls,
        "modifier": modifier,
        "total": sum(rolls) + modifier,
        "label": label,
        "roller_id": roller_id,
        "timestamp": timestamp.isoformat(),
        "roll_id": str(uuid.uuid4()),
    }


def roll_dice_for_session(db: Session, session_id: str, formula: str, label: str = "", roller_id: str = "unknown") -> dict:
    session = get_session_or_404(db, session_id)
    result = perform_dice_roll(formula, label, roller_id)
    if "error" in result:
        raise ValueError(result["error"]["message"])
    db.add(
        Event(
            session_id=session_id,
            prompt_index=session.prompt_index,
            role=EventRole.SYSTEM,
            kind=EventKind.DICE_ROLL,
            agent_slot=None,
            text=f"{label or formula}: {result['total']}",
            json_payload=result,
        )
    )
    db.commit()
    return result


def roll_dice_batch_for_session(db: Session, session_id: str, rolls: list[dict]) -> list[dict]:
    return [roll_dice_for_session(db, session_id, item.get("formula", ""), item.get("label", ""), item.get("roller_id", "unknown")) for item in rolls]


def roll_initiative(db: Session, session_id: str) -> dict:
    session = get_session_or_404(db, session_id)
    tab1 = get_tab1_or_create(db, session_id)
    if not session.tab1_locked:
        raise ValueError("Lock Tab1 before rolling initiative")

    rolls = []
    initiative_values: dict[str, int] = {}
    for slot in range(1, 5):
        player_id = _player_for_slot(tab1, slot)
        class_id = _class_assignment_for_slot(tab1, slot)
        dex = CLASSES[class_id]["ability_scores"]["DEX"]
        modifier = (dex - 10) // 2
        formula = f"1d20+{modifier}" if modifier >= 0 else f"1d20{modifier}"
        result = roll_dice_for_session(db, session_id, formula, f"Initiative: {PLAYERS[player_id]['name']}", f"Player:{player_id}")
        rolls.append(result)
        initiative_values[f"pc:{slot}"] = result["total"]

    opposition_state = session.opposition_state or _empty_opposition_state()
    if opposition_state.get("active") and _living_opposition_instances(opposition_state):
        result = roll_dice_for_session(
            db,
            session_id,
            "1d20+2",
            "Initiative: Opposition",
            "Opposition",
        )
        rolls.append(result)
        initiative_values[OPPOSITION_INITIATIVE_ID] = result["total"]

    ordered = sorted(initiative_values.items(), key=lambda item: (-item[1], item[0]))
    session.combat_state = {
        "in_combat": True,
        "round": 1,
        "turn_index": 0,
        "initiative_order": [combatant_id for combatant_id, _ in ordered],
        "initiative_values": initiative_values,
    }
    db.add(
        Event(
            session_id=session_id,
            prompt_index=session.prompt_index,
            role=EventRole.SYSTEM,
            kind=EventKind.INITIATIVE_SET,
            agent_slot=None,
            text="Initiative order updated.",
            json_payload=copy.deepcopy(session.combat_state),
        )
    )
    db.commit()
    return {"combat_state": session.combat_state, "rolls": rolls}


def _reference_image_bytes(tab1: Tab1Inputs, last_actor_slot: int | None) -> bytes | None:
    if not last_actor_slot:
        return None
    player_id = _player_for_slot(tab1, last_actor_slot)
    class_id = _class_assignment_for_slot(tab1, last_actor_slot)
    if not player_id or not class_id:
        return None
    path = ASSET_DIR / _portrait_filename(player_id, class_id)
    if not path.exists():
        return None
    return path.read_bytes()


def generate_scene_image(db: Session, session_id: str) -> dict:
    session = get_session_or_404(db, session_id)
    provider = get_provider()
    tab1 = get_tab1_or_create(db, session_id)
    payload = {
        "structured_memory": [
            {
                "type": block.type.value,
                "from_prompt_index": block.from_prompt_index,
                "to_prompt_index": block.to_prompt_index,
                "json_payload": block.json_payload,
            }
            for block in _current_memory_blocks(db, session_id)
        ],
        "recent_context": [
            {"prompt_index": event.prompt_index, "role": event.role.value, "agent_slot": event.agent_slot, "text": event.text}
            for event in _recent_events(db, session)
        ],
    }
    prompt_text = provider.generate("agent10", settings.llm_model_summary, payload)
    log_artifact(db, session_id, "agent10", settings.llm_model_summary, payload, prompt_text, provider.provider_name)
    try:
        image_url = provider.generate_image(prompt_text, _reference_image_bytes(tab1, session.generated_image.get("last_actor_slot")))
    except Exception:
        image_url = asset_url(DEFAULT_IMAGE_FILE)
    if image_url == "mock://generated-image":
        image_url = asset_url(DEFAULT_IMAGE_FILE)
    session.generated_image = {"image_url": image_url, "prompt_text": prompt_text, "last_actor_slot": session.generated_image.get("last_actor_slot")}
    db.add(
        Event(
            session_id=session_id,
            prompt_index=session.prompt_index,
            role=EventRole.SYSTEM,
            kind=EventKind.IMAGE_GENERATED,
            agent_slot=None,
            text="Scene image updated.",
            json_payload=copy.deepcopy(session.generated_image),
        )
    )
    db.commit()
    return session.generated_image


def synthesize_player_reply_tts(db: Session, session_id: str, text: str, player_name: str) -> bytes:
    started_at = time.perf_counter()
    get_session_or_404(db, session_id)
    provider = get_provider()
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("Reply text is required for TTS")
    voice_alias = tts_voice_alias_for_player(player_name)
    try:
        audio_bytes = provider.generate_speech(clean_text, voice_alias)
        elapsed = time.perf_counter() - started_at
        logger.info(
            "TTS request completed in %.2fs session_id=%s player=%s voice_alias=%s text_chars=%s bytes=%s",
            elapsed,
            session_id,
            player_name,
            voice_alias,
            len(clean_text),
            len(audio_bytes),
        )
        return audio_bytes
    except Exception:
        elapsed = time.perf_counter() - started_at
        logger.exception(
            "TTS request failed after %.2fs session_id=%s player=%s voice_alias=%s text_chars=%s",
            elapsed,
            session_id,
            player_name,
            voice_alias,
            len(clean_text),
        )
        raise


def derive_party_state(db: Session, session_id: str) -> dict[str, dict]:
    session = get_session_or_404(db, session_id)
    tab1 = get_tab1_or_create(db, session_id)
    state = {}
    for slot in range(1, 5):
        player_id = _player_for_slot(tab1, slot)
        class_id = _class_assignment_for_slot(tab1, slot)
        if not player_id or not class_id:
            continue
        class_data = CLASSES[class_id]
        state[str(slot)] = {
            "hp_current": class_data["hp_max"],
            "status_effects": [],
            "inventory": list(class_data["inventory"]),
            "initiative": session.combat_state.get("initiative_values", {}).get(f"pc:{slot}"),
        }

    events = db.execute(select(Event).where(Event.session_id == session_id).order_by(Event.created_at.asc())).scalars().all()
    seen_state_events: set[tuple] = set()
    for event in events:
        payload = event.json_payload or {}
        if payload.get("target_type", "player") != "player":
            continue
        slot = payload.get("target_slot")
        if slot is None:
            continue
        key = str(slot)
        if key not in state:
            continue
        dedupe_key = None
        if event.kind in {EventKind.DAMAGE_APPLIED, EventKind.HP_CHANGED}:
            dedupe_key = (event.prompt_index, event.kind.value, slot, int(payload.get("amount", 0)))
        elif event.kind in {EventKind.CONDITION_ADDED, EventKind.CONDITION_REMOVED}:
            dedupe_key = (event.prompt_index, event.kind.value, slot, payload.get("status", ""))
        elif event.kind in {EventKind.INVENTORY_GAINED, EventKind.INVENTORY_LOST}:
            dedupe_key = (event.prompt_index, event.kind.value, slot, payload.get("item", ""))
        if dedupe_key is not None:
            if dedupe_key in seen_state_events:
                continue
            seen_state_events.add(dedupe_key)
        if event.kind in {EventKind.DAMAGE_APPLIED, EventKind.HP_CHANGED}:
            amount = int(payload.get("amount", 0))
            hp_max = CLASSES[_class_assignment_for_slot(tab1, int(slot))]["hp_max"]
            state[key]["hp_current"] = max(0, min(state[key]["hp_current"] - amount, hp_max))
        elif event.kind == EventKind.CONDITION_ADDED:
            status = payload.get("status", "")
            if status and status not in state[key]["status_effects"]:
                state[key]["status_effects"].append(status)
        elif event.kind == EventKind.CONDITION_REMOVED:
            status = payload.get("status", "")
            state[key]["status_effects"] = [item for item in state[key]["status_effects"] if item != status]
        elif event.kind == EventKind.INVENTORY_GAINED:
            item = payload.get("item", "")
            if item:
                state[key]["inventory"].append(item)
        elif event.kind == EventKind.INVENTORY_LOST:
            item = payload.get("item", "")
            if item in state[key]["inventory"]:
                state[key]["inventory"].remove(item)
    return state


def get_session_detail(db: Session, session_id: str) -> dict:
    session = get_session_or_404(db, session_id)
    if _maybe_finalize_opposition_cleanup(db, session):
        db.commit()
        session = get_session_or_404(db, session_id)
    tab1 = get_tab1_or_create(db, session_id)
    events = db.execute(select(Event).where(Event.session_id == session_id).order_by(Event.prompt_index.asc(), Event.created_at.asc())).scalars().all()
    memory_blocks = _current_memory_blocks(db, session_id)
    drafts = db.execute(select(NarrativeDraft).where(NarrativeDraft.session_id == session_id).order_by(NarrativeDraft.created_at.asc())).scalars().all()
    party_state = derive_party_state(db, session_id)
    party = []
    for slot in range(1, 5):
        player_id = _player_for_slot(tab1, slot)
        class_id = _class_assignment_for_slot(tab1, slot)
        if player_id and class_id:
            party.append(_party_member(slot, player_id, class_id, party_state.get(str(slot), {})))
    adventure = serialize_adventure(tab1.adventure_id)
    gm_monsters = [serialize_monster_reference(name) for name in sorted(ADVENTURES.get(tab1.adventure_id, {}).get("monsters", []))]
    return {
        "session": session,
        "tab1": tab1,
        "events": events,
        "memory_blocks": memory_blocks,
        "narrative_drafts": drafts,
        "party": party,
        "active_adventure": adventure,
        "gm_monsters": gm_monsters,
        "image_state": session.generated_image or _default_generated_image(),
    }

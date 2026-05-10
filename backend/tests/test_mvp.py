import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./test_story_engine.db"

from app import main as main_module  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Event, EventKind, EventRole  # noqa: E402
from app.services import _advance_combat_turn, _append_state_change, _apply_hazard_skill_result, get_session_or_404, resolve_actions_for_payload, use_item  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(main_module.app) as c:
        yield c


def mk2_tab1_payload():
    return {
        "preset_id": "valaska",
        "adventure_id": "icebane-castle",
        "selected_player_ids": ["Joe", "Annie", "Tom", "Jannet"],
        "class_assignments": {
            "1": "Fighter",
            "2": "Rogue",
            "3": "Wizard",
            "4": "Cleric",
        },
    }


def jannet_wizard_payload():
    return {
        "preset_id": "valaska",
        "adventure_id": "icebane-castle",
        "selected_player_ids": ["Joe", "Annie", "Tom", "Jannet"],
        "class_assignments": {
            "1": "Fighter",
            "2": "Rogue",
            "3": "Cleric",
            "4": "Wizard",
        },
    }


def east_marsh_jannet_wizard_payload():
    payload = jannet_wizard_payload()
    payload["adventure_id"] = "east-marsh-raid"
    return payload


def old_people_barrow_payload():
    payload = jannet_wizard_payload()
    payload["adventure_id"] = "old-people-barrow"
    return payload


def collecting_taxes_payload():
    payload = jannet_wizard_payload()
    payload["adventure_id"] = "collecting-taxes"
    return payload


def telas_wagons_payload():
    payload = jannet_wizard_payload()
    payload["adventure_id"] = "telas-wagons"
    return payload


def create_and_lock_session(client: TestClient) -> str:
    created = client.post("/session").json()
    session_id = created["session_id"]
    resp = client.put(f"/session/{session_id}/tab1", json=mk2_tab1_payload())
    assert resp.status_code == 200
    lock = client.post(f"/session/{session_id}/lock")
    assert lock.status_code == 200
    return session_id


def test_prompt_index_increments_only_on_user_prompt(client: TestClient):
    session_id = create_and_lock_session(client)

    for i in range(3):
        r = client.post(f"/session/{session_id}/prompt", json={"agent_slot": 1, "user_text": f"u{i}"})
        assert r.status_code == 200
        assert r.json()["session"]["prompt_index"] == i + 1

    detail = client.get(f"/session/{session_id}").json()
    transcript_events = [event for event in detail["events"] if event["kind"] == "transcript"]
    assert len(transcript_events) == 7
    assert [event["prompt_index"] for event in transcript_events if event["role"] == "user"] == [1, 2, 3]
    assert [event["prompt_index"] for event in transcript_events if event["role"] == "agent"] == [1, 2, 3]


def test_summarization_triggers_at_multiples_of_7(client: TestClient):
    session_id = create_and_lock_session(client)

    for i in range(6):
        r = client.post(f"/session/{session_id}/prompt", json={"agent_slot": 1, "user_text": f"u{i}"})
        assert r.status_code == 200
        assert r.json()["summary_triggered"] is False

    r7 = client.post(f"/session/{session_id}/prompt", json={"agent_slot": 1, "user_text": "u7"})
    assert r7.status_code == 200
    assert r7.json()["summary_triggered"] is True

    detail = client.get(f"/session/{session_id}").json()
    assert detail["session"]["last_summarized_prompt_index"] == 7
    turn_blocks = [block for block in detail["memory_blocks"] if block["type"] == "turn_delta"]
    assert len(turn_blocks) == 1
    assert turn_blocks[0]["from_prompt_index"] == 1
    assert turn_blocks[0]["to_prompt_index"] == 7


def test_memory_blocks_are_append_only(client: TestClient):
    session_id = create_and_lock_session(client)
    baseline = client.get(f"/session/{session_id}").json()
    baseline_ids = [block["block_id"] for block in baseline["memory_blocks"]]
    assert len(baseline_ids) == 1

    for i in range(7):
        client.post(f"/session/{session_id}/prompt", json={"agent_slot": 1, "user_text": f"u{i}"})

    after = client.get(f"/session/{session_id}").json()
    after_ids = [block["block_id"] for block in after["memory_blocks"]]

    assert len(after_ids) == 2
    assert baseline_ids[0] in after_ids
    assert len(set(after_ids)) == 2


def test_state_transitions_match_spec(client: TestClient):
    created = client.post("/session").json()
    session_id = created["session_id"]
    assert created["state"] == "DRAFT_TAB1"

    saved = client.put(f"/session/{session_id}/tab1", json=mk2_tab1_payload())
    assert saved.status_code == 200

    locked = client.post(f"/session/{session_id}/lock").json()
    assert locked["state"] == "ACTIVE"

    end = client.post(f"/session/{session_id}/end").json()
    assert end["state"] == "ENDED"

    client.put(f"/session/{session_id}/narrative-agent", json={"selected_player_id": "Joe"})
    build = client.post(f"/session/{session_id}/build-narrative")
    assert build.status_code == 200

    detail = client.get(f"/session/{session_id}").json()
    assert detail["session"]["state"] == "ENDED"

    reset = client.post(f"/session/{session_id}/reset").json()
    assert reset["state"] == "DRAFT_TAB1"
    detail2 = client.get(f"/session/{session_id}").json()
    assert detail2["session"]["prompt_index"] == 0


def test_travel_loads_predefined_combat_encounter(client: TestClient):
    session_id = create_and_lock_session(client)

    travel = client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-1",
            "location_name": "The Thaw Gate",
            "location_description": "A cold gate.",
        },
    )

    assert travel.status_code == 200
    detail = client.get(f"/session/{session_id}").json()
    assert detail["session"]["encounter_state"]["encounter_type"] == "combat"
    assert detail["session"]["encounter_state"]["status"] == "combat_active"
    assert detail["session"]["opposition_state"]["active"] is True
    assert detail["session"]["combat_state"]["in_combat"] is True
    assert "opp:12" in detail["session"]["combat_state"]["initiative_order"]
    encounter_events = [event for event in detail["events"] if event["json_payload"].get("source") == "encounter_start"]
    assert encounter_events
    assert "Opposition appears" in encounter_events[0]["text"]


def test_combat_prompting_is_locked_to_active_initiative(client: TestClient):
    session_id = create_and_lock_session(client)
    client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-1",
            "location_name": "The Thaw Gate",
            "location_description": "A cold gate.",
        },
    )
    detail = client.get(f"/session/{session_id}").json()
    active = detail["session"]["combat_state"]["initiative_order"][detail["session"]["combat_state"]["turn_index"]]
    wrong_slot = 1
    if active == "pc:1":
        wrong_slot = 2
    if active == "opp:12":
        wrong_slot = 1

    response = client.post(f"/session/{session_id}/prompt", json={"agent_slot": wrong_slot, "user_text": "Act out of turn."})

    assert response.status_code == 400
    assert "initiative" in response.json()["detail"].lower()


def test_jannet_wizard_starts_with_stacked_fireball_scrolls_and_consumes_one(client: TestClient):
    created = client.post("/session").json()
    session_id = created["session_id"]
    assert client.put(f"/session/{session_id}/tab1", json=jannet_wizard_payload()).status_code == 200
    assert client.post(f"/session/{session_id}/lock").status_code == 200

    detail = client.get(f"/session/{session_id}").json()
    jannet = next(member for member in detail["tab1"]["party"] if member["player_id"] == "Jannet")
    assert "Fireball Scroll x10" in jannet["inventory"]

    client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-1",
            "location_name": "The Thaw Gate",
            "location_description": "A cold gate.",
        },
    )
    before_scroll = client.get(f"/session/{session_id}").json()
    before_instances = {
        instance["monster_id"]: instance["current_hp"]
        for instance in before_scroll["session"]["opposition_state"]["instances"]
        if not instance["is_dead"]
    }
    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        session.combat_state = {
            **session.combat_state,
            "in_combat": True,
            "turn_index": 0,
            "initiative_order": ["pc:4", "opp:12"],
            "initiative_values": {"pc:4": 20, "opp:12": 10},
        }
        db.commit()
        use_item(db, session_id, 4, "Fireball Scroll")

    after = client.get(f"/session/{session_id}").json()
    jannet_after = next(member for member in after["tab1"]["party"] if member["player_id"] == "Jannet")
    assert "Fireball Scroll x9" in jannet_after["inventory"]
    assert "Fireball Scroll x10" not in jannet_after["inventory"]
    fireball_damage_events = [
        event for event in after["events"]
        if event["kind"] == "hp_changed" and event["json_payload"].get("amount") == 100
    ]
    assert len(fireball_damage_events) == len(before_instances)
    assert after["session"]["opposition_state"]["active"] is False
    assert after["session"]["combat_state"]["in_combat"] is False
    assert after["session"]["encounter_state"]["status"] == "resolved"


def test_fireball_scroll_resolves_even_if_model_labels_it_as_spell():
    payload = {
        "agent_identity": {"slot": 4, "name": "Jannet"},
        "class_sheet": {"class_id": "Wizard", "inventory": ["Fireball Scroll x10"]},
        "mechanical_resolution_hint": {
            "actor_id": "pc:4",
            "visible_monster_targets": [
                {"target_id": "monster-a", "target_type": "monster", "name": "Monster-One", "armor_class": 13, "current_hp": 16, "hp_max": 16},
                {"target_id": "monster-b", "target_type": "monster", "name": "Monster-Two", "armor_class": 13, "current_hp": 16, "hp_max": 16},
            ],
            "available_actions": [{"action_type": "USE_ITEM", "ability": "FIREBALL_SCROLL", "display_name": "Fireball Scroll x10"}],
        },
    }

    result = resolve_actions_for_payload(
        payload,
        {
            "actions": [
                {"actor_id": "pc:4", "target_id": "monster-a", "action_type": "SPELL", "ability": "FIREBALL_SCROLL"},
                {"actor_id": "pc:4", "target_id": "monster-b", "action_type": "SPELL", "ability": "FIREBALL_SCROLL"},
            ]
        },
    )

    assert result["errors"] == []
    assert all(action["success"] for action in result["results"])
    changes = result["state_changes"][0]["targets"]
    damaged_targets = {target["target_id"] for target in changes if target["target_type"] == "monster"}
    assert damaged_targets == {"monster-a", "monster-b"}
    inventory_removes = [target for target in changes if target["target_type"] == "player"]
    assert len(inventory_removes) == 2


def test_downed_combatant_is_skipped_but_returns_to_original_order_when_healed(client: TestClient):
    session_id = create_and_lock_session(client)
    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        session.combat_state = {
            "in_combat": True,
            "round": 1,
            "turn_index": 0,
            "initiative_order": ["pc:1", "pc:4", "pc:2"],
            "initiative_values": {"pc:1": 20, "pc:4": 15, "pc:2": 10},
            "acted_this_round": {},
        }
        db.add(
            Event(
                session_id=session_id,
                prompt_index=1,
                role=EventRole.SYSTEM,
                kind=EventKind.DAMAGE_APPLIED,
                text="Jannet takes 99 damage.",
                json_payload={"target_type": "player", "target_slot": 4, "amount": 99, "source": "test"},
            )
        )
        db.commit()

        session = get_session_or_404(db, session_id)
        _advance_combat_turn(db, session, "pc:1")
        db.commit()
        assert session.combat_state["initiative_order"] == ["pc:1", "pc:4", "pc:2"]
        assert session.combat_state["turn_index"] == 2
        assert session.combat_state["acted_this_round"]["pc:4"] is True

        db.add(
            Event(
                session_id=session_id,
                prompt_index=2,
                role=EventRole.SYSTEM,
                kind=EventKind.DAMAGE_APPLIED,
                text="Jannet heals 10 HP.",
                json_payload={"target_type": "player", "target_slot": 4, "amount": -10, "source": "test"},
            )
        )
        db.commit()

        session = get_session_or_404(db, session_id)
        _advance_combat_turn(db, session, "pc:2")
        db.commit()
        assert session.combat_state["round"] == 2
        assert session.combat_state["turn_index"] == 0
        assert session.combat_state["acted_this_round"] == {}

        _advance_combat_turn(db, session, "pc:1")
        db.commit()
        assert session.combat_state["turn_index"] == 1
        assert session.combat_state["initiative_order"][session.combat_state["turn_index"]] == "pc:4"


def test_revived_combatant_whose_turn_passed_waits_until_next_round(client: TestClient):
    session_id = create_and_lock_session(client)
    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        session.combat_state = {
            "in_combat": True,
            "round": 1,
            "turn_index": 2,
            "initiative_order": ["pc:4", "pc:1", "pc:2"],
            "initiative_values": {"pc:4": 20, "pc:1": 15, "pc:2": 10},
            "acted_this_round": {"pc:1": True},
        }
        db.add(
            Event(
                session_id=session_id,
                prompt_index=1,
                role=EventRole.SYSTEM,
                kind=EventKind.DAMAGE_APPLIED,
                text="Jannet takes 99 damage.",
                json_payload={"target_type": "player", "target_slot": 4, "amount": 99, "source": "test"},
            )
        )
        db.commit()

        session = get_session_or_404(db, session_id)
        _append_state_change(db, session, 2, target_type="player", target_slot=4, kind="healing", amount=10, source="test")
        db.commit()
        assert session.combat_state["acted_this_round"]["pc:4"] is True

        _advance_combat_turn(db, session, "pc:2")
        db.commit()
        assert session.combat_state["round"] == 2
        assert session.combat_state["turn_index"] == 0
        assert session.combat_state["acted_this_round"] == {}


def test_long_rest_is_blocked_while_living_opposition_is_active(client: TestClient):
    session_id = create_and_lock_session(client)
    client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-1",
            "location_name": "The Thaw Gate",
            "location_description": "A cold gate.",
        },
    )

    response = client.post(f"/session/{session_id}/long-rest")

    assert response.status_code == 400
    assert "Opposition is active" in response.json()["detail"]


def test_travel_is_blocked_while_combat_is_active(client: TestClient):
    session_id = create_and_lock_session(client)
    client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-1",
            "location_name": "The Thaw Gate",
            "location_description": "A cold gate.",
        },
    )

    response = client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-2",
            "location_name": "Frost-Choked Hall",
            "location_description": "A nearby hall.",
        },
    )

    assert response.status_code == 400
    assert "combat is active" in response.json()["detail"]


def test_east_marsh_arrival_stealth_rolls_for_each_player_and_logs_results(client: TestClient):
    created = client.post("/session").json()
    session_id = created["session_id"]
    assert client.put(f"/session/{session_id}/tab1", json=east_marsh_jannet_wizard_payload()).status_code == 200
    assert client.post(f"/session/{session_id}/lock").status_code == 200

    response = client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-1",
            "location_name": "The Blackwater Approach",
            "location_description": "A marsh approach.",
        },
    )

    assert response.status_code == 200
    detail = client.get(f"/session/{session_id}").json()
    stealth_rolls = [
        event for event in detail["events"]
        if event["kind"] == "dice_roll" and event["json_payload"].get("source") == "arrival_stealth"
    ]
    assert len(stealth_rolls) == 4
    stealth_summary = [
        event for event in detail["events"]
        if event["kind"] == "transcript" and event["json_payload"].get("source") == "arrival_stealth"
    ]
    assert stealth_summary
    assert "Stealth infiltration checks" in stealth_summary[0]["text"]


def test_east_marsh_boss_deaths_from_fireball_complete_objective(client: TestClient):
    created = client.post("/session").json()
    session_id = created["session_id"]
    assert client.put(f"/session/{session_id}/tab1", json=east_marsh_jannet_wizard_payload()).status_code == 200
    assert client.post(f"/session/{session_id}/lock").status_code == 200

    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        session.current_location_id = "loc-4"
        session.current_location_name = "Supply Cache Pit"
        mission_state = dict(session.mission_objective_state or {})
        mission_state["allowed_location_ids"] = ["loc-5"]
        session.mission_objective_state = mission_state
        db.commit()

    travel = client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-5",
            "location_name": "The War Leader's Tent",
            "location_description": "The boss tent.",
        },
    )
    assert travel.status_code == 200

    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        session.combat_state = {
            **session.combat_state,
            "in_combat": True,
            "turn_index": 0,
            "initiative_order": ["pc:4", "opp:12"],
            "initiative_values": {"pc:4": 20, "opp:12": 10},
            "acted_this_round": {},
        }
        db.commit()
        use_item(db, session_id, 4, "Fireball Scroll")

    detail = client.get(f"/session/{session_id}").json()
    assert detail["session"]["mission_objective_state"]["complete"] is True
    assert detail["session"]["mission_objective_state"]["boss_defeated"] is True
    assert detail["session"]["combat_state"]["in_combat"] is False


def test_old_people_barrow_puzzle_door_failure_applies_damage(client: TestClient):
    created = client.post("/session").json()
    session_id = created["session_id"]
    assert client.put(f"/session/{session_id}/tab1", json=old_people_barrow_payload()).status_code == 200
    assert client.post(f"/session/{session_id}/lock").status_code == 200

    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        session.current_location_id = "loc-4"
        session.current_location_name = "Puzzle Door"
        session.encounter_state = {
            "active": True,
            "status": "blocking",
            "location_id": "loc-4",
            "encounter_type": "hazard",
            "encounter_name": "Puzzle Door",
            "definition": {"type": "hazard", "name": "Puzzle Door", "hazard": "puzzle_door", "blocks_travel_to": ["loc-5"]},
            "hazard": {
                "hazard_id": "puzzle_door",
                "name": "Puzzle Door",
                "mode": "global",
                "required_successes": 3,
                "global_successes": 2,
                "global_failures": 0,
                "status": "blocking",
            },
        }
        _apply_hazard_skill_result(db, session, 1, 1, {"action_type": "SKILL", "success": False, "attack_total": 7})
        db.commit()

    detail = client.get(f"/session/{session_id}").json()
    damage_events = [
        event for event in detail["events"]
        if event["kind"] == "damage_applied" and event["json_payload"].get("source") == "hazard_skill"
    ]
    assert damage_events
    assert detail["session"]["encounter_state"]["hazard"]["global_failures"] == 1


def test_old_people_barrow_puzzle_door_blocks_burial_vault_until_cleared(client: TestClient):
    created = client.post("/session").json()
    session_id = created["session_id"]
    assert client.put(f"/session/{session_id}/tab1", json=old_people_barrow_payload()).status_code == 200
    assert client.post(f"/session/{session_id}/lock").status_code == 200

    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        session.current_location_id = "loc-4"
        session.current_location_name = "Puzzle Door"
        mission_state = dict(session.mission_objective_state or {})
        mission_state["allowed_location_ids"] = ["loc-2", "loc-5"]
        session.mission_objective_state = mission_state
        session.encounter_state = {
            "active": True,
            "status": "in_progress",
            "location_id": "loc-4",
            "encounter_type": "hazard",
            "encounter_name": "Puzzle Door",
            "definition": {"type": "hazard", "name": "Puzzle Door", "hazard": "puzzle_door", "blocks_travel_to": ["loc-5"]},
            "hazard": {"hazard_id": "puzzle_door", "name": "Puzzle Door", "mode": "global", "required_successes": 3, "global_successes": 2, "status": "in_progress"},
        }
        db.commit()

    blocked = client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-5",
            "location_name": "The Burial Vault",
            "location_description": "The room beyond the sealed door.",
        },
    )

    assert blocked.status_code == 400
    assert "Clear Puzzle Door" in blocked.json()["detail"]


def test_collecting_taxes_awards_one_quest_gold_drop_per_combat(client: TestClient):
    created = client.post("/session").json()
    session_id = created["session_id"]
    assert client.put(f"/session/{session_id}/tab1", json=collecting_taxes_payload()).status_code == 200
    assert client.post(f"/session/{session_id}/lock").status_code == 200

    travel = client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-1",
            "location_name": "Narrow Bridge Toll",
            "location_description": "A toll ambush on the road.",
        },
    )
    assert travel.status_code == 200

    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        session.combat_state = {
            **session.combat_state,
            "in_combat": True,
            "turn_index": 0,
            "initiative_order": ["pc:4", "opp:12"],
            "initiative_values": {"pc:4": 20, "opp:12": 10},
            "acted_this_round": {},
        }
        db.commit()
        use_item(db, session_id, 4, "Fireball Scroll")

    detail = client.get(f"/session/{session_id}").json()
    gained_events = [event for event in detail["events"] if event["kind"] == "inventory_gained"]
    quest_gold = [
        event for event in gained_events
        if event["json_payload"].get("source") == "mission_objective" and str(event["json_payload"].get("item", "")).endswith("gp")
    ]
    encounter_gold = [
        event for event in gained_events
        if event["json_payload"].get("source") == "encounter_drop" and str(event["json_payload"].get("item", "")).endswith("gp")
    ]
    assert len(quest_gold) == 1
    awarded = int(str(quest_gold[0]["json_payload"]["item"]).removesuffix("gp"))
    assert 50 <= awarded <= 125
    assert encounter_gold == []


def test_telas_wagons_mud_stuck_wagon_blocks_forward_travel_until_cleared(client: TestClient):
    created = client.post("/session").json()
    session_id = created["session_id"]
    assert client.put(f"/session/{session_id}/tab1", json=telas_wagons_payload()).status_code == 200
    assert client.post(f"/session/{session_id}/lock").status_code == 200

    travel = client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-1",
            "location_name": "Western Tundra Stretch",
            "location_description": "The lead wagon is stuck in deep mud.",
        },
    )
    assert travel.status_code == 200

    blocked = client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-2",
            "location_name": "Barrow Approach Scouts",
            "location_description": "The road ahead.",
        },
    )

    assert blocked.status_code == 400
    assert "Clear Mud-Stuck Wagon" in blocked.json()["detail"]

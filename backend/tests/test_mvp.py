import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./test_story_engine.db"

from app import main as main_module  # noqa: E402
from app import services as services_module  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Event, EventKind, EventRole  # noqa: E402
from app.services import _advance_combat_turn, _append_state_change, _apply_hazard_skill_result, dismiss_opposition, get_session_or_404, resolve_actions_for_payload, use_item  # noqa: E402


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


def test_magic_missile_spends_mp_and_fails_at_zero_mp():
    payload = {
        "agent_identity": {"slot": 4, "name": "Jannet"},
        "class_sheet": {"class_id": "Wizard", "inventory": [], "mp_current": 1, "mp_max": 6},
        "mechanical_resolution_hint": {
            "actor_id": "pc:4",
            "visible_monster_targets": [
                {"target_id": "monster-a", "target_type": "monster", "name": "Monster-One", "armor_class": 13, "current_hp": 16, "hp_max": 16},
            ],
            "available_actions": [{"action_type": "SPELL", "ability": "MAGIC_MISSILE", "display_name": "Magic Missile"}],
        },
    }

    result = resolve_actions_for_payload(
        payload,
        {"actions": [{"actor_id": "pc:4", "target_id": "monster-a", "action_type": "SPELL", "ability": "MAGIC_MISSILE"}]},
    )

    assert result["results"][0]["success"] is True
    assert any(
        change["kind"] == "mp_spend" and change["amount"] == 1
        for target in result["state_changes"][0]["targets"]
        for change in target["changes"]
    )

    payload["class_sheet"]["mp_current"] = 0
    failed = resolve_actions_for_payload(
        payload,
        {"actions": [{"actor_id": "pc:4", "target_id": "monster-a", "action_type": "SPELL", "ability": "MAGIC_MISSILE"}]},
    )

    assert failed["results"][0]["success"] is False
    assert "insufficient MP" in failed["results"][0]["reason"]


def test_potions_heal_hp_and_restore_mp_to_selected_targets(client: TestClient):
    session_id = create_and_lock_session(client)
    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        _append_state_change(db, session, 1, target_type="player", target_slot=1, kind="damage", amount=6, source="test")
        _append_state_change(db, session, 1, target_type="player", target_slot=3, kind="mp_spend", amount=4, source="test")
        _append_state_change(db, session, 1, target_type="player", target_slot=4, kind="inventory_add", value="Potion of Healing", source="test")
        _append_state_change(db, session, 1, target_type="player", target_slot=4, kind="inventory_add", value="Potion of Spell Restore", source="test")
        db.commit()

        use_item(db, session_id, 4, "Potion of Healing", "pc:1")
        use_item(db, session_id, 4, "Potion of Spell Restore", "pc:3")

    detail = client.get(f"/session/{session_id}").json()
    joe = next(member for member in detail["tab1"]["party"] if member["slot"] == 1)
    tom = next(member for member in detail["tab1"]["party"] if member["slot"] == 3)
    jannet = next(member for member in detail["tab1"]["party"] if member["slot"] == 4)
    assert joe["hp_current"] > 6
    assert tom["mp_current"] == tom["mp_max"]
    assert "Potion of Healing" not in jannet["inventory"]
    assert "Potion of Spell Restore" not in jannet["inventory"]
    assert any(event["kind"] == "resource_changed" for event in detail["events"])


def test_healing_potion_can_revive_downed_target(client: TestClient):
    session_id = create_and_lock_session(client)
    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        _append_state_change(db, session, 1, target_type="player", target_slot=3, kind="damage", amount=99, source="test")
        _append_state_change(db, session, 1, target_type="player", target_slot=4, kind="inventory_add", value="Potion of Healing", source="test")
        db.commit()

        use_item(db, session_id, 4, "Potion of Healing", "pc:3")

    detail = client.get(f"/session/{session_id}").json()
    target = next(member for member in detail["tab1"]["party"] if member["slot"] == 3)
    healer = next(member for member in detail["tab1"]["party"] if member["slot"] == 4)
    assert target["hp_current"] > 0
    assert "Potion of Healing" not in healer["inventory"]


def test_stackable_potion_awards_dedupe_same_prompt_and_stack_later(client: TestClient):
    session_id = create_and_lock_session(client)
    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        _append_state_change(db, session, 1, target_type="player", target_slot=2, kind="inventory_add", value="Potion Of Healing", source="gm_parser")
        _append_state_change(db, session, 1, target_type="player", target_slot=2, kind="inventory_add", value="Potion of Healing", source="tool")
        _append_state_change(db, session, 2, target_type="player", target_slot=2, kind="inventory_add", value="Potion of Healing", source="test")
        db.commit()

    detail = client.get(f"/session/{session_id}").json()
    annie = next(member for member in detail["tab1"]["party"] if member["slot"] == 2)
    potion_items = [item for item in annie["inventory"] if "potion" in item.lower() and "healing" in item.lower()]
    assert potion_items == ["Potion Of Healing x2"]


def test_opposition_targets_only_living_party_members(client: TestClient):
    session_id = create_and_lock_session(client)
    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        _append_state_change(db, session, 1, target_type="player", target_slot=3, kind="damage", amount=99, source="test")
        session.opposition_state = {
            "active": True,
            "group_id": "test",
            "monster_stats": {"monster_id": "Shadow", "attack_bonus": 4, "attack_text": "Claw. 1d6+2 slashing."},
            "instances": [{"monster_id": "monster-a", "display_name": "Monster-One", "current_hp": 10, "hp_max": 10, "is_dead": False}],
        }
        hint = services_module._build_opposition_mechanical_hint(db, session)

    assert "pc:3" not in {target["target_id"] for target in hint["party_targets"]}


def test_resolver_rejects_attacks_against_downed_players():
    payload = {
        "mechanical_resolution_hint": {
            "party_targets": [
                {"target_id": "pc:1", "target_type": "player", "name": "Joe", "armor_class": 16, "current_hp": 8, "hp_max": 12},
                {"target_id": "pc:3", "target_type": "player", "name": "Tammey", "armor_class": 12, "current_hp": 0, "hp_max": 10},
            ],
            "living_monster_actors": [
                {"actor_id": "monster-a", "name": "Monster-One", "ability": "SHADOW", "attack_formula": "1d20+4", "damage_formula": "1d6+2"}
            ],
        },
    }

    result = resolve_actions_for_payload(
        payload,
        {"actions": [{"actor_id": "monster-a", "target_id": "pc:3", "action_type": "ATTACK", "ability": "SHADOW"}]},
    )

    assert result["retry_required"] is True
    assert result["errors"][0]["kind"] == "invalid_target_state"
    assert "pc:3" not in {target["target_id"] for target in result["errors"][0]["viable_targets"]}


def phase5_payload(class_id: str, status_effects: list[str] | None = None, feature_uses: dict | None = None, current_combat_feature_uses: dict | None = None):
    return {
        "agent_identity": {"slot": 1, "name": "Tester"},
        "class_sheet": {
            "class_id": class_id,
            "inventory": [],
            "mp_current": 6,
            "mp_max": 6,
            "status_effects": status_effects or [],
            "feature_uses": feature_uses or {},
            "current_combat_feature_uses": current_combat_feature_uses or {},
        },
        "opposition_state": {"active": True},
        "mechanical_resolution_hint": {
            "actor_id": "pc:1",
            "ally_targets": [
                {"target_id": "pc:1", "target_type": "player", "slot": 1, "name": "Tester", "armor_class": 15, "current_hp": 8, "hp_max": 12, "mp_current": 6, "mp_max": 6, "status_effects": status_effects or []},
                {"target_id": "pc:2", "target_type": "player", "slot": 2, "name": "Ally", "armor_class": 12, "current_hp": 4, "hp_max": 10, "mp_current": 0, "mp_max": 0, "status_effects": []},
            ],
            "visible_monster_targets": [
                {"target_id": "monster-a", "target_type": "monster", "name": "Monster-One", "armor_class": 10, "current_hp": 10, "hp_max": 16},
                {"target_id": "monster-b", "target_type": "monster", "name": "Monster-Two", "armor_class": 10, "current_hp": 16, "hp_max": 16},
            ],
            "available_actions": [
                {"action_type": "ATTACK", "ability": "LONGSWORD", "display_name": "Longsword", "attack_formula": "1d20+5", "damage_formula": "1d8+3", "damage_type": "slashing"},
                {"action_type": "ATTACK", "ability": "LONGBOW", "display_name": "Longbow", "attack_formula": "1d20+5", "damage_formula": "1d8+3", "damage_type": "piercing"},
                {"action_type": "ATTACK", "ability": "RAPIER", "display_name": "Rapier", "attack_formula": "1d20+5", "damage_formula": "1d8+3", "damage_type": "piercing"},
                {"action_type": "ATTACK", "ability": "SMITE", "display_name": "Smite", "attack_formula": "1d20+5", "damage_formula": "1d8+3", "damage_type": "slashing"},
                {"action_type": "SPELL", "ability": "RAGE", "display_name": "Rage"},
                {"action_type": "SPELL", "ability": "LAY_ON_HANDS", "display_name": "Lay on Hands"},
                {"action_type": "SPELL", "ability": "BLESS", "display_name": "Bless"},
                {"action_type": "SPELL", "ability": "THUNDERWAVE", "display_name": "Thunderwave"},
                {"action_type": "SPELL", "ability": "FIREBOLT", "display_name": "Firebolt"},
                {"action_type": "SPELL", "ability": "BURNING_HANDS", "display_name": "Burning Hands"},
            ],
        },
    }


def test_phase5_fighter_and_ranger_multiattack_rules(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(services_module, "randbelow", lambda sides: sides - 1)
    fighter = resolve_actions_for_payload(
        phase5_payload("Fighter"),
        {"actions": [
            {"actor_id": "pc:1", "target_id": "monster-a", "action_type": "ATTACK", "ability": "LONGSWORD"},
            {"actor_id": "pc:1", "target_id": "monster-b", "action_type": "ATTACK", "ability": "LONGSWORD"},
        ]},
    )
    assert fighter["retry_required"] is False

    invalid_fighter = resolve_actions_for_payload(
        phase5_payload("Fighter"),
        {"actions": [
            {"actor_id": "pc:1", "target_id": "monster-a", "action_type": "ATTACK", "ability": "LONGSWORD"},
            {"actor_id": "pc:1", "target_id": "monster-a", "action_type": "ATTACK", "ability": "LONGSWORD"},
        ]},
    )
    assert invalid_fighter["retry_required"] is True

    ranger = resolve_actions_for_payload(
        phase5_payload("Ranger"),
        {"actions": [
            {"actor_id": "pc:1", "target_id": "monster-a", "action_type": "ATTACK", "ability": "LONGBOW"},
            {"actor_id": "pc:1", "target_id": "monster-a", "action_type": "ATTACK", "ability": "LONGBOW"},
        ]},
    )
    assert ranger["retry_required"] is False
    hp_after_values = [result["target_hp_after"] for result in ranger["results"] if result["hit"]]
    assert hp_after_values == sorted(hp_after_values, reverse=True)


def test_named_cleave_and_double_nock_expand_to_feature_attacks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(services_module, "randbelow", lambda sides: sides - 1)

    fighter = resolve_actions_for_payload(
        phase5_payload("Fighter"),
        {"actions": [{"actor_id": "pc:1", "target_id": "monster-a", "action_type": "ATTACK", "ability": "CLEAVE"}]},
    )
    assert fighter["retry_required"] is False
    assert len(fighter["results"]) == 2
    assert {result["target_id"] for result in fighter["results"]} == {"monster-a", "monster-b"}
    assert all(result["ability"] == "CLEAVE" for result in fighter["results"])

    ranger = resolve_actions_for_payload(
        phase5_payload("Ranger"),
        {"actions": [{"actor_id": "pc:1", "target_id": "monster-a", "action_type": "SPELL", "ability": "DOUBLE_NOCK"}]},
    )
    assert ranger["retry_required"] is False
    assert len(ranger["results"]) == 2
    assert [result["target_id"] for result in ranger["results"]] == ["monster-a", "monster-a"]
    assert all(result["ability"] == "DOUBLE_NOCK" for result in ranger["results"])


def test_phase5_rogue_skill_expert_rolls_with_advantage(monkeypatch: pytest.MonkeyPatch):
    rolls = iter([2, 18])
    monkeypatch.setattr(services_module, "randbelow", lambda sides: next(rolls))

    result = resolve_actions_for_payload(
        phase5_payload("Rogue"),
        {"actions": [{"actor_id": "pc:1", "target_id": "pc:1", "action_type": "SKILL", "ability": "PERCEPTION"}]},
    )

    assert len(result["rolls"]) == 2
    assert result["results"][0]["attack_total"] == 21
    assert result["results"][0]["success"] is True


def test_phase5_rage_adds_status_and_blocks_third_use():
    rage = resolve_actions_for_payload(
        phase5_payload("Barbarian", feature_uses={"rage": 1}),
        {"actions": [{"actor_id": "pc:1", "target_id": "pc:1", "action_type": "SPELL", "ability": "RAGE"}]},
    )
    assert rage["results"][0]["success"] is True
    changes = [change for target in rage["state_changes"][0]["targets"] for change in target["changes"]]
    assert {"kind": "status_add", "amount": 0, "value": "Rage"} in changes
    assert {"kind": "feature_use", "amount": 1, "value": "rage"} in changes

    blocked = resolve_actions_for_payload(
        phase5_payload("Barbarian", feature_uses={"rage": 2}),
        {"actions": [{"actor_id": "pc:1", "target_id": "pc:1", "action_type": "SPELL", "ability": "RAGE"}]},
    )
    assert blocked["results"][0]["success"] is False


def test_phase5_smite_lay_on_hands_and_bless_use_limits():
    smite_used = resolve_actions_for_payload(
        phase5_payload("Paladin", current_combat_feature_uses={"smite": 1}),
        {"actions": [{"actor_id": "pc:1", "target_id": "monster-a", "action_type": "ATTACK", "ability": "SMITE"}]},
    )
    assert smite_used["results"][0]["success"] is False

    lay = resolve_actions_for_payload(
        phase5_payload("Paladin"),
        {"actions": [{"actor_id": "pc:1", "target_id": "pc:2", "action_type": "SPELL", "ability": "LAY_ON_HANDS"}]},
    )
    assert lay["results"][0]["healing"] == 5
    assert any(
        change["kind"] == "feature_use" and change["value"] == "lay_on_hands"
        for target in lay["state_changes"][0]["targets"]
        for change in target["changes"]
    )

    bless = resolve_actions_for_payload(
        phase5_payload("Cleric"),
        {"actions": [{"actor_id": "pc:1", "target_id": "pc:1", "action_type": "SPELL", "ability": "BLESS"}]},
    )
    assert bless["results"][0]["success"] is True
    assert sum(
        1
        for target in bless["state_changes"][0]["targets"]
        for change in target["changes"]
        if change["kind"] == "status_add" and change["value"] == "Bless"
    ) == 2


def test_phase5_new_spells_are_backend_resolved(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(services_module, "randbelow", lambda sides: sides - 1)

    firebolt = resolve_actions_for_payload(
        phase5_payload("Wizard"),
        {"actions": [{"actor_id": "pc:1", "target_id": "monster-a", "action_type": "SPELL", "ability": "FIREBOLT"}]},
    )
    assert firebolt["results"][0]["success"] is True
    assert firebolt["results"][0]["damage"] == 10

    burning = resolve_actions_for_payload(
        phase5_payload("Wizard"),
        {"actions": [{"actor_id": "pc:1", "target_id": "monster-a", "action_type": "SPELL", "ability": "BURNING_HANDS"}]},
    )
    assert burning["results"][0]["success"] is True
    assert len([target for target in burning["state_changes"][0]["targets"] if target["target_type"] == "monster"]) == 2

    thunderwave = resolve_actions_for_payload(
        phase5_payload("Druid"),
        {"actions": [{"actor_id": "pc:1", "target_id": "monster-a", "action_type": "SPELL", "ability": "THUNDERWAVE"}]},
    )
    assert thunderwave["results"][0]["success"] is True
    assert any(
        change["kind"] == "mp_spend"
        for target in thunderwave["state_changes"][0]["targets"]
        for change in target["changes"]
    )


def test_thunderwave_duplicate_actions_resolve_only_one_aoe(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(services_module, "randbelow", lambda sides: sides - 1)

    result = resolve_actions_for_payload(
        phase5_payload("Druid"),
        {
            "actions": [
                {"actor_id": "pc:1", "target_id": "monster-a", "action_type": "SPELL", "ability": "THUNDERWAVE"},
                {"actor_id": "pc:1", "target_id": "monster-b", "action_type": "SPELL", "ability": "THUNDERWAVE"},
                {"actor_id": "pc:1", "target_id": "monster-a", "action_type": "SPELL", "ability": "THUNDERWAVE"},
                {"actor_id": "pc:1", "target_id": "monster-b", "action_type": "SPELL", "ability": "THUNDERWAVE"},
            ]
        },
    )

    monster_targets = [target for target in result["state_changes"][0]["targets"] if target["target_type"] == "monster"]
    mp_spends = [
        change
        for target in result["state_changes"][0]["targets"]
        for change in target["changes"]
        if change["kind"] == "mp_spend"
    ]
    assert len(monster_targets) == 2
    assert all(target["changes"][0]["amount"] == 16 for target in monster_targets)
    assert len(mp_spends) == 1
    assert len(result["results"]) == 1
    assert len(result["results"][0]["per_target_results"]) == 2


def test_action_result_guides_agent_when_combat_ends(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(services_module, "randbelow", lambda sides: sides - 1)
    payload = phase5_payload("Wizard")
    payload["mechanical_resolution_hint"]["visible_monster_targets"] = [
        {"target_id": "monster-a", "target_type": "monster", "name": "Monster-One", "armor_class": 10, "current_hp": 4, "hp_max": 16},
    ]

    result = resolve_actions_for_payload(
        payload,
        {"actions": [{"actor_id": "pc:1", "target_id": "monster-a", "action_type": "SPELL", "ability": "FIREBOLT"}]},
    )

    assert result["combat_ended"] is True
    assert "ends the combat" in result["combat_end_guidance"]


def test_action_result_does_not_end_combat_when_monster_survives(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(services_module, "randbelow", lambda sides: 0)
    payload = phase5_payload("Wizard")
    payload["mechanical_resolution_hint"]["visible_monster_targets"] = [
        {"target_id": "monster-a", "target_type": "monster", "name": "Monster-One", "armor_class": 10, "current_hp": 16, "hp_max": 16},
    ]

    result = resolve_actions_for_payload(
        payload,
        {"actions": [{"actor_id": "pc:1", "target_id": "monster-a", "action_type": "SPELL", "ability": "FIREBOLT"}]},
    )

    assert result["combat_ended"] is False
    assert result["combat_end_guidance"] == ""


def test_sneak_attack_result_tells_agent_bonus_damage_applied(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(services_module, "randbelow", lambda sides: sides - 1)

    result = resolve_actions_for_payload(
        phase5_payload("Rogue"),
        {"actions": [{"actor_id": "pc:1", "target_id": "monster-a", "action_type": "ATTACK", "ability": "RAPIER"}]},
    )

    assert result["results"][0]["success"] is True
    assert "Sneak Attack applied" in result["results"][0]["bonus_damage_note"]


def test_tool_inventory_cannot_consume_mechanical_potion_without_action_result(client: TestClient):
    session_id = create_and_lock_session(client)
    generation = services_module.GenerationResult(
        content="I use the potion.",
        pending_roll_results=[],
        pending_action_results=[],
        pending_state_changes=[
            {
                "source": "tool",
                "targets": [
                    {
                        "target_type": "player",
                        "target_slot": 2,
                        "changes": [{"kind": "inventory_remove", "amount": 0, "value": "Potion of Spell Restore"}],
                    }
                ],
            }
        ],
        continuation=None,
    )
    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        _append_state_change(db, session, 1, target_type="player", target_slot=2, kind="inventory_add", value="Potion of Spell Restore", source="test")
        db.commit()
        session = get_session_or_404(db, session_id)
        services_module._apply_generation_result(db, session, 2, 2, generation)
        db.commit()

    detail = client.get(f"/session/{session_id}").json()
    annie = next(member for member in detail["tab1"]["party"] if member["slot"] == 2)
    assert "Potion of Spell Restore" in annie["inventory"]


def test_tool_inventory_allows_mechanical_potion_transfer(client: TestClient):
    session_id = create_and_lock_session(client)
    generation = services_module.GenerationResult(
        content="I hand over the potion.",
        pending_roll_results=[],
        pending_action_results=[],
        pending_state_changes=[
            {
                "source": "tool",
                "targets": [
                    {
                        "target_type": "player",
                        "target_slot": 2,
                        "changes": [{"kind": "inventory_remove", "amount": 0, "value": "Potion of Spell Restore"}],
                    },
                    {
                        "target_type": "player",
                        "target_slot": 3,
                        "changes": [{"kind": "inventory_add", "amount": 0, "value": "Potion of Spell Restore"}],
                    },
                ],
            }
        ],
        continuation=None,
    )
    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        _append_state_change(db, session, 1, target_type="player", target_slot=2, kind="inventory_add", value="Potion of Spell Restore", source="test")
        db.commit()
        session = get_session_or_404(db, session_id)
        services_module._apply_generation_result(db, session, 2, 2, generation)
        db.commit()

    detail = client.get(f"/session/{session_id}").json()
    annie = next(member for member in detail["tab1"]["party"] if member["slot"] == 2)
    tammey = next(member for member in detail["tab1"]["party"] if member["slot"] == 3)
    assert "Potion of Spell Restore" not in annie["inventory"]
    assert "Potion of Spell Restore" in tammey["inventory"]


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


def test_long_rest_restores_mp_when_safe(client: TestClient):
    session_id = create_and_lock_session(client)
    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        _append_state_change(db, session, 1, target_type="player", target_slot=3, kind="mp_spend", amount=4, source="test")
        db.commit()

    response = client.post(f"/session/{session_id}/long-rest")

    assert response.status_code == 200
    detail = client.get(f"/session/{session_id}").json()
    wizard = next(member for member in detail["tab1"]["party"] if member["slot"] == 3)
    assert wizard["mp_current"] == wizard["mp_max"]
    assert any(event["kind"] == "resource_changed" and event["json_payload"].get("source") == "long_rest" for event in detail["events"])


def test_failed_adventure_long_rest_spawns_configured_ambush(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(services_module, "randbelow", lambda sides: sides - 1)
    created = client.post("/session").json()
    session_id = created["session_id"]
    assert client.put(f"/session/{session_id}/tab1", json=old_people_barrow_payload()).status_code == 200
    assert client.post(f"/session/{session_id}/lock").status_code == 200
    travel = client.post(
        f"/session/{session_id}/travel",
        json={
            "location_id": "loc-1",
            "location_name": "The Frost-Cleft Entrance",
            "location_description": "A barrow entrance.",
        },
    )
    assert travel.status_code == 200

    response = client.post(f"/session/{session_id}/long-rest")

    assert response.status_code == 200
    detail = client.get(f"/session/{session_id}").json()
    assert detail["session"]["opposition_state"]["active"] is True
    assert [instance["monster_type"] for instance in detail["session"]["opposition_state"]["instances"]] == ["Zombie", "Zombie", "Zombie", "Zombie"]
    assert any("ambushed" in event["text"] for event in detail["events"])


def test_failed_flee_hands_turn_to_opposition_and_locks_button(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(services_module, "randbelow", lambda sides: sides - 1)
    session_id = create_and_lock_session(client)
    with SessionLocal() as db:
        session = get_session_or_404(db, session_id)
        session.opposition_state = {
            "active": True,
            "group_id": "test",
            "initiative_id": "opp:12",
            "monster_type": "Bandit",
            "monster_stats": {"ac": 12, "hp": 11},
            "instances": [
                {"monster_id": "monster-a", "display_name": "Monster-One", "monster_type": "Bandit", "monster_stats": {"ac": 12, "hp": 11}, "current_hp": 11, "hp_max": 11, "is_dead": False, "status_effects": []}
            ],
            "cleanup_after": "",
        }
        session.combat_state = {
            "in_combat": True,
            "round": 1,
            "turn_index": 0,
            "initiative_order": ["pc:1", "pc:2", "opp:12"],
            "initiative_values": {"pc:1": 20, "pc:2": 15, "opp:12": 10},
            "acted_this_round": {},
        }
        db.commit()
        dismiss_opposition(db, session_id)

        session = get_session_or_404(db, session_id)
        assert session.opposition_state["active"] is True
        assert session.opposition_state["flee_failed"] is True
        assert session.combat_state["initiative_order"][session.combat_state["turn_index"]] == "opp:12"


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

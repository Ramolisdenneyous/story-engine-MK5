import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./test_story_engine.db"

from app import main as main_module  # noqa: E402
from app.db import Base, engine  # noqa: E402


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
    assert detail2["events"] == []
    assert detail2["memory_blocks"] == []

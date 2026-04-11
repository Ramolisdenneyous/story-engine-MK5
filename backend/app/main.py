from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .game_data import ADVENTURES, ADVENTURE_SELECTION_IMAGE_FILE, CLASSES, DEFAULT_IMAGE_FILE, MAP_IMAGE_FILE, MONSTERS, PLAYERS, VALASKA_PRESET_ID
from .schemas import (
    CatalogResponse,
    CombatStateOut,
    DiceBatchRequest,
    DiceRollRequest,
    DiceRollResult,
    ImageGenerateResponse,
    InitiativeResponse,
    MonsterReferenceOut,
    NarrativeAgentRequest,
    NarrativeBuildResponse,
    OppositionSpawnRequest,
    PromptRequest,
    PromptResponse,
    SessionCreateResponse,
    SessionDetailResponse,
    SessionSummary,
    TravelRequest,
    TTSRequest,
    Tab1InputPayload,
    Tab1InputResponse,
)
from .services import (
    asset_url,
    build_narrative,
    create_session,
    dismiss_opposition,
    end_chapter,
    generate_scene_image,
    get_session_detail,
    lock_tab1,
    prompt_agent,
    reset_session,
    roll_dice_batch_for_session,
    roll_dice_for_session,
    roll_initiative,
    save_narrative_agent,
    save_tab1,
    serialize_adventure,
    serialize_monster_reference,
    spawn_opposition,
    synthesize_player_reply_tts,
    take_long_rest,
    travel_to_location,
)

app = FastAPI(title="Story Engine MK2", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ASSET_PATH = Path("/app/docs/images")
if ASSET_PATH.exists():
    app.mount("/assets", StaticFiles(directory=ASSET_PATH), name="assets")

MUSIC_PATH = Path("/app/docs/music")
if MUSIC_PATH.exists():
    app.mount("/music", StaticFiles(directory=MUSIC_PATH), name="music")


def _ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        statements = [
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS current_location_text TEXT DEFAULT '' NOT NULL",
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS combat_state JSON DEFAULT '{}' NOT NULL",
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS opposition_state JSON DEFAULT '{}' NOT NULL",
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS generated_image JSON DEFAULT '{}' NOT NULL",
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS selected_narrative_player_id VARCHAR(120) DEFAULT '' NOT NULL",
            "ALTER TABLE tab1_inputs ADD COLUMN IF NOT EXISTS preset_id VARCHAR(120) DEFAULT '' NOT NULL",
            "ALTER TABLE tab1_inputs ADD COLUMN IF NOT EXISTS adventure_id VARCHAR(120) DEFAULT '' NOT NULL",
            "ALTER TABLE tab1_inputs ADD COLUMN IF NOT EXISTS selected_player_ids JSON DEFAULT '[]' NOT NULL",
            "ALTER TABLE tab1_inputs ADD COLUMN IF NOT EXISTS class_assignments JSON DEFAULT '{}' NOT NULL",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS kind VARCHAR(32) DEFAULT 'transcript' NOT NULL",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS json_payload JSON DEFAULT '{}' NOT NULL",
        ]
        for statement in statements:
            try:
                conn.execute(text(statement))
            except Exception:
                pass
        enum_statements = [
            "ALTER TYPE eventkind ADD VALUE IF NOT EXISTS 'HP_CHANGED'",
            "ALTER TYPE eventkind ADD VALUE IF NOT EXISTS 'OPPOSITION_SPAWNED'",
            "ALTER TYPE eventkind ADD VALUE IF NOT EXISTS 'MONSTER_DIED'",
            "ALTER TYPE eventkind ADD VALUE IF NOT EXISTS 'OPPOSITION_DISMISSED'",
        ]
        for statement in enum_statements:
            try:
                conn.execute(text(statement))
            except Exception:
                pass


@app.on_event("startup")
def startup() -> None:
    _ensure_schema()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


def _session_summary(session) -> SessionSummary:
    return SessionSummary(
        session_id=session.session_id,
        state=session.state,
        prompt_index=session.prompt_index,
        last_summarized_prompt_index=session.last_summarized_prompt_index,
        tab1_locked=session.tab1_locked,
        combat_state=CombatStateOut(**(session.combat_state or {"in_combat": False, "round": 1, "turn_index": 0, "initiative_order": [], "initiative_values": {}})),
        selected_narrative_player_id=session.selected_narrative_player_id or "",
        opposition_state=(session.opposition_state or None),
    )


def _tab1_response(data: dict) -> Tab1InputResponse:
    tab1 = data["tab1"]
    session = data["session"]
    return Tab1InputResponse(
        preset_id=tab1.preset_id or VALASKA_PRESET_ID,
        adventure_id=tab1.adventure_id or "",
        selected_player_ids=tab1.selected_player_ids,
        class_assignments={int(k): v for k, v in tab1.class_assignments.items()},
        selected_agent_slots=session.selected_agent_slots,
        agent_names={int(k): v for k, v in session.agent_names.items()},
        tab1_locked=session.tab1_locked,
        party=data["party"],
        active_adventure=data["active_adventure"],
    )


@app.get("/catalog", response_model=CatalogResponse)
def get_catalog():
    return CatalogResponse(
        preset_id=VALASKA_PRESET_ID,
        preset_name="Valaska",
        map_image_url=asset_url(MAP_IMAGE_FILE),
        adventure_selection_image_url=asset_url(ADVENTURE_SELECTION_IMAGE_FILE),
        default_image_url=asset_url(DEFAULT_IMAGE_FILE),
        adventures=[serialize_adventure(adventure_id) for adventure_id in ADVENTURES.keys()],
        players=[
            {
                "player_id": player["player_id"],
                "name": player["name"],
                "archetype": player["archetype"],
                "gender": player["gender"],
                "race": player["race"],
                "irl_job": player["irl_job"],
                "keywords": player["keywords"],
                "display_text": player["display_text"],
                "image_url": asset_url(f"Player-{player['player_id']}.jpg"),
            }
            for player in PLAYERS.values()
        ],
        classes=[
            {
                "class_id": cls["class_id"],
                "name": cls["name"],
                "role": cls["role"],
                "armor_class": cls["armor_class"],
                "hp_max": cls["hp_max"],
            }
            for cls in CLASSES.values()
        ],
        monsters=[MonsterReferenceOut(**serialize_monster_reference(monster_id)) for monster_id in sorted(MONSTERS.keys())],
    )


@app.post("/session", response_model=SessionCreateResponse)
def create_session_endpoint(db: Session = Depends(get_db)):
    session = create_session(db)
    return SessionCreateResponse(session_id=session.session_id, state=session.state)


@app.put("/session/{session_id}/tab1", response_model=Tab1InputResponse)
def save_tab1_endpoint(session_id: str, payload: Tab1InputPayload, db: Session = Depends(get_db)):
    try:
        save_tab1(db, session_id, payload.model_dump())
        return _tab1_response(get_session_detail(db, session_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/session/{session_id}/tab1", response_model=Tab1InputResponse)
def get_tab1_endpoint(session_id: str, db: Session = Depends(get_db)):
    try:
        return _tab1_response(get_session_detail(db, session_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/session/{session_id}/lock", response_model=SessionSummary)
def lock_session_endpoint(session_id: str, db: Session = Depends(get_db)):
    try:
        return _session_summary(lock_tab1(db, session_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/prompt", response_model=PromptResponse)
def prompt_endpoint(session_id: str, payload: PromptRequest, db: Session = Depends(get_db)):
    try:
        session, user_event, agent_event, summary_triggered = prompt_agent(db, session_id, payload.agent_slot, payload.user_text)
        return PromptResponse(
            session=_session_summary(session),
            user_event=user_event,
            agent_event=agent_event,
            summary_triggered=summary_triggered,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/travel", response_model=SessionSummary)
def travel_endpoint(session_id: str, payload: TravelRequest, db: Session = Depends(get_db)):
    try:
        return _session_summary(
            travel_to_location(db, session_id, payload.location_id, payload.location_name, payload.location_description)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/spawn-opposition", response_model=SessionSummary)
def spawn_opposition_endpoint(session_id: str, payload: OppositionSpawnRequest, db: Session = Depends(get_db)):
    try:
        return _session_summary(spawn_opposition(db, session_id, payload.monster_type, payload.quantity))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/dismiss-opposition", response_model=SessionSummary)
def dismiss_opposition_endpoint(session_id: str, db: Session = Depends(get_db)):
    try:
        return _session_summary(dismiss_opposition(db, session_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/end", response_model=SessionSummary)
def end_chapter_endpoint(session_id: str, db: Session = Depends(get_db)):
    try:
        return _session_summary(end_chapter(db, session_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.put("/session/{session_id}/narrative-agent", response_model=SessionSummary)
def save_narrative_agent_endpoint(session_id: str, payload: NarrativeAgentRequest, db: Session = Depends(get_db)):
    try:
        return _session_summary(save_narrative_agent(db, session_id, payload.selected_player_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/build-narrative", response_model=NarrativeBuildResponse)
def build_narrative_endpoint(session_id: str, db: Session = Depends(get_db)):
    try:
        draft = build_narrative(db, session_id)
        return NarrativeBuildResponse(draft_id=draft.draft_id, chapter_text=draft.chapter_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/roll-dice", response_model=DiceRollResult)
def roll_dice_endpoint(session_id: str, payload: DiceRollRequest, db: Session = Depends(get_db)):
    try:
        return DiceRollResult(**roll_dice_for_session(db, session_id, payload.formula, payload.label, payload.roller_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/roll-dice-batch", response_model=list[DiceRollResult])
def roll_dice_batch_endpoint(session_id: str, payload: DiceBatchRequest, db: Session = Depends(get_db)):
    try:
        return [DiceRollResult(**item) for item in roll_dice_batch_for_session(db, session_id, [roll.model_dump() for roll in payload.rolls])]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/roll-initiative", response_model=InitiativeResponse)
def roll_initiative_endpoint(session_id: str, db: Session = Depends(get_db)):
    try:
        result = roll_initiative(db, session_id)
        return InitiativeResponse(combat_state=CombatStateOut(**result["combat_state"]), rolls=[DiceRollResult(**roll) for roll in result["rolls"]])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/long-rest", response_model=SessionSummary)
def long_rest_endpoint(session_id: str, db: Session = Depends(get_db)):
    try:
        return _session_summary(take_long_rest(db, session_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/generate-image", response_model=ImageGenerateResponse)
def generate_image_endpoint(session_id: str, db: Session = Depends(get_db)):
    try:
        data = generate_scene_image(db, session_id)
        return ImageGenerateResponse(image_url=data["image_url"], prompt_text=data["prompt_text"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/session/{session_id}/tts")
def tts_endpoint(session_id: str, payload: TTSRequest, db: Session = Depends(get_db)):
    try:
        audio_bytes = synthesize_player_reply_tts(db, session_id, payload.text, payload.player_name)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.post("/session/{session_id}/reset", response_model=SessionSummary)
def reset_endpoint(session_id: str, db: Session = Depends(get_db)):
    try:
        return _session_summary(reset_session(db, session_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/session/{session_id}", response_model=SessionDetailResponse)
def get_session_endpoint(session_id: str, db: Session = Depends(get_db)):
    try:
        data = get_session_detail(db, session_id)
        return SessionDetailResponse(
            session=_session_summary(data["session"]),
            tab1=_tab1_response(data),
            events=data["events"],
            memory_blocks=data["memory_blocks"],
            narrative_drafts=[NarrativeBuildResponse(draft_id=draft.draft_id, chapter_text=draft.chapter_text) for draft in data["narrative_drafts"]],
            image_state=data["image_state"],
            gm_monsters=data["gm_monsters"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

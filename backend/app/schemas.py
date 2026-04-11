from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import EventKind, EventRole, SessionState


class SessionCreateResponse(BaseModel):
    session_id: str
    state: SessionState


class Tab1PartyAssignment(BaseModel):
    slot: int
    player_id: str
    class_id: str


class Tab1InputPayload(BaseModel):
    preset_id: str = "valaska"
    adventure_id: str = ""
    selected_player_ids: list[str] = Field(default_factory=list)
    class_assignments: dict[int, str] = Field(default_factory=dict)


class PartyMemberOut(BaseModel):
    slot: int
    player_id: str
    player_name: str
    class_id: str
    portrait_url: str
    base_portrait_url: str
    race: str
    archetype: str
    keywords: list[str]
    armor_class: int
    hp_max: int
    hp_current: int
    status_effects: list[str]
    inventory: list[str]
    initiative: int | None = None


class ObjectiveOut(BaseModel):
    id: str
    description: str
    status: str


class AdventureLocationOut(BaseModel):
    id: str
    number: int
    title: str
    description: str
    x_pct: float
    y_pct: float


class AdventureOut(BaseModel):
    adventure_id: str
    title: str
    description: str
    objectives: list[ObjectiveOut]
    monsters: list[str]
    map_image_url: str
    locations: list[AdventureLocationOut]


class Tab1InputResponse(BaseModel):
    preset_id: str
    adventure_id: str
    selected_player_ids: list[str]
    class_assignments: dict[int, str]
    selected_agent_slots: list[int]
    agent_names: dict[int, str]
    tab1_locked: bool
    party: list[PartyMemberOut]
    active_adventure: AdventureOut | None = None


class CombatStateOut(BaseModel):
    in_combat: bool
    round: int
    turn_index: int
    initiative_order: list[str]
    initiative_values: dict[str, int]


class OppositionMonsterInstanceOut(BaseModel):
    monster_id: str
    display_name: str
    current_hp: int
    hp_max: int
    is_dead: bool
    status_effects: list[str]


class OppositionStateOut(BaseModel):
    active: bool
    group_id: str
    initiative_id: str
    monster_type: str
    monster_stats: dict
    instances: list[OppositionMonsterInstanceOut]


class SessionSummary(BaseModel):
    session_id: str
    state: SessionState
    prompt_index: int
    last_summarized_prompt_index: int
    tab1_locked: bool
    combat_state: CombatStateOut
    selected_narrative_player_id: str
    opposition_state: OppositionStateOut | None = None


class PromptRequest(BaseModel):
    agent_slot: int
    user_text: str


class TravelRequest(BaseModel):
    location_id: str
    location_name: str
    location_description: str


class OppositionSpawnRequest(BaseModel):
    monster_type: str
    quantity: int = Field(ge=1, le=4)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    prompt_index: int
    role: Literal["user", "agent", "system"]
    kind: EventKind
    agent_slot: int | None
    text: str
    json_payload: dict
    created_at: datetime


class MemoryBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    block_id: str
    type: str
    from_prompt_index: int
    to_prompt_index: int
    json_payload: dict
    created_at: datetime


class PromptResponse(BaseModel):
    session: SessionSummary
    user_event: EventOut
    agent_event: EventOut
    summary_triggered: bool


class NarrativeAgentRequest(BaseModel):
    selected_player_id: str


class NarrativeBuildResponse(BaseModel):
    draft_id: str
    chapter_text: str


class DiceRollRequest(BaseModel):
    formula: str
    label: str = ""
    roller_id: str = "unknown"


class DiceRollResult(BaseModel):
    formula: str
    dice_count: int
    dice_sides: int
    rolls: list[int]
    modifier: int
    total: int
    label: str = ""
    roller_id: str = "unknown"
    timestamp: datetime
    roll_id: str


class DiceBatchRequest(BaseModel):
    rolls: list[DiceRollRequest]


class InitiativeResponse(BaseModel):
    combat_state: CombatStateOut
    rolls: list[DiceRollResult]


class ImageGenerateResponse(BaseModel):
    image_url: str
    prompt_text: str


class TTSRequest(BaseModel):
    text: str
    player_name: str


class ImageStateOut(BaseModel):
    image_url: str
    prompt_text: str
    last_actor_slot: int | None = None


class MonsterReferenceOut(BaseModel):
    monster_id: str
    ac: int
    hp: int
    attack_bonus: int
    attack_text: str
    image_url: str


class CatalogResponse(BaseModel):
    preset_id: str
    preset_name: str
    map_image_url: str
    adventure_selection_image_url: str
    default_image_url: str
    adventures: list[AdventureOut]
    players: list[dict]
    classes: list[dict]
    monsters: list[MonsterReferenceOut]


class SessionDetailResponse(BaseModel):
    session: SessionSummary
    tab1: Tab1InputResponse
    events: list[EventOut]
    memory_blocks: list[MemoryBlockOut]
    narrative_drafts: list[NarrativeBuildResponse]
    image_state: ImageStateOut
    gm_monsters: list[MonsterReferenceOut]

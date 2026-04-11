import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def json_type():
    return JSON().with_variant(JSONB, "postgresql")


class SessionState(str, enum.Enum):
    DRAFT_TAB1 = "DRAFT_TAB1"
    LOCKING = "LOCKING"
    ACTIVE = "ACTIVE"
    SUMMARIZING = "SUMMARIZING"
    ENDED = "ENDED"
    NARRATING = "NARRATING"
    RESETTING = "RESETTING"


class EventRole(str, enum.Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class EventKind(str, enum.Enum):
    TRANSCRIPT = "transcript"
    DICE_ROLL = "dice_roll"
    INITIATIVE_SET = "initiative_set"
    TURN_ENDED = "turn_ended"
    DAMAGE_APPLIED = "damage_applied"
    HP_CHANGED = "hp_changed"
    CONDITION_ADDED = "condition_added"
    CONDITION_REMOVED = "condition_removed"
    INVENTORY_GAINED = "inventory_gained"
    INVENTORY_LOST = "inventory_lost"
    IMAGE_GENERATED = "image_generated"
    OPPOSITION_SPAWNED = "opposition_spawned"
    MONSTER_DIED = "monster_died"
    OPPOSITION_DISMISSED = "opposition_dismissed"


class MemoryBlockType(str, enum.Enum):
    WORLD_CHAPTER_LOCK = "world_chapter_lock"
    TURN_DELTA = "turn_delta"


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    state: Mapped[SessionState] = mapped_column(Enum(SessionState), default=SessionState.DRAFT_TAB1, nullable=False)
    prompt_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected_agent_slots: Mapped[list] = mapped_column(json_type(), default=list, nullable=False)
    agent_names: Mapped[dict] = mapped_column(json_type(), default=dict, nullable=False)
    tab1_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_summarized_prompt_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    narrative_agent_definition_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    current_location_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    combat_state: Mapped[dict] = mapped_column(json_type(), default=dict, nullable=False)
    opposition_state: Mapped[dict] = mapped_column(json_type(), default=dict, nullable=False)
    generated_image: Mapped[dict] = mapped_column(json_type(), default=dict, nullable=False)
    selected_narrative_player_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Tab1Inputs(Base):
    __tablename__ = "tab1_inputs"

    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), primary_key=True)
    world_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    chapter_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    agent_identity_text_by_slot: Mapped[dict] = mapped_column(json_type(), default=dict, nullable=False)
    preset_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    adventure_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    selected_player_ids: Mapped[list] = mapped_column(json_type(), default=list, nullable=False)
    class_assignments: Mapped[dict] = mapped_column(json_type(), default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    prompt_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    role: Mapped[EventRole] = mapped_column(Enum(EventRole), nullable=False)
    kind: Mapped[EventKind] = mapped_column(Enum(EventKind), default=EventKind.TRANSCRIPT, nullable=False)
    agent_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    json_payload: Mapped[dict] = mapped_column(json_type(), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class MemoryBlock(Base):
    __tablename__ = "memory_blocks"

    block_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[MemoryBlockType] = mapped_column(Enum(MemoryBlockType), nullable=False)
    from_prompt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    to_prompt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    json_payload: Mapped[dict] = mapped_column(json_type(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NarrativeDraft(Base):
    __tablename__ = "narrative_drafts"

    draft_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    narrative_agent_definition_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_snapshot: Mapped[dict] = mapped_column(json_type(), nullable=False)
    chapter_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class LLMArtifact(Base):
    __tablename__ = "llm_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_counts: Mapped[dict] = mapped_column(json_type(), nullable=False)
    raw_input_ref: Mapped[str] = mapped_column(Text, nullable=False)
    raw_output_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

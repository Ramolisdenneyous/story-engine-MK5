export type SessionState = "DRAFT_TAB1" | "LOCKING" | "ACTIVE" | "SUMMARIZING" | "ENDED" | "NARRATING" | "RESETTING";

export type CatalogBoot = {
  preset_id: string;
  preset_name: string;
  map_image_url: string;
  adventure_selection_image_url: string;
  default_image_url: string;
  adventures: AdventureSummary[];
  players: PlayerCatalogSummary[];
  classes: ClassCatalogSummary[];
};

export type AdventureSummary = {
  adventure_id: string;
  title: string;
  description: string;
};

export type Objective = {
  id: string;
  description: string;
  status: string;
};

export type AdventureLocation = {
  id: string;
  number: number;
  title: string;
  description: string;
  x_pct: number;
  y_pct: number;
};

export type Adventure = {
  adventure_id: string;
  title: string;
  description: string;
  objectives: Objective[];
  monsters: string[];
  map_image_url: string;
  locations: AdventureLocation[];
};

export type PlayerCatalogSummary = {
  player_id: string;
  name: string;
  archetype: string;
  gender: string;
  race: string;
  keywords: string[];
  image_url: string;
};

export type ClassCatalogSummary = {
  class_id: string;
  name: string;
  role: string;
  armor_class: number;
  hp_max: number;
};

export type Monster = {
  monster_id: string;
  ac: number;
  hp: number;
  attack_bonus: number;
  attack_text: string;
  image_url: string;
};

export type CombatState = {
  in_combat: boolean;
  round: number;
  turn_index: number;
  initiative_order: string[];
  initiative_values: Record<string, number>;
  acted_this_round: Record<string, boolean>;
};

export type OppositionMonsterInstance = {
  monster_id: string;
  display_name: string;
  monster_type: string;
  current_hp: number;
  hp_max: number;
  is_dead: boolean;
  status_effects: string[];
};

export type MissionObjectiveState = {
  adventure_id: string;
  title: string;
  public_goal: string;
  progress_label: string;
  status: string;
  complete: boolean;
  return_available: boolean;
  returned_to_moosehearth?: boolean;
  allowed_location_ids?: string[];
  visited_location_ids?: string[];
  undead_kills?: number;
  target_kills?: number;
  gold_collected?: number;
  target_gold?: number;
  celebration_song?: CelebrationSongResponse;
  updates?: Array<{ prompt_index: number; text: string }>;
};

export type CelebrationSongResponse = {
  status: string;
  lyrics: string;
  prompt_text: string;
  audio_url: string;
  file_name: string;
  error: string;
};

export type EncounterState = {
  adventure_id?: string;
  location_id?: string;
  location_name?: string;
  encounter_type?: string;
  encounter_name?: string;
  active?: boolean;
  repeatable?: boolean;
  status?: string;
  hazard?: Record<string, unknown>;
  search?: {
    available?: boolean;
    found?: boolean;
    loot?: string[];
  };
  dropped_loot?: string[];
};

export type OppositionState = {
  active: boolean;
  group_id: string;
  initiative_id: string;
  monster_type: string;
  monster_stats: Record<string, unknown>;
  instances: OppositionMonsterInstance[];
  cleanup_after: string;
  flee_failed?: boolean;
};

export type PartyMember = {
  slot: number;
  player_id: string;
  player_name: string;
  class_id: string;
  portrait_url: string;
  base_portrait_url: string;
  race: string;
  archetype: string;
  keywords: string[];
  armor_class: number;
  hp_max: number;
  hp_current: number;
  mp_max: number;
  mp_current: number;
  status_effects: string[];
  class_features: string[];
  feature_uses: Record<string, number>;
  current_combat_feature_uses: Record<string, number>;
  inventory: string[];
  initiative: number | null;
};

export type TranscriptEvent = {
  event_id: string;
  prompt_index: number;
  role: "user" | "agent" | "system";
  kind: string;
  agent_slot: number | null;
  text: string;
  json_payload: Record<string, unknown>;
  created_at: string;
};

export type AttackResolvedPayload = {
  actor_id: string;
  target_id: string;
  hit: boolean;
  damage: number;
  target_hp_after: number;
};

export type PromptResponse = {
  session: SessionDetail["session"];
  user_event: TranscriptEvent;
  agent_event: TranscriptEvent | null;
  system_events: TranscriptEvent[];
  extra_events?: TranscriptEvent[];
  narration_pending: boolean;
  followup_pending?: boolean;
  followup_expected_agent_events?: number;
  summary_triggered: boolean;
};

export type SessionDetail = {
  session: {
    session_id: string;
    state: SessionState;
    prompt_index: number;
    last_summarized_prompt_index: number;
    tab1_locked: boolean;
    combat_state: CombatState;
    selected_narrative_player_id: string;
    opposition_state?: OppositionState | null;
    current_location_id: string;
    current_location_name: string;
    encounter_state: EncounterState;
    mission_objective_state: MissionObjectiveState;
  };
  tab1: {
    preset_id: string;
    adventure_id: string;
    selected_player_ids: string[];
    class_assignments: Record<number, string>;
    selected_agent_slots: number[];
    agent_names: Record<number, string>;
    tab1_locked: boolean;
    party: PartyMember[];
    active_adventure: Adventure | null;
  };
  events: TranscriptEvent[];
  memory_blocks: Array<{
    block_id: string;
    type: string;
    from_prompt_index: number;
    to_prompt_index: number;
    json_payload: Record<string, unknown>;
  }>;
  narrative_drafts: Array<{ draft_id: string; chapter_text: string }>;
  image_state: { image_url: string; prompt_text: string; last_actor_slot: number | null };
  gm_monsters: Monster[];
};

export type TtsState = "idle" | "loading" | "playing";

export type FeedbackCreateResponse = {
  feedback_id: string;
  session_id: string;
  created_at: string;
};

export const SLOT_COLORS: Record<number, string> = {
  1: "#f56f7e",
  2: "#ff9e4a",
  3: "#f4cf59",
  4: "#60d48f",
  12: "#69b7ff",
};

export const OPPOSITION_SLOT = 12;

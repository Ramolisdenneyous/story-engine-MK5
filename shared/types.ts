export type SessionState =
  | "DRAFT_TAB1"
  | "LOCKING"
  | "ACTIVE"
  | "SUMMARIZING"
  | "ENDED"
  | "NARRATING"
  | "RESETTING";

export interface EventRecord {
  event_id: string;
  session_id: string;
  prompt_index: number;
  role: "user" | "agent" | "system";
  agent_slot: number | null;
  text: string;
  created_at: string;
}

export interface MemoryBlockRecord {
  block_id: string;
  session_id: string;
  type: "world_chapter_lock" | "turn_delta";
  from_prompt_index: number;
  to_prompt_index: number;
  json_payload: Record<string, unknown>;
  created_at: string;
}

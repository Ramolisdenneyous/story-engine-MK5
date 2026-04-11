CREATE TABLE IF NOT EXISTS sessions (
  session_id UUID PRIMARY KEY,
  state VARCHAR(32) NOT NULL,
  prompt_index INTEGER NOT NULL DEFAULT 0,
  selected_agent_slots JSONB NOT NULL DEFAULT '[]'::jsonb,
  agent_names JSONB NOT NULL DEFAULT '{}'::jsonb,
  tab1_locked BOOLEAN NOT NULL DEFAULT FALSE,
  last_summarized_prompt_index INTEGER NOT NULL DEFAULT 0,
  narrative_agent_definition_text TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tab1_inputs (
  session_id UUID PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
  world_text TEXT NOT NULL DEFAULT '',
  chapter_text TEXT NOT NULL DEFAULT '',
  agent_identity_text_by_slot JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events (
  event_id UUID PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  prompt_index INTEGER NOT NULL,
  role VARCHAR(16) NOT NULL,
  agent_slot INTEGER NULL,
  text TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_events_session_prompt_created ON events(session_id, prompt_index, created_at);

CREATE TABLE IF NOT EXISTS memory_blocks (
  block_id UUID PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  type VARCHAR(32) NOT NULL,
  from_prompt_index INTEGER NOT NULL,
  to_prompt_index INTEGER NOT NULL,
  json_payload JSONB NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_memory_blocks_session_created ON memory_blocks(session_id, created_at);

CREATE TABLE IF NOT EXISTS narrative_drafts (
  draft_id UUID PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  narrative_agent_definition_text TEXT NOT NULL,
  source_snapshot JSONB NOT NULL,
  chapter_text TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS llm_artifacts (
  artifact_id UUID PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  agent_id VARCHAR(32) NOT NULL,
  provider VARCHAR(64) NOT NULL,
  model VARCHAR(128) NOT NULL,
  input_hash VARCHAR(64) NOT NULL,
  token_counts JSONB NOT NULL,
  raw_input_ref TEXT NOT NULL,
  raw_output_ref TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

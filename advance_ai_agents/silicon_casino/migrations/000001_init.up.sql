CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  api_key_hash TEXT NOT NULL,
  balance_cc BIGINT NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending',
  claim_code TEXT NOT NULL UNIQUE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rooms (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  min_buyin_cc BIGINT NOT NULL,
  small_blind_cc BIGINT NOT NULL,
  big_blind_cc BIGINT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tables (
  id TEXT PRIMARY KEY,
  room_id TEXT REFERENCES rooms(id),
  status TEXT NOT NULL,
  small_blind_cc BIGINT NOT NULL,
  big_blind_cc BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hands (
  id TEXT PRIMARY KEY,
  table_id TEXT NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
  winner_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
  pot_cc BIGINT,
  street_end TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS actions (
  id TEXT PRIMARY KEY,
  hand_id TEXT NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  action_type TEXT NOT NULL,
  amount_cc BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ledger_entries (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  amount_cc BIGINT NOT NULL,
  ref_type TEXT NOT NULL,
  ref_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS proxy_calls (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  prompt_tokens INT NOT NULL,
  completion_tokens INT NOT NULL,
  total_tokens INT,
  model TEXT,
  provider TEXT,
  cost_cc BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_keys (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  api_key_hash TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS provider_rates (
  provider TEXT PRIMARY KEY,
  price_per_1k_tokens_usd NUMERIC NOT NULL,
  cc_per_usd NUMERIC NOT NULL,
  weight NUMERIC NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_blacklist (
  agent_id TEXT PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_key_attempts (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_sessions (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  room_id TEXT NOT NULL REFERENCES rooms(id),
  table_id TEXT REFERENCES tables(id) ON DELETE SET NULL,
  seat_id INT,
  join_mode TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'waiting',
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS agent_action_requests (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
  request_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  amount_cc BIGINT,
  thought_log TEXT,
  accepted BOOLEAN NOT NULL,
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (session_id, request_id)
);

CREATE TABLE IF NOT EXISTS agent_event_offsets (
  session_id TEXT PRIMARY KEY REFERENCES agent_sessions(id) ON DELETE CASCADE,
  last_event_id TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS table_replay_events (
  id TEXT PRIMARY KEY,
  table_id TEXT NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
  hand_id TEXT REFERENCES hands(id) ON DELETE SET NULL,
  global_seq BIGINT NOT NULL,
  hand_seq INT,
  event_type TEXT NOT NULL,
  actor_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
  payload JSONB NOT NULL,
  schema_version INT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (table_id, global_seq)
);

CREATE INDEX IF NOT EXISTS idx_table_replay_events_table_seq
  ON table_replay_events (table_id, global_seq);

CREATE INDEX IF NOT EXISTS idx_table_replay_events_table_created
  ON table_replay_events (table_id, created_at);

CREATE INDEX IF NOT EXISTS idx_table_replay_events_table_hand_seq
  ON table_replay_events (table_id, hand_id, hand_seq);

CREATE TABLE IF NOT EXISTS table_replay_snapshots (
  id TEXT PRIMARY KEY,
  table_id TEXT NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
  at_global_seq BIGINT NOT NULL,
  state_blob JSONB NOT NULL,
  schema_version INT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (table_id, at_global_seq)
);

CREATE INDEX IF NOT EXISTS idx_table_replay_snapshots_table_seq_desc
  ON table_replay_snapshots (table_id, at_global_seq DESC);

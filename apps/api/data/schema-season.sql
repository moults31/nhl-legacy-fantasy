-- Season mode tables (separate from roster WR tables).

DROP TABLE IF EXISTS season_state;
CREATE TABLE IF NOT EXISTS season_state (
  current_day INTEGER NOT NULL DEFAULT 0,
  user_team_indices TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS season_teams (
  record INTEGER PRIMARY KEY,
  city TEXT NOT NULL,
  abbrev TEXT,
  full_name TEXT
);

CREATE TABLE IF NOT EXISTS season_players (
  record INTEGER PRIMARY KEY,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  proteam INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS season_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  day INTEGER NOT NULL,
  text_key TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS season_gm_states (
  record INTEGER PRIMARY KEY,
  gm_first_name TEXT NOT NULL,
  gm_last_name TEXT NOT NULL,
  current_day INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS season_schedule (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  game_index INTEGER NOT NULL,
  day INTEGER NOT NULL,
  team_pair INTEGER,
  val1 INTEGER NOT NULL,
  val2 INTEGER NOT NULL,
  event_type INTEGER NOT NULL,
  event_flag INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS season_performance (
  record INTEGER PRIMARY KEY,
  gm_first_name TEXT NOT NULL,
  gm_last_name TEXT NOT NULL,
  current_day INTEGER NOT NULL,
  budget_score INTEGER NOT NULL,
  performance_score INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 0,
  team_index INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS season_player_ratings (
  record INTEGER NOT NULL,
  field_id TEXT NOT NULL,
  value INTEGER NOT NULL,
  PRIMARY KEY (record, field_id)
);

DROP TABLE IF EXISTS season_transactions;
CREATE TABLE IF NOT EXISTS season_transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  record INTEGER NOT NULL,
  day INTEGER NOT NULL,
  event_index INTEGER NOT NULL,
  sub_type INTEGER NOT NULL,
  player_name TEXT,
  team_from_name TEXT,
  team_to_name TEXT,
  team_context_name TEXT,
  team_from_record INTEGER,
  team_to_record INTEGER
);

CREATE TABLE IF NOT EXISTS season_user_teams (
  record INTEGER PRIMARY KEY,
  is_user INTEGER NOT NULL DEFAULT 0,
  identifier INTEGER NOT NULL,
  counter INTEGER NOT NULL,
  games_played INTEGER NOT NULL DEFAULT 0
);

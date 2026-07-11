-- Season mode tables (separate from roster WR tables).

CREATE TABLE IF NOT EXISTS season_state (
  current_day INTEGER NOT NULL DEFAULT 0
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

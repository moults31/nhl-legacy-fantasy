-- Webapp Representation (WR) tables.
-- These use stable IDs/slugs and are independent of any SR/NR version.

CREATE TABLE IF NOT EXISTS teams (
  slug TEXT PRIMARY KEY,
  city TEXT NOT NULL,
  full_name TEXT NOT NULL,
  abbrev TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
  id TEXT PRIMARY KEY,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  main_team_slug TEXT REFERENCES teams(slug) ON DELETE SET NULL
);

-- Mapping tables connect WR IDs to the NR-leaky values of the current SR version.
-- For v1 these map to TDB record indices (player.record) and raw WBbd values (team.sr_proteam).
-- When SR v2 arrives, these tables are re-seeded and the WR tables stay unchanged.

CREATE TABLE IF NOT EXISTS team_mappings (
  wr_team_slug TEXT PRIMARY KEY REFERENCES teams(slug) ON DELETE CASCADE,
  sr_record INTEGER NOT NULL,
  sr_proteam INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS player_mappings (
  wr_player_id TEXT PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
  sr_record INTEGER NOT NULL
);

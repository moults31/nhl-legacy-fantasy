-- Minimal synthetic seed data for local development.
-- In production these rows (and the mapping tables) are populated from a
-- vanilla roster export produced by nhl-db-studio-mule.

INSERT OR IGNORE INTO teams (slug, city, full_name, abbrev) VALUES
  ('anaheim', 'Anaheim', 'Anaheim Ducks', 'ANA'),
  ('st-louis', 'St. Louis', 'St. Louis Blues', 'STL');

INSERT OR IGNORE INTO players (id, first_name, last_name, main_team_slug) VALUES
  ('mason-mctavish', 'Mason', 'McTavish', 'anaheim'),
  ('connor-mcdavid', 'Connor', 'McDavid', 'st-louis');

INSERT OR IGNORE INTO team_mappings (wr_team_slug, sr_record, sr_proteam) VALUES
  ('anaheim', 0, 0),
  ('st-louis', 24, 24);

INSERT OR IGNORE INTO player_mappings (wr_player_id, sr_record) VALUES
  ('mason-mctavish', 1424),
  ('connor-mcdavid', 500);

import Database from "better-sqlite3";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { config } from "./config.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

let db: Database.Database | null = null;

export function createDb(databaseUrl: string): Database.Database {
  const database = new Database(databaseUrl);
  if (databaseUrl !== ":memory:") {
    database.pragma("journal_mode = WAL");
  }
  return database;
}

export function getDb(): Database.Database {
  if (!db) {
    db = createDb(config.databaseUrl);
  }
  return db;
}

export function initDb(database: Database.Database = getDb()): void {
  const schemaSql = readFileSync(join(__dirname, "../data/schema.sql"), "utf8");
  database.exec(schemaSql);
}

export function closeDb(): void {
  db?.close();
  db = null;
}

export interface TeamRow {
  slug: string;
  city: string;
  full_name: string;
  abbrev: string;
}

export interface PlayerRow {
  id: string;
  first_name: string;
  last_name: string;
  main_team_slug: string | null;
}

export interface PlayerMappingRow {
  wr_player_id: string;
  sr_record: number;
}

export interface TeamMappingRow {
  wr_team_slug: string;
  sr_record: number;
  sr_proteam: number;
}

export function getTeams(database: Database.Database = getDb()): TeamRow[] {
  return database.prepare<[], TeamRow>("SELECT * FROM teams ORDER BY city").all();
}

/** ZZ-/ZZZ-/ZZZZ-only last names are placeholder records in the vanilla roster.
 * The game filters them out of the in-game UI; mirror that here. */
const ZZ_FILTER =
  "last_name NOT IN ('ZZ', 'ZZZ', 'ZZZZ')";

export function getPlayers(database: Database.Database = getDb()): PlayerRow[] {
  return database
    .prepare<[], PlayerRow>(`SELECT * FROM players WHERE ${ZZ_FILTER} ORDER BY last_name, first_name`)
    .all();
}

export function getPlayersByTeam(slug: string, database: Database.Database = getDb()): PlayerRow[] {
  return database
    .prepare<[string], PlayerRow>(
      `SELECT * FROM players WHERE main_team_slug = ? AND ${ZZ_FILTER} ORDER BY last_name, first_name`
    )
    .all(slug);
}

export function setPlayerTeam(
  playerId: string,
  teamSlug: string | null,
  database: Database.Database = getDb()
): void {
  database
    .prepare<[string | null, string]>(
      "UPDATE players SET main_team_slug = ? WHERE id = ?"
    )
    .run(teamSlug, playerId);
}

export function getPlayerMappings(database: Database.Database = getDb()): Map<string, PlayerMappingRow> {
  const rows = database
    .prepare<[], PlayerMappingRow>("SELECT * FROM player_mappings")
    .all();
  return new Map(rows.map((r) => [r.wr_player_id, r]));
}

export function getTeamMappings(database: Database.Database = getDb()): Map<string, TeamMappingRow> {
  const rows = database
    .prepare<[], TeamMappingRow>("SELECT * FROM team_mappings")
    .all();
  return new Map(rows.map((r) => [r.wr_team_slug, r]));
}

// ── Season mode queries ──

export interface SeasonTeamRow {
  record: number;
  city: string;
  abbrev: string | null;
  full_name: string | null;
}

export interface SeasonPlayerRow {
  record: number;
  first_name: string;
  last_name: string;
  proteam: number;
}

export interface SeasonEventRow {
  id: number;
  day: number;
  text_key: string;
}

export interface SeasonGmStateRow {
  record: number;
  gm_first_name: string;
  gm_last_name: string;
  current_day: number;
}

export function getSeasonDay(database: Database.Database = getDb()): number {
  const row = database
    .prepare<[], { current_day: number }>("SELECT current_day FROM season_state LIMIT 1")
    .get();
  return row?.current_day ?? 0;
}

export function getSeasonUserTeamIndices(database: Database.Database = getDb()): number[] {
  const row = database
    .prepare<[], { user_team_indices: string }>("SELECT user_team_indices FROM season_state LIMIT 1")
    .get();
  if (!row?.user_team_indices) return [];
  try {
    return JSON.parse(row.user_team_indices);
  } catch {
    return [];
  }
}

export function getSeasonTeams(database: Database.Database = getDb()): SeasonTeamRow[] {
  return database
    .prepare<[], SeasonTeamRow>("SELECT * FROM season_teams ORDER BY record")
    .all();
}

export function getSeasonPlayers(database: Database.Database = getDb()): SeasonPlayerRow[] {
  return database
    .prepare<[], SeasonPlayerRow>(
      "SELECT * FROM season_players WHERE last_name NOT IN ('ZZ', 'ZZZ', 'ZZZZ') ORDER BY last_name, first_name"
    )
    .all();
}

export function getSeasonPlayersByProteam(
  proteam: number,
  database: Database.Database = getDb()
): SeasonPlayerRow[] {
  return database
    .prepare<[number], SeasonPlayerRow>(
      "SELECT * FROM season_players WHERE proteam = ? AND last_name NOT IN ('ZZ', 'ZZZ', 'ZZZZ') ORDER BY last_name, first_name"
    )
    .all(proteam);
}

export function getSeasonEvents(database: Database.Database = getDb()): SeasonEventRow[] {
  return database
    .prepare<[], SeasonEventRow>("SELECT * FROM season_events ORDER BY day, id")
    .all();
}

export function getSeasonGmStates(database: Database.Database = getDb()): SeasonGmStateRow[] {
  return database.prepare<[], SeasonGmStateRow>(
    "SELECT * FROM season_gm_states ORDER BY record"
  ).all();
}

export interface SeasonScheduleRow {
  id: number;
  game_index: number;
  day: number;
  home_team: number | null;
  away_team: number | null;
  home_goals: number;
  away_goals: number;
  val1: number;
  val2: number;
  event_type: number;
  event_flag: number;
  is_future: number;
}

export function getSeasonSchedule(database: Database.Database = getDb()): SeasonScheduleRow[] {
  return database.prepare<[], SeasonScheduleRow>(
    "SELECT * FROM season_schedule ORDER BY game_index"
  ).all();
}

export interface SeasonPerformanceRow {
  record: number;
  gm_first_name: string;
  gm_last_name: string;
  current_day: number;
  budget_score: number;
  performance_score: number;
  active: number;
  team_index: number;
}

export function getSeasonPerformance(database: Database.Database = getDb()): SeasonPerformanceRow[] {
  return database.prepare<[], SeasonPerformanceRow>(
    "SELECT * FROM season_performance ORDER BY record"
  ).all();
}

export function getSeasonRatingsForPlayer(record: number, database: Database.Database = getDb()): Record<string, number> {
  const rows = database.prepare<[number], { field_id: string; value: number }>(
    "SELECT field_id, value FROM season_player_ratings WHERE record = ?"
  ).all(record);
  const result: Record<string, number> = {};
  for (const r of rows) result[r.field_id] = r.value;
  return result;
}

export interface SeasonTransactionRow {
  id: number;
  record: number;
  day: number;
  event_index: number;
  sub_type: number;
  player_name: string | null;
  team_from_name: string | null;
  team_to_name: string | null;
  team_context_name: string | null;
  team_from_record: number | null;
  team_to_record: number | null;
}

export function getSeasonTransactions(database: Database.Database = getDb()): SeasonTransactionRow[] {
  return database.prepare<[], SeasonTransactionRow>(
    "SELECT * FROM season_transactions ORDER BY event_index"
  ).all();
}

export interface SeasonUserTeamRow {
  record: number;
  is_user: number;
  identifier: number;
  counter: number;
  games_played: number;
}

export function getSeasonUserTeams(database: Database.Database = getDb()): SeasonUserTeamRow[] {
  return database.prepare<[], SeasonUserTeamRow>(
    "SELECT * FROM season_user_teams ORDER BY record"
  ).all();
}

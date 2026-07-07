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

export function getPlayers(database: Database.Database = getDb()): PlayerRow[] {
  return database
    .prepare<[], PlayerRow>("SELECT * FROM players ORDER BY last_name, first_name")
    .all();
}

export function getPlayersByTeam(slug: string, database: Database.Database = getDb()): PlayerRow[] {
  return database
    .prepare<[string], PlayerRow>(
      "SELECT * FROM players WHERE main_team_slug = ? ORDER BY last_name, first_name"
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

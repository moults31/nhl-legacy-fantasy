import Database from "better-sqlite3";
import { readFileSync } from "node:fs";
import path from "node:path";
import { SeasonFullExportSchema } from "@nlf/spec-client";

const dbPath =
  process.env.DB_PATH || path.resolve(import.meta.dirname, "../data/dev.db");

const jsonPath =
  process.env.SEASON_JSON ||
  path.resolve(import.meta.dirname, "../data/season.json");

const db = new Database(dbPath);
db.pragma("journal_mode = WAL");

console.log(`Seeding season data into ${dbPath}`);

// Run schema
const schemaSql = readFileSync(
  path.resolve(import.meta.dirname, "../data/schema-season.sql"),
  "utf-8",
);
db.exec(schemaSql);

// Read and validate season JSON
console.log(`Reading season JSON from ${jsonPath}`);
const raw = JSON.parse(readFileSync(jsonPath, "utf-8"));
const parsed = SeasonFullExportSchema.parse(raw);

// Clear existing season data
db.exec("DELETE FROM season_state");
db.exec("DELETE FROM season_teams");
db.exec("DELETE FROM season_players");
db.exec("DELETE FROM season_events");
db.exec("DELETE FROM season_gm_states");

// Insert state
db.prepare("INSERT INTO season_state (current_day) VALUES (?)").run(
  parsed.current_day,
);

// Insert teams
const insertTeam = db.prepare(
  "INSERT INTO season_teams (record, city, abbrev, full_name) VALUES (?, ?, ?, ?)",
);
const teamTx = db.transaction(() => {
  for (const t of parsed.teams) {
    insertTeam.run(t.record, t.city, t.abbrev ?? null, t.full_name ?? null);
  }
});
teamTx();
console.log(`  ${parsed.teams.length} teams`);

// Insert players
const insertPlayer = db.prepare(
  "INSERT INTO season_players (record, first_name, last_name, proteam) VALUES (?, ?, ?, ?)",
);
const playerTx = db.transaction(() => {
  for (const p of parsed.players) {
    insertPlayer.run(p.record, p.first_name, p.last_name, p.proteam);
  }
});
playerTx();
console.log(`  ${parsed.players.length} players`);

// Insert calendar events
const insertEvent = db.prepare(
  "INSERT INTO season_events (day, text_key) VALUES (?, ?)",
);
const eventTx = db.transaction(() => {
  for (const e of parsed.calendar ?? []) {
    insertEvent.run(e.day, e.text_key);
  }
});
eventTx();
console.log(`  ${(parsed.calendar ?? []).length} events`);

// Insert GM states
const insertGm = db.prepare(
  "INSERT INTO season_gm_states (record, gm_first_name, gm_last_name, current_day) VALUES (?, ?, ?, ?)",
);
const gmTx = db.transaction(() => {
  for (const g of parsed.gm_states ?? []) {
    insertGm.run(g.record, g.gm_first_name, g.gm_last_name, g.current_day);
  }
});
gmTx();
console.log(`  ${(parsed.gm_states ?? []).length} GM states`);

console.log("Season seed complete.");

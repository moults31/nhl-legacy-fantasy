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

// Clear existing season data (in correct FK order)
db.exec("DELETE FROM season_player_ratings");
db.exec("DELETE FROM season_events");
db.exec("DELETE FROM season_transactions");
db.exec("DELETE FROM season_schedule");
db.exec("DELETE FROM season_performance");
db.exec("DELETE FROM season_user_teams");
db.exec("DELETE FROM season_gm_states");
db.exec("DELETE FROM season_players");
db.exec("DELETE FROM season_teams");
db.exec("DELETE FROM season_state");

// Insert state
const uti = JSON.stringify(parsed.user_team_indices ?? []);
db.prepare("INSERT INTO season_state (current_day, user_team_indices) VALUES (?, ?)").run(
  parsed.current_day, uti,
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

// Insert schedule
const insertSchedule = db.prepare(
  "INSERT INTO season_schedule (game_index, day, team_pair, val1, val2, event_type, event_flag) VALUES (?, ?, ?, ?, ?, ?, ?)",
);
const schedTx = db.transaction(() => {
  for (const s of parsed.schedule ?? []) {
    insertSchedule.run(s.game_index, s.day, s.team_pair ?? null, s.val1, s.val2, s.event_type, s.event_flag);
  }
});
schedTx();
console.log(`  ${(parsed.schedule ?? []).length} schedule entries`);

// Insert performance
const insertPerf = db.prepare(
  "INSERT INTO season_performance (record, gm_first_name, gm_last_name, current_day, budget_score, performance_score, active, team_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
);
const perfTx = db.transaction(() => {
  for (const p of parsed.performance ?? []) {
    insertPerf.run(p.record, p.gm_first_name, p.gm_last_name, p.current_day, p.budget_score, p.performance_score, p.active, p.team_index);
  }
});
perfTx();
console.log(`  ${(parsed.performance ?? []).length} performance entries`);

// Insert player ratings
const insertRating = db.prepare(
  "INSERT OR REPLACE INTO season_player_ratings (record, field_id, value) VALUES (?, ?, ?)",
);
const ratingTx = db.transaction(() => {
  for (const r of parsed.player_ratings ?? []) {
    const base: Record<string, unknown> = r as unknown as Record<string, unknown>;
    for (const [key, val] of Object.entries(base)) {
      if (key === "record") continue;
      if (typeof val === "number") {
        insertRating.run(r.record, key, val);
      }
    }
  }
});
ratingTx();
console.log(`  ${(parsed.player_ratings ?? []).length} player rating records`);

// Insert transactions
const insertTxn = db.prepare(
  "INSERT INTO season_transactions (record, day, event_index, sub_type, player_name, team_from_name, team_to_name, team_context_name, team_from_record, team_to_record) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
);
const txnTx = db.transaction(() => {
  for (const t of parsed.transactions ?? []) {
    insertTxn.run(t.record, t.day, t.event_index, t.sub_type, t.player_name ?? null, t.team_from_name ?? null, t.team_to_name ?? null, t.team_context_name ?? null, t.team_from_record ?? null, t.team_to_record ?? null);
  }
});
txnTx();
console.log(`  ${(parsed.transactions ?? []).length} transactions`);

// Insert user teams
const insertUser = db.prepare(
  "INSERT INTO season_user_teams (record, is_user, identifier, counter, games_played) VALUES (?, ?, ?, ?, ?)",
);
const userTx = db.transaction(() => {
  for (const u of parsed.user_teams ?? []) {
    insertUser.run(u.record, u.is_user ? 1 : 0, u.identifier, u.counter, u.games_played);
  }
});
userTx();
console.log(`  ${(parsed.user_teams ?? []).length} user team records`);

console.log("Season seed complete.");

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { createDb, initDb, getPlayers, getTeams, getPlayerMappings, getTeamMappings } from "./db.js";
import { buildSrV1Roster, WrPlayer, WrTeam } from "@nlf/spec-client";

describe("WR -> SR v1 translation", () => {
  it("produces a valid roster document from seeded WR state", () => {
    const db = createDb(":memory:");
    initDb(db);

    // Seed with the same data as data/seed.sql, but using the DB directly.
    db.exec(`
      INSERT INTO teams (slug, city, full_name, abbrev) VALUES
        ('anaheim', 'Anaheim', 'Anaheim Ducks', 'ANA'),
        ('st-louis', 'St. Louis', 'St. Louis Blues', 'STL');

      INSERT INTO players (id, first_name, last_name, main_team_slug) VALUES
        ('mason-mctavish', 'Mason', 'McTavish', 'st-louis'),
        ('connor-mcdavid', 'Connor', 'McDavid', 'anaheim');

      INSERT INTO team_mappings (wr_team_slug, sr_record, sr_proteam) VALUES
        ('anaheim', 0, 0),
        ('st-louis', 24, 24);

      INSERT INTO player_mappings (wr_player_id, sr_record) VALUES
        ('mason-mctavish', 1424),
        ('connor-mcdavid', 500);
    `);

    const teams = getTeams(db);
    const players = getPlayers(db);
    const playerMappings = getPlayerMappings(db);
    const teamMappings = getTeamMappings(db);

    const wrTeams: WrTeam[] = teams.map((t) => ({
      slug: t.slug,
      city: t.city,
      fullName: t.full_name,
      abbrev: t.abbrev,
    }));

    const wrPlayers: WrPlayer[] = players.map((p) => ({
      id: p.id,
      firstName: p.first_name,
      lastName: p.last_name,
      mainTeamSlug: p.main_team_slug,
    }));

    const sr = buildSrV1Roster({
      teams: wrTeams,
      players: wrPlayers,
      mappings: {
        players: new Map(
          Array.from(playerMappings.entries()).map(([id, m]) => [
            id,
            { wrPlayerId: id, srRecord: m.sr_record },
          ])
        ),
        teams: new Map(
          Array.from(teamMappings.entries()).map(([slug, m]) => [
            slug,
            { wrTeamSlug: slug, srRecord: m.sr_record, srProteam: m.sr_proteam },
          ])
        ),
      },
    });

    assert.equal(sr.schema, "nhl-legacy-roster/0.1");
    assert.equal(sr.players.length, 2);

    const mason = sr.players.find((p) => p.last_name === "McTavish");
    assert.ok(mason);
    assert.equal(mason!.proteam, 24);

    const connor = sr.players.find((p) => p.last_name === "McDavid");
    assert.ok(connor);
    assert.equal(connor!.proteam, 0);
  });
});

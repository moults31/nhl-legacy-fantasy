import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  buildSrV1Roster,
  seedMappingsFromVanilla,
  WrPlayer,
  WrTeam,
} from "./translator.js";
import { SrV1RosterSchema } from "./schema.js";

const fixtureUrl = import.meta.resolve(
  "@moults31/nhl-legacy-roster-spec/fixtures/v1/vanilla.json"
);
const vanilla = SrV1RosterSchema.parse(
  JSON.parse(readFileSync(fileURLToPath(fixtureUrl), "utf8"))
);

describe("seedMappingsFromVanilla", () => {
  it("maps teams and players by name", () => {
    const teams: WrTeam[] = [
      { slug: "anaheim", city: "Anaheim", fullName: "Anaheim Ducks", abbrev: "ANA" },
      { slug: "st-louis", city: "St. Louis", fullName: "St. Louis Blues", abbrev: "STL" },
    ];
    const players: WrPlayer[] = [
      {
        id: "mason-mctavish",
        firstName: "Mason",
        lastName: "McTavish",
        mainTeamSlug: "anaheim",
      },
      {
        id: "connor-mcdavid",
        firstName: "Connor",
        lastName: "McDavid",
        mainTeamSlug: "st-louis",
      },
    ];

    const mappings = seedMappingsFromVanilla(teams, players, vanilla);

    assert.equal(mappings.teams.get("anaheim")?.srProteam, 0);
    assert.equal(mappings.teams.get("st-louis")?.srProteam, 24);
    assert.equal(mappings.players.get("mason-mctavish")?.srRecord, 1424);
    assert.equal(mappings.players.get("connor-mcdavid")?.srRecord, 500);
  });
});

describe("buildSrV1Roster", () => {
  it("produces a schema-valid roster with proteam assignments", () => {
    const teams: WrTeam[] = [
      { slug: "anaheim", city: "Anaheim", fullName: "Anaheim Ducks", abbrev: "ANA" },
      { slug: "st-louis", city: "St. Louis", fullName: "St. Louis Blues", abbrev: "STL" },
    ];
    const players: WrPlayer[] = [
      {
        id: "mason-mctavish",
        firstName: "Mason",
        lastName: "McTavish",
        mainTeamSlug: "st-louis", // moved
      },
    ];

    const mappings = seedMappingsFromVanilla(teams, players, vanilla);
    const roster = buildSrV1Roster({ teams, players, mappings });

    assert.equal(roster.schema, "nhl-legacy-roster/0.1");
    assert.equal(roster.players.length, 1);
    assert.equal(roster.players[0].proteam, 24);
  });
});

import { SrV1Player, SrV1Roster, SR_V1_SCHEMA_TOKEN } from "./schema.js";

/**
 * Webapp Representation (WR) types.
 *
 * The WR uses stable IDs and slugs. It deliberately does NOT use NR-leaky
 * values like TDB row indices (`record`) or raw `WBbd` proteam values.
 */
export interface WrTeam {
  slug: string;
  city: string;
  fullName: string;
  abbrev: string;
}

export interface WrPlayer {
  id: string;
  firstName: string;
  lastName: string;
  mainTeamSlug: string | null;
}

/**
 * Mapping table connecting WR IDs to the NR-leaky values in SR v1.
 *
 * This is seeded from a vanilla roster export and refreshed when the vanilla
 * roster changes. It is the only place in the webapp that knows about
 * `record` and `proteam` values.
 */
export interface PlayerMapping {
  wrPlayerId: string;
  srRecord: number;
}

export interface TeamMapping {
  wrTeamSlug: string;
  srRecord: number;
  /** Logical team ID (WBbd/proteam value), NOT the ttOk record index. See {@link NHL_LOGICAL_TEAM_IDS}. */
  srProteam: number;
}

export interface Mappings {
  players: Map<string, PlayerMapping>;
  teams: Map<string, TeamMapping>;
}

export interface BuildRosterOptions {
  teams: WrTeam[];
  players: WrPlayer[];
  mappings: Mappings;
}

/**
 * Logical team IDs used as `srProteam` values in the SR v1 schema.
 *
 * These are the values stored in the game's `cPbu.WBbd` (proteam) field.  They
 * are **not** contiguous record indices into the `ttOk` team table — that table
 * is ordered alphabetically while these IDs follow the original EA NHL team
 * numbering (with gaps for defunct/relocated franchises).
 *
 * This constant is intentionally a **bitemporal truth** — the EA numbering
 * hasn't changed since 2014 and won't change (the game is frozen).  It's not
 * used at runtime (the seed script bakes these values into the mapping table),
 * but it lives here because the proteam numbering is *the* non-obvious
 * piece of domain knowledge that every maintainer of the seed pipeline will
 * need to understand.  The alternative — rediscovering it from a mule export
 * each time — is slower and more error-prone.  See `roster_db.rs::team_info`
 * in the mule repo for the source of truth.
 */
export const NHL_LOGICAL_TEAM_IDS = new Map<string, number>([
  ["ANA", 1],  // Anaheim
  ["BOS", 2],  // Boston
  ["BUF", 3],  // Buffalo
  ["CGY", 5],  // Calgary
  ["CAR", 6],  // Carolina
  ["CHI", 7],  // Chicago
  ["COL", 8],  // Colorado
  ["CBJ", 9],  // Columbus
  ["DAL", 10], // Dallas
  ["DET", 11], // Detroit
  ["EDM", 12], // Edmonton
  ["FLA", 13], // Florida
  ["LAK", 14], // Los Angeles
  ["MIN", 15], // Minnesota
  ["MTL", 16], // Montreal
  ["NSH", 17], // Nashville
  ["NJD", 18], // New Jersey
  ["NYI", 19], // NY Islanders
  ["NYR", 20], // NY Rangers
  ["OTT", 21], // Ottawa
  ["PHI", 22], // Philadelphia
  ["PIT", 24], // Pittsburgh
  ["SJS", 25], // San Jose
  ["STL", 27], // St. Louis
  ["TBL", 28], // Tampa Bay
  ["TOR", 29], // Toronto
  ["VAN", 30], // Vancouver
  ["VGK", 31], // Vegas
  ["WPG", 32], // Winnipeg
  ["WSH", 33], // Washington
  ["SEA", 228], // Seattle
  ["UTA", 229], // Utah
]);

/**
 * Build an SR v1 roster document from the WR state.
 *
 * Only players whose `mainTeamSlug` is known and mapped are included; the mule
 * import is proteam-only, so unlisted players keep their vanilla assignment.
 */
export function buildSrV1Roster(options: BuildRosterOptions): SrV1Roster {
  const { teams, players, mappings } = options;

  const srTeams = teams
    .map((team): SrV1Roster["teams"][number] | null => {
      const mapping = mappings.teams.get(team.slug);
      if (!mapping) return null;
      return {
        record: mapping.srRecord,
        city: team.city,
        full_name: team.fullName,
        abbrev: team.abbrev,
      };
    })
    .filter((t): t is NonNullable<typeof t> => t !== null);

  // Index WR players by ID for quick name lookup while building the SR doc.
  const playerById = new Map(players.map((p) => [p.id, p]));

  const srPlayers: SrV1Player[] = [];
  for (const player of players) {
    if (!player.mainTeamSlug) continue;
    const playerMapping = mappings.players.get(player.id);
    const teamMapping = mappings.teams.get(player.mainTeamSlug);
    if (!playerMapping || !teamMapping) continue;

    srPlayers.push({
      record: playerMapping.srRecord,
      first_name: player.firstName,
      last_name: player.lastName,
      proteam: teamMapping.srProteam,
    });
  }

  return {
    schema: SR_V1_SCHEMA_TOKEN,
    teams: srTeams,
    players: srPlayers,
  };
}

/**
 * Seed mappings from a vanilla SR v1 export by matching names.
 *
 * In a real deployment this is run once after unpacking/exporting the vanilla
 * roster; here we provide a pure helper that can be fed from the DB seed
 * script.
 */
export function seedMappingsFromVanilla(
  wrTeams: WrTeam[],
  wrPlayers: WrPlayer[],
  vanilla: SrV1Roster
): Mappings {
  const teamMap = new Map<string, TeamMapping>();
  for (const team of wrTeams) {
    const srTeam = vanilla.teams.find(
      (t) =>
        t.city.toLowerCase() === team.city.toLowerCase() ||
        (t.abbrev && t.abbrev.toLowerCase() === team.abbrev.toLowerCase())
    );
    if (!srTeam) continue;
    teamMap.set(team.slug, {
      wrTeamSlug: team.slug,
      srRecord: srTeam.record,
      srProteam: srTeam.record, // In v1 the mapping table keeps these separate even if they often coincide.
    });
  }

  const playerMap = new Map<string, PlayerMapping>();
  for (const player of wrPlayers) {
    const srPlayer = vanilla.players.find(
      (p) =>
        p.first_name.toLowerCase() === player.firstName.toLowerCase() &&
        p.last_name.toLowerCase() === player.lastName.toLowerCase()
    );
    if (!srPlayer) continue;
    playerMap.set(player.id, {
      wrPlayerId: player.id,
      srRecord: srPlayer.record,
    });
  }

  return { players: playerMap, teams: teamMap };
}

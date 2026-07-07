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

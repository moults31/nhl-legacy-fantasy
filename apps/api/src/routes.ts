import { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import {
  buildSrV1Roster,
  SrV1Roster,
  WrPlayer,
  WrTeam,
} from "@nlf/spec-client";
import {
  getDb,
  getPlayerMappings,
  getPlayers,
  getPlayersByTeam,
  getTeamMappings,
  getTeams,
  setPlayerTeam,
} from "./db.js";
import { packRoster } from "./mule.js";

import { installRoster } from "./install.js";
import {
  getSeasonDay,
  getSeasonEvents,
  getSeasonGmStates,
  getSeasonPlayers,
  getSeasonPlayersByProteam,
  getSeasonTeams,
} from "./db.js";

interface AssignPlayerParams {
  playerId: string;
  teamSlug: string;
}

interface AssignPlayerBody {
  action: "assign" | "remove";
}

/** Build an SR v1 roster document from the current WR database state. */
function buildSr(teamSlug: string): SrV1Roster {
  const teams = getTeams();
  const players = getPlayers();
  const playerMappings = getPlayerMappings();
  const teamMappings = getTeamMappings();

  const team = teams.find((t) => t.slug === teamSlug);
  if (!team) {
    throw Object.assign(new Error("Team not found"), { statusCode: 404 });
  }

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

  // Ensure the requested team appears in the SR document.
  if (!sr.teams.find((t) => t.record === teamMappings.get(teamSlug)?.sr_record)) {
    const mapping = teamMappings.get(teamSlug);
    if (mapping) {
      sr.teams.push({
        record: mapping.sr_record,
        city: team.city,
        full_name: team.full_name,
        abbrev: team.abbrev,
      });
    }
  }

  return sr;
}

export async function registerRoutes(app: FastifyInstance): Promise<void> {
  app.get("/health", async () => ({ status: "ok" }));

  app.get("/teams", async () => {
    return getTeams();
  });

  app.get("/players", async () => {
    return getPlayers();
  });

  app.get("/teams/:slug/players", async (request: FastifyRequest<{ Params: { slug: string } }>) => {
    return getPlayersByTeam(request.params.slug);
  });

  app.post(
    "/players/:playerId/team/:teamSlug",
    async (
      request: FastifyRequest<{ Params: AssignPlayerParams; Body: AssignPlayerBody }>,
      reply: FastifyReply
    ) => {
      const { playerId, teamSlug } = request.params;
      const action = request.body?.action ?? "assign";
      setPlayerTeam(playerId, action === "remove" ? null : teamSlug);
      return reply.status(204).send();
    }
  );

  app.post(
    "/teams/:slug/export",
    async (request: FastifyRequest<{ Params: { slug: string } }>, reply: FastifyReply) => {
      try {
        const sr = buildSr(request.params.slug);
        const bin = await packRoster(sr);
        return reply
          .header("Content-Type", "application/octet-stream")
          .header("Content-Disposition", `attachment; filename="${request.params.slug}-roster.bin"`)
          .send(bin);
      } catch (err: any) {
        if (err?.statusCode === 404) {
          return reply.status(404).send({ error: err.message });
        }
        throw err;
      }
    }
  );

  app.post(
    "/teams/:slug/install",
    async (request: FastifyRequest<{ Params: { slug: string } }>, reply: FastifyReply) => {
      try {
        const sr = buildSr(request.params.slug);
        const bin = await packRoster(sr);
        const result = await installRoster(bin);
        return reply.send({
          installed: true,
          saveName: result.saveName,
          gameReady: true,
        });
      } catch (err: any) {
        if (err?.statusCode === 404) {
          return reply.status(404).send({ error: err.message });
        }
        throw err;
      }
    }
  );

  // ── Season mode routes ──

  app.get("/season/state", async () => {
    return { current_day: getSeasonDay() };
  });

  app.get("/season/teams", async () => {
    return getSeasonTeams();
  });

  app.get("/season/players", async () => {
    return getSeasonPlayers();
  });

  app.get(
    "/season/teams/:record/players",
    async (request: FastifyRequest<{ Params: { record: string } }>) => {
      const record = parseInt(request.params.record, 10);
      if (isNaN(record)) return [];
      // Season proteam = team record + 1 for the first ~32 teams
      const proteam = record + 1;
      return getSeasonPlayersByProteam(proteam);
    }
  );

  app.get("/season/events", async () => {
    return getSeasonEvents();
  });

  app.get("/season/gm-states", async () => {
    return getSeasonGmStates();
  });
}

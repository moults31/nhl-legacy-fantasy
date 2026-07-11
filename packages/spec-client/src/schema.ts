import { z } from "zod";

/**
 * Hand-derived Zod schema and TypeScript types for SR v1
 * (`nhl-legacy-roster/0.1`).
 *
 * The canonical source of truth is the JSON Schema in the spec repo:
 *   @moults31/nhl-legacy-roster-spec/schemas/nhl-legacy-roster.v1.json
 *
 * These types are validated against the spec fixtures in CI.
 */

export const SrV1TeamSchema = z.object({
  record: z.number().int().nonnegative(),
  city: z.string(),
  full_name: z.string().optional(),
  abbrev: z.string().optional(),
});

export const SrV1PlayerSchema = z.object({
  record: z.number().int().nonnegative(),
  first_name: z.string(),
  last_name: z.string(),
  proteam: z.number().int().nonnegative(),
});

export const SrV1RosterSchema = z.object({
  schema: z.literal("nhl-legacy-roster/0.1"),
  teams: z.array(SrV1TeamSchema),
  players: z.array(SrV1PlayerSchema),
});

export type SrV1Team = z.infer<typeof SrV1TeamSchema>;
export type SrV1Player = z.infer<typeof SrV1PlayerSchema>;
export type SrV1Roster = z.infer<typeof SrV1RosterSchema>;

export const SR_V1_SCHEMA_TOKEN = "nhl-legacy-roster/0.1" as const;

// ── Season v1 schema (`nhl-legacy-season/0.1`) ──

export const SeasonCalendarEventSchema = z.object({
  record: z.number().int().nonnegative(),
  day: z.number().int().nonnegative(),
  text_key: z.string(),
});

export const SeasonGmStateSchema = z.object({
  record: z.number().int().nonnegative(),
  gm_first_name: z.string(),
  gm_last_name: z.string(),
  current_day: z.number().int().nonnegative(),
});

export const SeasonScheduleEntrySchema = z.object({
  game_index: z.number().int().nonnegative(),
  day: z.number().int().nonnegative(),
  team_pair: z.number().int().optional(),
  val1: z.number().int(),
  val2: z.number().int(),
  event_type: z.number().int(),
  event_flag: z.number().int(),
});

export const SeasonPerformanceSchema = z.object({
  record: z.number().int().nonnegative(),
  gm_first_name: z.string(),
  gm_last_name: z.string(),
  current_day: z.number().int().nonnegative(),
  budget_score: z.number().int(),
  performance_score: z.number().int(),
  active: z.number().int(),
  team_index: z.number().int(),
});

export const SeasonPlayerRatingSchema = z.object({
  record: z.number().int().nonnegative(),
}).catchall(z.number().int());

export const SeasonTransactionSchema = z.object({
  record: z.number().int().nonnegative(),
  day: z.number().int().nonnegative(),
  player_id: z.number().int().nonnegative(),
  team_from: z.number().int(),
  team_to: z.number().int(),
  event_index: z.number().int(),
  sub_type: z.number().int(),
});

export const SeasonUserTeamSchema = z.object({
  record: z.number().int().nonnegative(),
  is_user: z.boolean(),
  identifier: z.number().int(),
  counter: z.number().int(),
  games_played: z.number().int(),
});

export const SeasonFullExportSchema = z.object({
  schema: z.literal("nhl-legacy-season/0.1"),
  current_day: z.number().int().nonnegative(),
  teams: z.array(SrV1TeamSchema),
  players: z.array(SrV1PlayerSchema),
  calendar: z.array(SeasonCalendarEventSchema).optional().default([]),
  gm_states: z.array(SeasonGmStateSchema).optional().default([]),
  schedule: z.array(SeasonScheduleEntrySchema).optional(),
  performance: z.array(SeasonPerformanceSchema).optional(),
  player_ratings: z.array(SeasonPlayerRatingSchema).optional(),
  transactions: z.array(SeasonTransactionSchema).optional(),
  user_teams: z.array(SeasonUserTeamSchema).optional(),
  standings: z.unknown().optional(),
  player_details: z.unknown().optional(),
});

export type SeasonCalendarEvent = z.infer<typeof SeasonCalendarEventSchema>;
export type SeasonGmState = z.infer<typeof SeasonGmStateSchema>;
export type SeasonFullExport = z.infer<typeof SeasonFullExportSchema>;

export type SeasonScheduleEntry = z.infer<typeof SeasonScheduleEntrySchema>;
export type SeasonPerformance = z.infer<typeof SeasonPerformanceSchema>;
export type SeasonPlayerRating = z.infer<typeof SeasonPlayerRatingSchema>;
export type SeasonTransaction = z.infer<typeof SeasonTransactionSchema>;
export type SeasonUserTeam = z.infer<typeof SeasonUserTeamSchema>;

export const SEASON_SCHEMA_TOKEN = "nhl-legacy-season/0.1" as const;

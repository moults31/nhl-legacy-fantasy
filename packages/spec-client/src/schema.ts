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

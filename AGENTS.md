# Agent notes

## Tool management

This project uses [mise](https://mise.jdx.dev/) to pin tool versions and
define task commands. Always use mise to run project commands instead of
calling pnpm/turbo directly.

- `mise tasks ls` — list available tasks
- `mise run <task>` — run a named task (e.g. `mise run build`, `mise run test`)
- `mise x -- <command>` — run an ad-hoc command with tool shims active

Never run `pnpm`, `turbo`, or `tsx` directly. Always prefix with `mise run`
or `mise x --`.

## Project shape

This is a TypeScript monorepo (pnpm workspaces + turbo):

- `apps/api` — Fastify backend, SQLite WR database, mule CLI integration.
- `apps/web` — Vite + React PWA frontend.
- `packages/spec-client` — TypeScript/Zod bindings and WR→SR translator for the
  external spec repo.

The spec repo lives at `https://github.com/moults31/nhl-legacy-roster-spec.git`
and is consumed as a **pnpm git dependency** (`#main` branch). Do not copy
its contents into this repo; update the branch/tag in
`packages/spec-client/package.json` when moving to a new SR version.

The mule repo lives at `https://github.com/moults31/nhl-db-studio-mule.git`
and is consumed as a **Cargo git dependency** (`main` branch). `scripts/setup.sh`
runs `cargo install` to build the `roster-cli` binary into `.cargo-bin/`.

## Local reference material

Same policy as the predecessor repo:

- Everything game/modding-related belongs under `/_local/` (gitignored).
- Do not commit binaries, game assets, or third-party modding tool trees.
  **Exception:** `tests/fixtures/xbox/` contains a small canonical roster .bin
  (the 2026 trade deadline update) used by the test suite and as the default
  `VANILLA_ROSTER_BIN`.  This is a controlled-size fixture, not a raw game dump.
- No upstream source code from Modding Studio, `nhl-database-studio`, etc.

## Database

- SQLite via `better-sqlite3`.
- Schema: `apps/api/data/schema.sql`
- Seed data: `apps/api/data/seed.sql`
- Reset: `pnpm db:reset`

The WR tables (`teams`, `players`) use stable IDs/slugs. The mapping tables
(`team_mappings`, `player_mappings`) connect WR IDs to the NR-leaky values of
the current SR version. In production these mappings are seeded from a vanilla
roster export produced by the mule.

## Mule integration

The backend invokes `nhl-db-studio-mule` as a subprocess:

1. `mule unpack <vanilla.bin> -o default.db`
2. `mule import -o edited.db default.db roster.json`
3. `mule pack-fdeflate edited.db -o roster.bin`

For the export endpoint to work, `VANILLA_ROSTER_BIN` must be set and the mule
binary must be on `PATH` (or `MULE_BINARY` must point to it).

## Conventions

- Prefer TypeScript for the webapp. Rust is only for the external mule/studio.
- Keep `packages/spec-client` as the only place that knows about SR schema
  details. Other packages should use its exported types and `buildSrV1Roster`.
- The WR model must not use `record` or `proteam` values directly.
- When adding a new SR version, create a new translator/schema file in
  `packages/spec-client`, keep the old one, and switch callers over.

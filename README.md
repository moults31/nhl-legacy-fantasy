# NHL Legacy Fantasy

A webapp for building custom NHL Legacy Edition rosters from a stable webapp
representation (WR), producing game-ready `.bin` save files via
[`nhl-db-studio-mule`](https://github.com/moults31/nhl-db-studio-mule).

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────────┐
│  Webapp WR  │────▶│  SR v1 (spec)   │────▶│  nhl-db-studio-mule │
│  (SQLite)   │     │  JSON document  │     │  CLI: import/pack   │
└─────────────┘     └─────────────────┘     └─────────────────────┘
```

- **WR** — webapp's internal model: stable player IDs and team slugs, plus
  `main_team`. Independent of any NR/SR version.
- **SR** — spec repo [`nhl-legacy-roster-spec`](https://github.com/moults31/nhl-legacy-roster-spec):
  versioned JSON Schema (`nhl-legacy-roster/0.1`) consumed by both webapp and
  producer. v1 is WR-aligned; v2 (future) will be NR-aligned when
  `nhl-database-studio` replaces the mule.
- **NR** — the game-compatible representation inside the mule/studio.

The webapp backend shells out to the mule CLI: `unpack` → `import` (SR patch)
→ `pack-fdeflate` → `.bin` download.

## Monorepo structure

```
apps/
  api/          Fastify + SQLite backend
  web/          Vite + React PWA frontend
packages/
  spec-client/  Hand-derived TS/Zod bindings + WR→SR translator for the spec
```

## Prerequisites

- Node.js 20+
- pnpm 10+ (managed by `packageManager`)
- `nhl-db-studio-mule` binary installed and on `PATH`
- A vanilla NHL Legacy roster `.bin` file

## Quick start

```bash
# Install dependencies and build workspace packages
pnpm install
pnpm --filter @nlf/spec-client build
pnpm --filter @nlf/api db:seed

# Terminal 1: backend
VANILLA_ROSTER_BIN=/path/to/vanilla/roster.bin pnpm --filter @nlf/api dev

# Terminal 2: frontend
pnpm --filter @nlf/web dev
```

Open http://localhost:5173.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3001` | API port |
| `DATABASE_URL` | `apps/api/data/dev.db` | SQLite database path |
| `MULE_BINARY` | `nhl-db-studio-mule` | Mule CLI binary name/path |
| `VANILLA_ROSTER_BIN` | — | **Required.** Path to vanilla roster `.bin` |
| `CORS_ORIGIN` | `http://localhost:5173` | Allowed CORS origin |

## Scripts

```bash
pnpm dev            # start all apps in dev mode (turbo)
pnpm build          # build all apps
pnpm db:seed        # seed dev database
pnpm db:reset       # delete and re-seed dev database
```

## Testing

```bash
pnpm --filter @nlf/spec-client test
```

## Versioning the producer seam

The spec repo is the neutral contract. When `nhl-database-studio` arrives we
will cut SR v2 aligned with its NR, and only the `packages/spec-client`
translator needs to change — the WR model stays the same.

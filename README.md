# NHL Legacy Fantasy

[![CI](https://github.com/moults31/nhl-legacy-fantasy/actions/workflows/ci.yml/badge.svg)](https://github.com/moults31/nhl-legacy-fantasy/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Node.js 22+](https://img.shields.io/badge/node-22%2B-green.svg)](https://nodejs.org/)
[![pnpm 10+](https://img.shields.io/badge/pnpm-10%2B-orange.svg)](https://pnpm.io/)

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

- [mise](https://mise.jdx.dev/) — manages Node.js, pnpm, and task scripts
- Rust toolchain (`cargo`) — needed to build the mule CLI binary
- A vanilla NHL Legacy roster `.bin` file

## Quick start

```bash
# Install pinned tools and workspace dependencies
mise trust
mise install
mise run install

# Build packages and seed the database
mise run build
mise run db:seed

# Terminal 1: backend
mise run dev:api

# Terminal 2: frontend
mise run dev:web
```

Open http://localhost:5173.

List all available commands: `mise tasks ls`

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
mise run dev            # start all apps in dev mode (turbo)
mise run dev:api        # start backend only
mise run dev:web       # start frontend only
mise run build          # build all apps
mise run lint           # typecheck all packages
mise run test           # run tests
mise run db:seed        # seed dev database
mise run db:reset       # delete and re-seed dev database
```

## Testing

```bash
mise run test
```

## Versioning the producer seam

The spec repo is the neutral contract. When `nhl-database-studio` arrives we
will cut SR v2 aligned with its NR, and only the `packages/spec-client`
translator needs to change — the WR model stays the same.

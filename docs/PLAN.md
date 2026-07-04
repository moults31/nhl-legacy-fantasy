# Plan: Linux roster path for NHL Legacy Fantasy

## Goal

Build a **Rust** CLI and libraries that can:

1. Read and write NHL Legacy roster saves that the game will load
2. Edit them **semantically** (players, teams, ratings, assignments)
3. Install them into a local Legacy install for play

This is the foundation for a mostly-offline social fantasy-hockey game: fantasy state lives here; Legacy is the presentation layer.

Prefer **Rust** for all tools and libraries unless something is clearly better done another way.

## Inputs we rely on (local, not in git)

See [AGENTS.md](../AGENTS.md). In short:

- Modding Studio `defs/` and vanilla roster saves
- EADBEditor field dictionary (`NHL 14 xml.xml`) and assemblies to reverse for checksums / TDB write
- A working Legacy install and its Proton save directory for load tests
- Recomp tree only as reference for existing TDB experiments

## Architecture

Three layers, one CLI surface:

| Layer | Responsibility |
|-------|----------------|
| **Container** | `RosterFile` pack/unpack (header + zlib payload) and install into the Xenia-style content tree (payload + `.header`) |
| **TDB** | Read/write EA TDB (`default.db`): bit-packed tables, field descriptors, CRC reseal |
| **Semantic** | Map tables/fields to players, teams, ratings; JSON export/import for fantasy automation |

Always **patch a known-good base roster DB** (vanilla or an existing custom save). Do not synthesize a full TDB from scratch.

### Semantic model (game tables)

| Table | Role |
|-------|------|
| `ubPc` | Player bios |
| `kOtt` | Teams |
| `ZBac` | Player index |
| `eGlu` | Rosters and lines |
| `dSvy` / `mHuy` | Skater / goalie ratings |

Field display names come from EADBEditor’s `NHL 14 xml.xml`. Foreign keys and enums come from Modding Studio `defs/`.

## Milestones

1. **Unpack** — `RosterFile` → `default.db`; bit-identical to the zlib payload on vanilla and a live custom save
2. **Pack** — unchanged body round-trips to a byte-identical container (proves header checksums; port feudalnate `EAChecksum` from EADBEditor)
3. **TDB edit** — parse tables, set fields, reseal TDB CRCs (informed by EADBEditor / existing recomp experiments)
4. **Semantic I/O** — export/import players and teams as JSON (team assignment + a few bio/rating fields first)
5. **Install + verify** — write save + header into the Proton content path; confirm load in Legacy
6. **CLI** — `unpack` / `pack` / `install` / `export` / `import` suitable for fantasy automation

## Later (after the roster path works)

- Feed fantasy/historical rosters from `nhl-ratings-archive` (or a slim export) into our JSON import
- Broader fantasy game features (leagues, seasons, social) on top of this compile-to-Legacy step

## Out of scope for this plan

- Running Windows GUIs as the primary workflow
- Full Modding Studio feature parity (portraits, equipment shop, audio, etc.)
- Editing on-disc `nhlng.db` for roster swaps (roster **saves** are the load path)

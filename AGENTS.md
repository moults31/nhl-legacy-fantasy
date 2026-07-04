# Agent notes

## Gitignored local material (`_local/`)

These paths are **not** in git. They must exist on the machine for format work, schema lookup, and in-game verification. Symlinks to sibling checkouts under the parent `nhl-legacy` workspace are fine.

| Path | What should be here | Why |
|------|---------------------|-----|
| `_local/modding-tools/EADBEditor/` | Community EA DB Editor (especially `NHL 14 xml.xml`, `EAChecksum.dll`, `EA DB Editor.exe`) | Field name dictionary and algorithms to port for roster DB read/write and save checksums |
| `_local/modding-tools/NHL Modding Studio 0.1.0-beta.3 portable/` | Portable Modding Studio (`defs/`, `vanilla-saves/`, optional full app) | Confirmed table relationships, enums, and known-good vanilla roster saves |
| `_local/modding-tools/nhl-ratings-archive/` | Clone of the ratings/archive app (source) | Future fantasy/historical content pipeline; not required for the first roster CLI |
| `_local/nhl-legacy-recomp/` | NHL Legacy recomp source tree | Existing TDB experiment notes/tools (`tools/stick_widen`) and game integration context |
| `_local/NHL Legacy Recomp/` | Working game install (`nhllegacy.exe`, `game/`, launch script) | Load custom rosters and confirm edits in-game |

### Outside this repo (document only)

Roster saves for the Proton-launched install typically live under the Steam compatdata prefix, e.g. `…/compatdata/<appid>/pfx/drive_c/users/steamuser/Documents/nhllegacy/`. Agents should treat that path as the install target for load tests, not as something committed here.

## Conventions

- Prefer **Rust** for tools and libraries unless there is a strong reason not to.
- Follow [docs/PLAN.md](docs/PLAN.md) for scope and milestones.
- Do not commit binaries, game assets, or third-party modding tool trees from `_local/`.

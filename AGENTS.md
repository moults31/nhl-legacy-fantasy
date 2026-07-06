# Agent notes

## Gitignored local material (`_local/`)

**Everything agents need is under `./_local/`** — do not search outside the checkout for modding tools, vanilla saves, the game install, or roster saves. Symlinks into `_local/` are fine.

Full inventory, the McTavish edit pair, and save paths: **[docs/LOCAL-ARTIFACTS.md](docs/LOCAL-ARTIFACTS.md)**.

| Path | What should be here | Why |
|------|---------------------|-----|
| `_local/modding-tools/EADBEditor/` | Community EA DB Editor (`NHL 14 xml.xml`, `EAChecksum.dll`, `EA DB Editor.exe`) | Field name dictionary and algorithms to port for roster DB read/write and save checksums |
| `_local/modding-tools/NHL Modding Studio 0.1.0-beta.3 portable/` | Portable Modding Studio (`defs/`, `vanilla-saves/`, optional full app) | Confirmed table relationships, enums, and known-good vanilla roster saves |
| `_local/modding-tools/nhl-ratings-archive/` | Clone of the ratings/archive app (source) | Future fantasy/historical content pipeline; not required for the first roster CLI |
| `_local/nhl-legacy-recomp/` | NHL Legacy recomp source tree | Existing TDB experiment notes/tools (`tools/stick_widen`) and game integration context |
| `_local/NHL Legacy Recomp/` | Working game install (`nhllegacy.exe`, `game/`, `launch-nhl-legacy.sh`) | Load custom rosters and confirm edits in-game |
| `_local/game-saves/xbox/` | **`roster1.bin`**, **`testroster.bin`** (+ `.header` sidecars) | In-game save pair: McTavish Anaheim → St. Louis (`TESTROSTER` vs pre-move `ROSTER1`, 2026-07-04) |
| `_local/game-saves/proton-snapshot/` | Symlink to live `454109EC` content tree | Optional; tracks Proton writes without copying |

### Proton save location (reference only)

The game still writes saves under Steam compatdata when launched via `launch-nhl-legacy.sh` (app id **3623314720**). Stable copies for tests live in `_local/game-saves/xbox/`. See [docs/LOCAL-ARTIFACTS.md](docs/LOCAL-ARTIFACTS.md) for the full path pattern.

## Reference source policy

**No upstream source code will ever be added** (Modding Studio, `nhl-database-studio`, `tdb-savedata`, `tdb-core`, etc.). Do not ask for it or defer work waiting for it. Port algorithms from `_local/` binaries (IL/binary RE), fixtures, and in-game oracles. Full policy and milestone order: **[docs/REFERENCE-POLICY.md](docs/REFERENCE-POLICY.md)**.

## Conventions

- Prefer **Rust** for tools and libraries unless there is a strong reason not to.
- Follow [docs/PLAN.md](docs/PLAN.md) for scope and milestones.
- Do not commit binaries, game assets, or third-party modding tool trees from `_local/`.

## Archived diagnostic scripts

The `DO-NOT-MERGE` branch archives ~70 diagnostic/experimental Python scripts
and Rust test files from the roster move discovery phase (D1D2 chain reverse
engineering, MS CC team ID mapping, CRC analysis). These are one-off tools, not
part of the active pipeline. If you need to revisit a particular analysis, check
that branch; do not merge it into `main`.

### Tools kept on `main`

| Path | Purpose |
|------|---------|
| `tools/install_recomp_roster.py` | Install a packed roster blob into the game save tree |
| `tools/gen_roster_db.py` | Regenerate `roster_db.rs` from CSV exports |

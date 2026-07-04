# Reference source policy

**No additional reference source code will ever be provided for this project.**

Everything agents may use is already in this checkout:

| Available | Not coming — do not wait or defer |
|-----------|-----------------------------------|
| `_local/modding-tools/EADBEditor/` (binaries + `NHL 14 xml.xml`) | Modding Studio / `nhl-database-studio` source |
| `_local/modding-tools/NHL Modding Studio 0.1.0-beta.3 portable/` (`defs/`, vanilla saves, **exe only**) | `tdb-savedata`, `tdb-core`, or other Rust crate sources |
| `_local/nhl-legacy-recomp/` (recomp tree; `stick_widen` notes) | Sibling checkout paths outside `_local/` (e.g. `../../../nhl-database-studio/`) |
| `_local/game-saves/xbox/` (McTavish pair, baselines) | Upstream repos, private forks, or “when we get the source” |
| Committed Rust in this repo | Windows GUI automation as the primary workflow |

## How to proceed

When an algorithm is unknown, **derive it here** — do not open issues or PR notes that block on external source.

1. **IL / binary reverse engineering** — `EA DB Editor.exe`, `EAChecksum.dll`, `NHL Modding Studio.exe` (strings, embedded paths, Cecil/IL dumps).
2. **Fixture oracles** — `_local/game-saves/xbox/{roster1,testroster}.bin`, `tests/fixtures/`, Modding Studio `vanilla-saves/`.
3. **Schema and field names** — `NHL 14 xml.xml`, Modding Studio `defs/`.
4. **In-game verification** — milestone 5 load test via `_local/NHL Legacy Recomp/`.

## Milestone order (checksum work)

| Layer | Blocker | Path forward |
|-------|---------|--------------|
| **M3 TDB CRC** | Reseal `default.db` internal CRCs | Port `DBFileInfo.CalcChecksums` from EA DB Editor IL (`DB_CRC.crc32_be`, `len` then `start`) |
| **M2 container** | `RosterFile` u32 @ `0x10` / `0x28` | Reverse embedded `tdb-savedata` logic in `NHL Modding Studio.exe`; McTavish pair as oracle |
| **M4+ semantic** | Table id mapping | `NHL 14 xml.xml` + `defs/` — no source required |

M3 unblocks TDB edits; M2 unblocks `pack()` for edited payloads. Both are independent of any future source drop because **there will be none**.

## Agent checklist

- Do **not** ask the user for Modding Studio source, `tdb-savedata`, or `tdb-core`.
- Do **not** defer tasks with “once we have the source tree”.
- Do **not** search parent directories outside this repo for sibling checkouts.
- Do port algorithms from IL, run discovery tests, and document findings in `docs/M2-PACK.md` / `docs/M3-TDB.md`.

# Local modding tools (`_local/modding-tools/`)

Reference material under `_local/` is gitignored but should be symlinked locally (see [AGENTS.md](../AGENTS.md)). Use these assets to inform and validate Rust implementations — do not commit binaries or vendor them into the repo.

## EADBEditor bundle

Path: `_local/modding-tools/EADBEditor/`

| File | Role in our milestones |
|------|------------------------|
| `NHL 14 xml.xml` | Field display names → 4-char TDB IDs (M4 semantic I/O) |
| `EAChecksum.dll` | Custom 1024-entry rotation-table hash (.NET); used by MC02Handler |
| `MC02Handler.dll` | Xbox **MC02** save package read/write; hashes via `EAChecksum.TransformBlock` |
| `EA DB Editor.exe` | Opens `.DB` or `.MC02`; TDB internal CRCs via `DB_CRC.crc32_be` (M3) |

### Two container paths

Proton/Legacy roster saves on disk use the **`RosterFile\0`** wrapper (milestone 1 `roster-container`). That is what the game loads from `Documents/nhllegacy/`.

EA DB Editor instead works with **MC02 packages** extracted from rosters (`MaddenDatabase`: *"You must first extract the MC02 / DB file from the roster!"*). MC02 uses `EAChecksum` for header/descriptor/savedata hashes through `MC02Handler.Package`.

As of milestone 1, the u32 at `RosterFile` offset **0x10** has **not** been matched by invoking `EAChecksum` over obvious byte ranges on a live Proton save. Treat RosterFile container checksum (M2) and MC02/EAChecksum as related but distinct until proven otherwise.

### EAChecksum algorithm (for porting)

Reverse-engineered from `EAChecksum.dll` via IL inspection:

- Default lookup table: 1024 × `u32` (initialized in `EAChecksum..ctor`)
- `CacheFirstBlock`: derives `Last` from the first 4 bytes using rotates/OR/NOT
- Main loop: rotate `Last` left 10, index table (`NextIndex`), shift/OR next byte, XOR with table value
- `get_GetHash`: returns `~Last`
- `get_GetHashBytes`: `BitConverter.GetBytes(hash)` then **byte-reverse** (big-endian on wire)

MC02Handler calls `TransformBlock` (not `TransformFinalBlock`) then reads `get_GetHashBytes`.

### TDB CRC (milestone 3)

Inside `default.db`, EA DB Editor reseals with **`DB_CRC.crc32_be`** (standard CRC-32 table, big-endian convention). Port this for `ea-tdb`, not `EAChecksum`.

## NHL Modding Studio portable

Path: `_local/modding-tools/NHL Modding Studio 0.1.0-beta.3 portable/`

| Path | Use |
|------|-----|
| `defs/` | Confirmed table FKs, enums, relationships (M4) |
| `vanilla-saves/` | Optional roster test vectors (drop blobs per README there) |
| `extractor/` | `.big` archive extraction reference |

## Validation on Linux

The EADBEditor bundle is .NET Framework 2.0. On Linux, load `EAChecksum.dll` with **.NET 8 + reflection** (works for calling `TransformBlock` / `get_GetHash`). Full GUI (`EA DB Editor.exe`) requires Windows/Mono.

Use extracted tables and IL as golden references when porting to Rust; keep a small dotnet harness under `tools/` (optional) for cross-checks during M2/M3 development.

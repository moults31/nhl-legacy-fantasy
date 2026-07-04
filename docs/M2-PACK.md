# Milestone 2: RosterFile pack and container checksum

This document records milestone 2 from [PLAN.md](PLAN.md).

## Goal

Round-trip an unchanged roster save byte-for-byte:

```
pack(unpack(save)) == save
```

## Status (2026-07-04)

| Item | Status |
|------|--------|
| `pack_unchanged` / unchanged round-trip test | **Done** — byte-identical on fixture |
| `EaChecksum` Rust port (MC02 path) | **Done** — validated against `EAChecksum.dll` (`[1..=10]` → `0xA1112550`) |
| Container `@0x10` / `@0x28` checksums | **Done** — reverse-engineered from `NHL Modding Studio.exe` |
| `pack()` for edited DBs | **Done** — seals both checksums; zlib level may differ from original |
| Discovery harness | **Done** — `checksum_discover*.rs`, `checksum_oracle.rs` |
| Full M2 acceptance (`pack(unpack(save)) == save` for edited saves) | **Partial** — checksums correct; byte-identical repack requires matching deflate |
| M5 in-game load (unchanged repack) | **Pass** — M5CHK01 |
| M5 in-game load (edited repack) | **In progress** — M5MCT01 pending operator test |

## Prerequisites

1. **EADBEditor bundle** — available at `_local/modding-tools/EADBEditor/` (`EAChecksum.dll`, `MC02Handler.dll`, `EA DB Editor.exe`, `NHL 14 xml.xml`). See [MODDING-TOOLS.md](MODDING-TOOLS.md).
2. **Working M1 unpack** — `roster-container` extracts a bit-identical TDB payload; header fields are parsed in `RosterHeader`.
3. **Fixture** — `tests/fixtures/xbox/roster.bin` from a Proton save.

## Observed Xbox 360 header layout (48 bytes)

| Offset | Size | Field | Notes |
|--------|------|-------|-------|
| 0x00 | 16 | magic | `RosterFile\0` + padding |
| 0x10 | 4 | checksum_primary | u32 BE; IEEE reflected CRC-32 over `[0x1c .. end)` |
| 0x14 | 4 | field_0x14 | u32 BE; observed `4` (container version) |
| 0x18 | 4 | field_0x18 | u32 BE; observed `0` |
| 0x1C | 4 | field_0x1c | u32 BE; observed `1` |
| 0x20 | 4 | field_0x20 | u32 BE; observed `1` on Legacy saves (`2` on older fixture) |
| 0x24 | 4 | uncompressed_size | u32 BE; equals TDB byte length |
| 0x28 | 4 | checksum_secondary | u32 BE; MSB-first CRC-32 (poly `0x04C11DB7`) over `[0x2c .. end)` |
| 0x2C | 4 | field_0x2c | u32 BE; upper 16 bits vary; lower 16 often `0x0C00` on Legacy saves |
| 0x30 | rest | zlib payload | standard zlib (`0x78 0x9c`) |

## Checksum strategy

`EAChecksum.dll` is the feudalnate algorithm used by **`MC02Handler`** for Xbox MC02 save packages. EA DB Editor opens MC02-wrapped content, not raw `RosterFile` blobs.

### Algorithm (confirmed 2026-07-04)

Reverse-engineered from `NHL Modding Studio.exe` pack path (`0x140b460d3` / `0x140b4622d` / `0x140b47db0`):

| Field | Input slice | Primitive | Init | Final |
|-------|-------------|-----------|------|-------|
| `@0x10` | `[0x1c .. file_end)` | IEEE reflected CRC-32 | `0xFFFFFFFF` | `!crc` |
| `@0x28` | `[0x2c .. file_end)` | MSB-first CRC-32 (`0x04C11DB7`) | `0xFFFFFFFF` | `!crc` |

Write order: seal `@0x28` first, then `@0x10` (primary input includes the sealed `@0x28` field).

Rust: `crates/roster-container/src/container_checksum.rs` (`seal_checksums`, `verify_checksums`).

Oracle validation: `tests/checksum_oracle.rs` against `_local/game-saves/xbox/{roster1,testroster}.bin`, fixture, and Modding Studio vanilla 360 save when present.

### M5 in-game verification (2026-07-04)

| Save | Description | Result |
|------|-------------|--------|
| **M5CHK01** | Unchanged `testroster` repack, new slot name | **Pass** |
| **M5ANA01** | `roster1` DB + `testroster` template (wrong `@0x2c` + over-compressed zlib) | **Fail** — damaged |
| **M5ANA02** | `roster1` DB + `roster1` template | **Pass** — McTavish on Anaheim |
| **M5MCT01** | `testroster` DB with `cPbu.WBbd` patched to Anaheim + repack | **Fail** — damaged (v1 ~818 KB, v2 ~2.456 MB stored blocks) |

If a damaged M5 slot blocks the title screen, remove it with `python3 tools/install_m5_saves.py --remove M5MCT01`. Legacy auto-loads the active roster on startup.

### Edited repack gate (M5MCT01, confirmed 2026-07-04)

**Unchanged** round-trips load (M5CHK01, M5ANA02). **Any recompressed payload fails**, even when:

- Container checksums `@0x10` / `@0x28` verify in Rust
- Zlib header is `78 9c` and payload is ~2.45 MB (near-stored stored blocks)
- `@0x2c` is copied from the template save

Game originals use a **single dynamic-Huffman deflate block** at ~1:1 ratio (`789cec7b…`). Our encoders (default flate2, stored blocks) produce a different bitstream; the game rejects them as damaged. Single-byte TDB edits cannot reuse the template compressed bytes.

**Next:** reverse `pack_xbox_save` from `NHL Modding Studio.exe` (embedded `tdb-savedata`) or clone the original dynamic block tables. Until then, semantic edits work in TDB (`write_field`) but cannot be installed via `pack()`.

**Interim for Anaheim baseline:** repack unchanged `roster1.bin` (M5ANA02) or edit in-game from TESTROSTER.

Edited repack requirements learned from M5:

1. **Template match** — use the template save whose header metadata matches the payload lineage.
2. **Near-stored deflate** — game saves are ~1:1 with `78 9c` (~2.45 MB). Default flate2 (~818 KB) lists but fails load (M5ANA01 / M5MCT01 v1). Edited repacks use stored deflate blocks under `78 9c` (~2.456 MB).
3. **`@0x2c` override** — upper 16 bits are content-dependent; pass a reference value until the algorithm is reversed (`pack_with_field_0x2c`).

Install helper: `tools/install_m5_saves.py` (optional `--only M5MCT01`). **Building the blob alone does not install it** — run the script (or copy blob + `.header` sidecar) before refreshing in-game.

### Discovery history

Brute-force over obvious slices (`checksum_discover` + `checksum_discover_extended`) ruled out `EAChecksum`, TDB `Crc32Be`, chained CRC, zlib digests, and MD5/SHA1 truncations before binary RE identified the dual-CRC layout above.

**TDB internal CRCs** (M3) are a separate layer. In-game saves keep stale TDB CRC fields; M2 container checksum is what changes on save.

## Implementation steps

1. Implement `ea_checksum` module in `roster-container` — **done** (table embedded from DLL; golden test vs .NET 8 reflection).
2. **`pack` API** — **partial**:

   ```rust
   pub fn pack(db: &[u8], template: &RosterHeader) -> Result<Vec<u8>>;
   ```

   Recompress with zlib, copy template header fields, update `uncompressed_size`, write checksum once algorithm is confirmed.
3. **Round-trip test** — `pack(unpack(save)) == save` on the fixture.
4. **In-game verification** — milestone 5.

## Out of scope for M2

- TDB internal CRC reseal (milestone 3 — `DB_CRC.crc32_be` from EA DB Editor, see [MODDING-TOOLS.md](MODDING-TOOLS.md))
- PS3 `PS3RosterFile` pack format
- Proton content-tree install (milestone 5)

## Risks

| Risk | Mitigation |
|------|------------|
| RosterFile checksum ≠ EAChecksum | Use MC02Handler/EAChecksum for MC02 path; keep searching for RosterFile-specific rule |
| zlib compression level differs | Reuse original compressed bytes when DB unchanged; match deflate params |
| Xbox checksum write-back unverified | M5 in-game load is acceptance gate |

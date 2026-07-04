# Milestone 3: TDB parse and CRC reseal

Scope from [PLAN.md](PLAN.md): read/write EA TDB (`default.db`), reseal internal CRCs after edits.

## Status

| Item | Status |
|------|--------|
| `ea-tdb` crate | **In progress** (merged #2; follow-up on branch) |
| Directory / table parse | **Done** — EA DB Editor layout (8-byte directory, 40-byte info, 16-byte fields) |
| Bit-packed field read | **Done** — `read_bits` / `TableLayout::read_field` |
| Bit-packed field write | **Partial** — `write_bits` helper; no table writer yet |
| CRC reseal | **Not started** |
| Semantic tables (`ubPc`, `kOtt`, …) | **Internal ids in save** — see note below |
| McTavish move diff fixture | **Available** — `_local/game-saves/xbox/{roster1,testroster}.bin` |

## `ea-tdb`

- **`Crc32Be`** — EA DB Editor `DB_CRC.crc32_be`
- **`TdbFile`** — file header + directory
- **`TableLayout`** — 40-byte info block + field descriptors + `read_field`

Layout reverse-engineered from EA DB Editor IL (`DBTable.ReadTableHeader`, `Field.ReadEntry`).

## On-disk layout (Legacy roster TDB)

| Region | Size | Notes |
|--------|------|-------|
| File header | `0x14` | magic, endian, `source_size`, table count |
| File header CRC | 4 @ `0x14` | reseal TBD |
| Directory | `8 × count` @ `0x18` | table id + BE offset into table data |
| Table data start | `0x18 + 8×count` | `0x150` on fixture (39 tables) |

### Directory entry (8 bytes)

| Offset | Field |
|--------|-------|
| 0 | table id (ASCII) |
| 4 | offset from table data start to **info block** (BE u32) |

### Table info block (40 bytes, `DBTable.infosize`)

| Offset | Field |
|--------|-------|
| 0 | on-disk table id (ASCII) |
| 4 | `unknown_2` (often `6`) |
| 8 | `record_length_bytes` |
| 12 | `record_length_bits` |
| 20 | `max_records` (u16 BE) |
| 22 | `current_records` (u16 BE) |
| 28 | `num_fields` (u8) |
| 36 | `header_crc` (u32 BE; reseal TBD) |

### Field descriptor (16 bytes)

| Offset | Field |
|--------|-------|
| 0 | `kind_code` (u32 BE) |
| 4 | `record_bit_offset` (u32 BE) |
| 8 | field id (ASCII) |
| 12 | `bit_width` (u32 BE) |

Records begin at `info_offset + 40 + num_fields×16`.

## Semantic tables note

Unpacked Legacy roster `default.db` files do **not** contain literal `ubPc` / `kOtt` / `eGlu` strings. The 39 top-level directory tables use internal ids (`ajmx`, `OEtS`, …). Map semantic names via `NHL 14 xml.xml` and Modding Studio `defs/` (e.g. `ubPc.dXSB` → team id).

## In-game edit pair (2026-07-04)

Operator moved **Mason McTavish** (Anaheim → St. Louis) and saved as **`TESTROSTER`**. Pre-move baseline: **`ROSTER1`**. Copies under `_local/game-saves/xbox/` — see [LOCAL-ARTIFACTS.md](LOCAL-ARTIFACTS.md).

Integration test `crates/ea-tdb/tests/mctavish_move.rs` unpacks both saves and checks shape, McTavish presence, container checksum change, and record reordering on save. Use this pair for CRC/checksum and team-field discovery (offset-stable diffs are not expected).

## Next steps

1. CRC reseal — file header @ `0x14`, table `header_crc` @ info+36
2. `write_field` + table writer
3. Resolve internal table id → `ubPc` / `dXSB` for programmatic team moves
4. M2 — diff container checksum @ `0x10` between `roster1.bin` and `testroster.bin`

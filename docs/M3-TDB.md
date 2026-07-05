# Milestone 3: TDB parse and CRC reseal

Scope from [PLAN.md](PLAN.md): read/write EA TDB (`default.db`), reseal internal CRCs after edits.

**Reference policy:** [REFERENCE-POLICY.md](REFERENCE-POLICY.md) — no `tdb-core` / Modding Studio source; port from EA DB Editor IL and validate with fixtures.

## Status

| Item | Status |
|------|--------|
| `ea-tdb` crate | **Done** (2026-07-04) |
| Directory / table parse | **Done** — EA DB Editor layout (8-byte directory, 40-byte info, 16-byte fields) |
| Bit-packed field read | **Done** — `read_bits` / `TableLayout::read_field` |
| Bit-packed field write | **Done** — `write_field` on `TableLayout` with CRC reseal after patch |
| CRC reseal | **Done** — `reseal_checksums` / `verify_checksums` from EA DB Editor IL; M3 acceptance test confirms self-consistency |
| Game-save CRC fields | **Stale on save** — Legacy does not rewrite TDB CRCs in-game; our tool reseal is self-consistent |
| Semantic tables (`ubPc`, `kOtt`, …) | **Mapped** — `cPbu` = exhibition player bio; team move = `WBbd` (`proteam`) |
| McTavish move diff fixture | **Available** — `_local/game-saves/xbox/{roster1,testroster}.bin` |

## `ea-tdb`

- **`Crc32Be`** — EA DB Editor `DB_CRC.crc32_be(crc, data, len, start)` (note **`len` before `start`**)
- **`reseal_checksums`** — `DBFileInfo.CalcChecksums` chain (header @ `0x14`, table `prior_crc` / `header_crc`, EOF)
- **`TdbFile`** — file header + directory
- **`TableLayout`** — 40-byte info block + field descriptors + `read_field`

Layout reverse-engineered from EA DB Editor IL (`DBTable.ReadTableHeader`, `Field.ReadEntry`, `CalcChecksums`).

## On-disk layout (Legacy roster TDB)

| Region | Size | Notes |
|--------|------|-------|
| File header | `0x14` | magic, endian, `source_size`, table count |
| File header CRC | 4 @ `0x14` | EA DB Editor reseal target; **unchanged on in-game save** |
| Directory | `8 × count` @ `0x18` | table id + BE offset into table data |
| Table data start | `0x18 + 8×count` | `0x150` on fixture (39 tables) |
| EOF CRC | 4 @ `file_len - 4` | often `0xDBDBDBDB` on Legacy saves; reseal overwrites |

### Directory entry (8 bytes)

| Offset | Field |
|--------|-------|
| 0 | table id (ASCII) |
| 4 | offset from table data start to **info block** (BE u32) |

### Table info block (40 bytes, `DBTable.infosize`)

| Offset | Field |
|--------|-------|
| 0 | `prior_crc` / `calcPcrc` (chained gap CRC; **not** a table id) |
| 4 | `unknown_2` (often `6`; allocation type in `tdb-core`) |
| 8 | `record_length_bytes` |
| 12 | `record_length_bits` |
| 20 | `max_records` (u16 BE) |
| 22 | `current_records` (u16 BE) |
| 28 | `num_fields` (u8) |
| 36 | `header_crc` (u32 BE; `~crc32_be` over info bytes 4..35) |

Table ids appear only in the **directory**, not in the info block.

## Legacy in-game save behavior (2026-07-04 McTavish pair)

Unpacking `roster1.bin` vs `testroster.bin` after an in-game roster edit:

| Field | Changes on game save? |
|-------|------------------------|
| RosterFile checksum @ `0x10` / `0x28` | **Yes** (M2 blocker) |
| TDB file header CRC @ `0x14` | **No** (identical `0x21E36BFD`) |
| Table `prior_crc` / `header_crc` (e.g. `ajmx`) | **No** |
| TDB payload bytes | **Yes** (~32% differ) |

The game loads saves with **stale** internal TDB CRC fields. Our EA DB Editor reseal is for **tool-written** DBs (consistent CRC chain); it does not round-trip existing game CRC bytes. Acceptance: `reseal_checksums` is idempotent on its own output; M5 confirms load after we pack with M2.

### TDB bit-field endian (Legacy roster saves)

File header byte @ `0x04` is `0x01` on observed Xbox saves. That marker selects **MSB-first** bit packing (`Endian::Big` in `ea-tdb`), not little-endian within each byte. Using the wrong order misreads numeric fields (e.g. `cPbu.WBbd` / `proteam`).

## McTavish team move (2026-07-04 pair)

In-game **Player Movement** updates **`cPbu.WBbd`** (`proteam`), not **`cPbu.BSXd`** (`team`):

| Save | McTavish `WBbd` | Team |
|------|-----------------|------|
| `roster1.bin` | `1` | Anaheim Ducks |
| `testroster.bin` | `25` | St. Louis Blues |

Only **one raw byte** differs inside the McTavish `cPbu` record between the pair (bit-packed `proteam` at record offset +115). Record index (`1424`) is stable across the pair despite file-offset reorder on save.

## Semantic tables note

Unpacked Legacy roster `default.db` files do **not** contain literal `ubPc` / `kOtt` / `eGlu` strings. The 39 top-level directory tables use internal ids (`ajmx`, `OEtS`, …). Map semantic names via `NHL 14 xml.xml` and Modding Studio `defs/`.

## Next steps

1. ~~M5 operator test **M5MCT01**~~ — resolved via exact-code template deflate re-encode (see M2-PACK.md)
2. M4: Semantic JSON export/import — see [M4-SEMANTIC.md](M4-SEMANTIC.md)
3. Reverse `@0x2c` upper-16 algorithm (may be coupled to deflate bitstream)

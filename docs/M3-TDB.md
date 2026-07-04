# Milestone 3: TDB parse and CRC reseal

Scope from [PLAN.md](PLAN.md): read/write EA TDB (`default.db`), reseal internal CRCs after edits.

## Status

| Item | Status |
|------|--------|
| `ea-tdb` crate | **In progress** — CRC, header, directory, table layout parse |
| Directory / table parse | **Partial** — 8-byte directory, 16+12-byte table headers |
| Field read/write | **Not started** |
| CRC reseal (`write_tdb`) | **Not started** |

## `ea-tdb` (initial)

- **`Crc32Be`** — port of EA DB Editor `DB_CRC.crc32_be` (1024-bit-style nibble table, poly `0x04C11DB7`)
- **`TdbHeader`** — magic `DB\0\x08`, endian marker, `source_size`, table count

Golden CRC vectors validated against a C# IL reimplementation (Mono.Cecil on `EA DB Editor.exe`).

## Fixed header layout (observed Legacy roster TDB)

| Offset | Size | Field |
|--------|------|-------|
| 0x00 | 4 | magic `DB\0\x08` |
| 0x04 | 4 | endian marker (LE u32 `1` on fixture) |
| 0x08 | 4 | `source_size` (BE u32; file size minus 4 on fixture) |
| 0x0C | 4 | reserved (0) |
| 0x10 | 4 | table count (BE u32; 39 on fixture) |
| 0x14 | 4 | header CRC (BE u32; reseal TBD) |
| 0x18 | 8 × count | directory entries |
| … | — | table blobs at `0x18 + count×8 + data_offset` |

### Directory entry (8 bytes)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | table id (printable ASCII) |
| 4 | 4 | data offset (BE u32, relative to table data start) |

### Table header (16 bytes at `table_data_start + offset`)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | on-disk table id (may differ from directory id) |
| 4 | 4 | field count (BE u32) |
| 8 | 4 | data allocation type (BE u32) |
| 12 | 4 | max records / size (BE u32) |

Field descriptors: 12 bytes each (`field_id[4]`, `record_bit_offset` BE, `bit_width` BE).

## Next implementation steps

1. Bit-packed field read/write (endian-aware)
2. CRC scopes reseal (file header @ 0x14, per-table, varchar pool)
3. Wire `roster-cli` to validate/reseal after container unpack

## Live game artifacts (not needed yet)

These help **M2 container checksum** and **M5 in-game verify**, not the current M3 CRC port:

| Artifact | Why |
|----------|-----|
| Fresh in-game “save roster” | Compare header fields 0x28/0x2C and checksum @ 0x10 |
| Save with checksum @ 0x10 zeroed | Confirm game rejects/accepts (validates algorithm) |
| Second roster save (vanilla vs edited) | Cross-check header/checksum patterns |

No game access required to continue M3 directory parsing.

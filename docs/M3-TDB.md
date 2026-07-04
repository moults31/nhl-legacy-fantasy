# Milestone 3: TDB parse and CRC reseal

Scope from [PLAN.md](PLAN.md): read/write EA TDB (`default.db`), reseal internal CRCs after edits.

## Status

| Item | Status |
|------|--------|
| `ea-tdb` crate | **Started** — `Crc32Be` (`DB_CRC.crc32_be`) + fixed header parse |
| Directory / table parse | **Not started** |
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
| 0x14+ | — | directory + table blobs (layout TBD) |

## Next implementation steps

1. Directory entries (16-byte records, 4-char table IDs — confirm BE u32 offsets against Modding Studio / future `tdb-core` reference)
2. Table header + field descriptor parse
3. Bit-packed field read/write (endian-aware)
4. CRC scopes reseal (file header, per-table, varchar pool — mirror EA DB Editor)
5. Wire `roster-cli` to validate/reseal after container unpack

## Live game artifacts (not needed yet)

These help **M2 container checksum** and **M5 in-game verify**, not the current M3 CRC port:

| Artifact | Why |
|----------|-----|
| Fresh in-game “save roster” | Compare header fields 0x28/0x2C and checksum @ 0x10 |
| Save with checksum @ 0x10 zeroed | Confirm game rejects/accepts (validates algorithm) |
| Second roster save (vanilla vs edited) | Cross-check header/checksum patterns |

No game access required to continue M3 directory parsing.

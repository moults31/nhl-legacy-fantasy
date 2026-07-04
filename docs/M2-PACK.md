# Milestone 2: RosterFile pack and container checksum

This document records the plan for milestone 2 from [PLAN.md](PLAN.md). It is not implemented yet.

## Goal

Round-trip an unchanged roster save byte-for-byte:

```
pack(unpack(save)) == save
```

## Prerequisites

1. **EADBEditor bundle** — available at `_local/modding-tools/EADBEditor/` (`EAChecksum.dll`, `MC02Handler.dll`, `EA DB Editor.exe`, `NHL 14 xml.xml`). See [MODDING-TOOLS.md](MODDING-TOOLS.md).
2. **Working M1 unpack** — `roster-container` extracts a bit-identical TDB payload; header fields are parsed in `RosterHeader`.
3. **Fixture** — `tests/fixtures/xbox/roster.bin` from a Proton save.

## Observed Xbox 360 header layout (48 bytes)

| Offset | Size | Field | Notes |
|--------|------|-------|-------|
| 0x00 | 16 | magic | `RosterFile\0` + padding |
| 0x10 | 4 | checksum | u32 BE; algorithm **TBD** (see below) |
| 0x14 | 4 | field_0x14 | u32 BE; observed `4` |
| 0x18 | 4 | field_0x18 | u32 BE; observed `0` |
| 0x1C | 4 | field_0x1c | u32 BE; observed `1` |
| 0x20 | 4 | field_0x20 | u32 BE; observed `2` |
| 0x24 | 4 | uncompressed_size | u32 BE; equals TDB byte length |
| 0x28 | 4 | field_0x28 | u32 BE; TBD |
| 0x2C | 4 | field_0x2c | u32 BE; TBD |
| 0x30 | rest | zlib payload | standard zlib (`0x78 0x9c`) |

## Checksum strategy

`EAChecksum.dll` is the feudalnate algorithm used by **`MC02Handler`** for Xbox MC02 save packages. EA DB Editor opens MC02-wrapped content, not raw `RosterFile` blobs.

Initial testing: invoking the real `EAChecksum` DLL (via .NET 8 reflection) over the live Proton `RosterFile` — with checksum zeroed and common slice ranges — did **not** reproduce the u32 at offset 0x10. Do not assume M2 equals a straight EAChecksum over the whole file.

Next steps:

1. **Diff-driven discovery** — mutate single header/payload bytes on a copy, reload in-game or compare against Modding Studio read path to see what invalidates the checksum field.
2. **Port EAChecksum to Rust anyway** — needed for MC02/interop and as a building block; algorithm summary in [MODDING-TOOLS.md](MODDING-TOOLS.md).
3. **Cross-check Modding Studio** — portable app read/write path for NHL 12–15 roster saves may document or mirror the Legacy container checksum.

## Implementation steps

1. Implement `ea_checksum` module in `roster-container` (pure Rust, table embedded or generated from DLL once).
2. **`pack` API**:

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

# Milestone 2: RosterFile pack and container checksum

This document records the plan for milestone 2 from [PLAN.md](PLAN.md). It is not implemented yet.

## Goal

Round-trip an unchanged roster save byte-for-byte:

```
pack(unpack(save)) == save
```

## Prerequisites

1. **EAChecksum reference** — obtain `EAChecksum.dll` and `EA DB Editor.exe` from the community EA DB Editor bundle and place them under `_local/modding-tools/EADBEditor/` (see [AGENTS.md](../AGENTS.md)). Only `NHL 14 xml.xml` is present today.
2. **Working M1 unpack** — `roster-container` extracts a bit-identical TDB payload; header fields are parsed in `RosterHeader`.

## Observed Xbox 360 header layout (48 bytes)

| Offset | Size | Field | Notes |
|--------|------|-------|-------|
| 0x00 | 16 | magic | `RosterFile\0` + padding |
| 0x10 | 4 | checksum | u32 BE; algorithm from EAChecksum |
| 0x14 | 4 | field_0x14 | u32 BE; observed `4` |
| 0x18 | 4 | field_0x18 | u32 BE; observed `0` |
| 0x1C | 4 | field_0x1c | u32 BE; observed `1` |
| 0x20 | 4 | field_0x20 | u32 BE; observed `2` |
| 0x24 | 4 | uncompressed_size | u32 BE; equals TDB byte length |
| 0x28 | 4 | field_0x28 | u32 BE; TBD |
| 0x2C | 4 | field_0x2c | u32 BE; TBD |
| 0x30 | rest | zlib payload | standard zlib (`0x78 0x9c`) |

## Implementation steps

1. **Reverse EAChecksum** — disassemble or trace `EAChecksum.dll` (feudalnate) to learn which byte ranges feed the checksum at 0x10 and whether other header fields participate. Prefer a pure-Rust port for Linux/CI; a temporary `libloading` FFI bridge is acceptable for validation only.
2. **`pack` API** — add to `roster-container`:

   ```rust
   pub fn pack(db: &[u8], template: &RosterHeader) -> Result<Vec<u8>>;
   ```

   Recompress with zlib at default compression, copy unchanged header fields from a template save, update `uncompressed_size`, recompute checksum.
3. **Round-trip test** — on `tests/fixtures/xbox/roster.bin`, assert byte identity after pack(unpack(...)).
4. **In-game verification** — milestone 5; Modding Studio beta notes that Xbox checksum write-back is not fully verified in isolation.

## Out of scope for M2

- TDB internal CRC reseal (milestone 3, `ea-tdb` crate)
- PS3 `PS3RosterFile` pack format
- Proton content-tree install (milestone 5)

## Risks

| Risk | Mitigation |
|------|------------|
| EAChecksum.dll unavailable | Block M2 until obtained; M1/M3 can work on raw `.db` |
| Checksum covers more than payload | Use original save as template; diff header after failed round-trip |
| zlib compression level differs | Match compressed size or use original compressed bytes when DB unchanged |

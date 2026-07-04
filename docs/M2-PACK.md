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
| `pack()` for edited DBs | **Blocked** — u32 @ 0x10 and 0x28 algorithms unknown |
| Discovery harness | **Done** — `crates/roster-container/tests/checksum_discover.rs` |
| Full M2 acceptance (`pack(unpack(save)) == save` for edited saves) | **Blocked** on container checksum |

## Prerequisites

1. **EADBEditor bundle** — available at `_local/modding-tools/EADBEditor/` (`EAChecksum.dll`, `MC02Handler.dll`, `EA DB Editor.exe`, `NHL 14 xml.xml`). See [MODDING-TOOLS.md](MODDING-TOOLS.md).
2. **Working M1 unpack** — `roster-container` extracts a bit-identical TDB payload; header fields are parsed in `RosterHeader`.
3. **Fixture** — `tests/fixtures/xbox/roster.bin` from a Proton save.

## Observed Xbox 360 header layout (48 bytes)

| Offset | Size | Field | Notes |
|--------|------|-------|-------|
| 0x00 | 16 | magic | `RosterFile\0` + padding |
| 0x10 | 4 | checksum_primary | u32 BE; changes on edit; algorithm **TBD** |
| 0x14 | 4 | field_0x14 | u32 BE; observed `4` (container version) |
| 0x18 | 4 | field_0x18 | u32 BE; observed `0` |
| 0x1C | 4 | field_0x1c | u32 BE; observed `1` |
| 0x20 | 4 | field_0x20 | u32 BE; observed `1` on Legacy saves (`2` on older fixture) |
| 0x24 | 4 | uncompressed_size | u32 BE; equals TDB byte length |
| 0x28 | 4 | checksum_secondary | u32 BE; also changes on edit; likely “second header checksum” per Modding Studio notes |
| 0x2C | 4 | field_0x2c | u32 BE; upper 16 bits vary; lower 16 often `0x0C00` on Legacy saves |
| 0x30 | rest | zlib payload | standard zlib (`0x78 0x9c`) |

## Checksum strategy

`EAChecksum.dll` is the feudalnate algorithm used by **`MC02Handler`** for Xbox MC02 save packages. EA DB Editor opens MC02-wrapped content, not raw `RosterFile` blobs.

### Discovery results (2026-07-04)

Brute-force over `_local/game-saves/xbox/{roster1,testroster}.bin`, `tests/fixtures/xbox/roster.bin`, and the vanilla Modding Studio save (`checksum_discover` integration test):

| Candidate | `@0x10` | `@0x28` |
|-----------|---------|---------|
| `EAChecksum` over compressed payload | No | No |
| `EAChecksum` over uncompressed TDB | No | No |
| `Crc32Be` (EA DB Editor `crc32_be`) over common slices | No | No |
| zlib `crc32` / adler32 / u32 sum/xor | No | No |

Both `@0x10` and `@0x28` change between **ROSTER1** and **TESTROSTER**; `@0x2C` low 16 bits stay `0x0C00` on Legacy saves.

**Likely implementation:** NHL Modding Studio embeds `crates/tdb-savedata/src/checksum.rs` (Rust) in `NHL Modding Studio.exe` — strings reference `nhl-savedata-xbox-` and `pack_xbox_save`. That source is not in this repo; porting the algorithm from the binary or obtaining the Modding Studio source tree is the fastest path to M2.

The Rust `EaChecksum` port in `roster-container` **does** match the reference DLL for MC02/interop; it is not the `RosterFile` container checksum.

Next steps:

1. **Port `tdb-savedata` checksum.rs** from Modding Studio source (preferred) or reverse the embedded Rust in `NHL Modding Studio.exe`.
2. **Validate** with `roster1.bin` / `testroster.bin` — recompute `@0x10` and `@0x28`, then wire into `pack()`.
3. **M5** — in-game load after first round-trip.

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

# Test fixtures

Roster save blobs are **not committed**. Copy them locally before running tests.

## Xbox 360 / Xenia (Proton)

1. Launch NHL Legacy once and create or use an existing roster save.
2. Copy the inner save file from the Proton compatdata prefix:

   ```
   ~/.steam/steam/steamapps/compatdata/3623314720/pfx/drive_c/users/steamuser/Documents/nhllegacy/
   …/454109EC/00000001/ROSTER …/ROSTER …
   ```

3. Place it at:

   ```
   tests/fixtures/xbox/roster.bin
   ```

The file must begin with the `RosterFile\0` magic (16 bytes). Tests unpack it to a `default.db` TDB payload and compare against a golden SHA-256 hash.

## Committed TDB snippet

`crates/ea-tdb/tests/fixtures/tdb_header.bin` — first 4 KiB of unpacked TDB (header + early tables).

`crates/ea-tdb/tests/fixtures/ajmx_table.bin` — isolated `ajmx` info block + descriptors (regenerate from full DB):

```bash
cargo run -p roster-cli -- unpack tests/fixtures/xbox/roster.bin -o /tmp/default.db
head -c 4096 /tmp/default.db > crates/ea-tdb/tests/fixtures/tdb_header.bin
dd if=/tmp/default.db of=crates/ea-tdb/tests/fixtures/ajmx_table.bin bs=1 skip=$((0xf1d0)) count=320
```

## Optional second fixture

A vanilla or alternate custom save helps validate header-field assumptions. Drop it alongside `roster.bin` with a distinct name and extend tests if needed.

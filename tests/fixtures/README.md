# Test fixtures

Roster save blobs are **not committed**. Copy or symlink them locally before running tests.

## Preferred layout (2026-07-04)

All reference material is consolidated under `_local/`. See **[docs/LOCAL-ARTIFACTS.md](../docs/LOCAL-ARTIFACTS.md)**.

### McTavish edit pair (integration tests)

Stable copies (no spaces in filenames):

```
_local/game-saves/xbox/roster1.bin      ← in-game ROSTER1 (before move)
_local/game-saves/xbox/testroster.bin   ← in-game TESTROSTER (McTavish → St. Louis)
```

`ea-tdb` integration test `mctavish_move.rs` reads these when present.

### Generic Xbox fixture

Optional mirror for M1 golden tests:

```
tests/fixtures/xbox/roster.bin
```

Any `RosterFile\0` blob from a Proton/Legacy save works. An older export may differ from `roster1.bin` / `testroster.bin`.

## Xbox 360 / Xenia (Proton) — manual copy

If `_local/game-saves/` is empty, copy from the live Proton prefix (also symlinked at `_local/game-saves/proton-snapshot/454109EC` when the game has been run):

```
~/.steam/steam/steamapps/compatdata/3623314720/pfx/drive_c/users/steamuser/Documents/nhllegacy/
…/454109EC/00000001/ROSTER …/ROSTER …
```

Place the inner `ROSTER …` file at `tests/fixtures/xbox/roster.bin` (or under `_local/game-saves/xbox/` with a descriptive name).

The file must begin with the `RosterFile\0` magic (16 bytes). M1 tests unpack to a `default.db` TDB payload and compare against a golden SHA-256 hash.

## Committed TDB snippet

`crates/ea-tdb/tests/fixtures/tdb_header.bin` — first 4 KiB of unpacked TDB (header + early tables).

`crates/ea-tdb/tests/fixtures/ajmx_table.bin` — isolated `ajmx` info block + descriptors (regenerate from full DB):

```bash
cargo run -p roster-cli -- unpack tests/fixtures/xbox/roster.bin -o /tmp/default.db
head -c 4096 /tmp/default.db > crates/ea-tdb/tests/fixtures/tdb_header.bin
dd if=/tmp/default.db of=crates/ea-tdb/tests/fixtures/ajmx_table.bin bs=1 skip=$((0xf1d0)) count=320
```

## Vanilla reference

Modding Studio vanilla Xbox roster (not the McTavish pair):

```
_local/modding-tools/NHL Modding Studio 0.1.0-beta.3 portable/vanilla-saves/360/ROSTER 20260531190619/ROSTER 20260531190619
```

# Local artifacts (`_local/`)

All gitignored reference material and game outputs for this repo live under **`_local/`**. Agents should **not** search outside the checkout tree for modding tools, vanilla saves, the Legacy install, or Proton roster saves — if something is missing, check here first.

Last consolidated: **2026-07-04** (operator moved resources into `_local/` and created an in-game roster edit pair).

## PR / milestone status

| Milestone | Status |
|-----------|--------|
| M1 unpack | Merged ([#1](https://github.com/nhl-legacy/nhl-legacy-fantasy/pull/1)) |
| M2 pack (unchanged round-trip) | On `main` in `roster-container` |
| M3 TDB parse | Merged ([#2](https://github.com/nhl-legacy/nhl-legacy-fantasy/pull/2)); CRC reseal in progress |

## Directory map

| Path | Contents |
|------|----------|
| `_local/modding-tools/EADBEditor/` | EA DB Editor bundle (`NHL 14 xml.xml`, `EAChecksum.dll`, `EA DB Editor.exe`) |
| `_local/modding-tools/NHL Modding Studio 0.1.0-beta.3 portable/` | `defs/`, `vanilla-saves/360/`, extractor |
| `_local/modding-tools/nhl-ratings-archive/` | Ratings/archive app source (future pipeline) |
| `_local/modding-tools/NHL DB Patcher/` | Additional modding reference |
| `_local/nhl-legacy-recomp/` | Recomp source (`tools/stick_widen` TDB experiments) |
| `_local/NHL Legacy Recomp/` | Working game install (`nhllegacy.exe`, `game/`, `launch-nhl-legacy.sh`) |
| `_local/game-saves/` | **Copied** roster save blobs for diff tests (see below) |
| `tests/fixtures/xbox/` | Optional mirror of roster blobs for `cargo test` (also gitignored) |

## In-game roster edit pair (McTavish move)

Operator session **2026-07-04** (~20:26–20:28 local):

1. In **Roster Management / Player Movement**, moved **Mason McTavish** from **Anaheim Ducks** to **St. Louis Blues**.
2. Saved via **Customize → Save → Roster** as **`TESTROSTER`** (slot 1, last modified `4/7/2026 20:28:43` in-game UI).
3. An earlier save **`ROSTER1`** (slot 2, `20:26:24`) captures roster state **before** the McTavish move (same session).

On disk (Xenia content tree under Proton), saves appear as timestamped folders:

```
…/Documents/nhllegacy/B13EBABEBABEBABE/454109EC/00000001/
  ROSTER 20260704202624/ROSTER 20260704202624   ← in-game name ROSTER1
  ROSTER 20260704202843/ROSTER 20260704202843   ← in-game name TESTROSTER
```

**Copies for agents** (stable names, no spaces):

| File | In-game name | Role |
|------|--------------|------|
| `_local/game-saves/xbox/roster1.bin` | ROSTER1 | Baseline before McTavish move |
| `_local/game-saves/xbox/testroster.bin` | TESTROSTER | After McTavish → St. Louis |
| `_local/game-saves/xbox/*.header` | (sidecar) | Xenia `.header` metadata |

Symlink to live Proton tree (updates if the game writes new saves):

`_local/game-saves/proton-snapshot/454109EC` → compatdata `…/454109EC/`

Launch script sets compatdata app id **3623314720** (`_local/NHL Legacy Recomp/launch-nhl-legacy.sh`).

### Known diff (unpacked TDB)

Both containers unpack to **2 456 076** bytes. McTavish bio text appears in both; **file offsets shift** on in-game save (DB rewrite/reorder). TDB file header CRC @ `0x14` is **unchanged** between the pair on this save — reseal rules TBD.

Container checksums at `RosterFile` offset **0x10** and **0x28** (u32 BE) **both** change between ROSTER1 and TESTROSTER. Offset **0x2C** low 16 bits are often `0x0C00` on Legacy saves. See [M2-PACK.md](M2-PACK.md) for the full 48-byte header map.

## Vanilla reference save

Modding Studio vanilla Xbox roster:

`_local/modding-tools/NHL Modding Studio 0.1.0-beta.3 portable/vanilla-saves/360/ROSTER 20260531190619/ROSTER 20260531190619`

Different content generation date from the Legacy install saves; use for schema/relationship validation, not as a byte-diff baseline for McTavish.

## Test fixture convention

`cargo test` looks for blobs under `tests/fixtures/xbox/` first (e.g. `roster.bin` from an earlier Proton export). When present, `_local/game-saves/xbox/{roster1,testroster}.bin` power the McTavish diff integration test in `ea-tdb`.

See [tests/fixtures/README.md](../tests/fixtures/README.md).

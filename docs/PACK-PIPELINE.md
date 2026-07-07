# Roster Editing Pipeline

## Summary

The confirmed path to produce working roster saves:

```
TRADEEDIT5.bin
  → unpack (decompress zlib payload after 48-byte header)
  → apply MS normalization (21 bytes from no-edit re-save)
  → apply player edits (proteam, team_alt, edit-log, CRC counter)
  → copy CRCs from a reference MS-processed save
  → pack-fdeflate (flate2 zlib + correct zero-padding)
  → install (write into 454109EC tree with .header sidecar)
```

## Why this works

Three discoveries drove this to working in-game saves:

### 1. flate2, not template deflate

The game accepts standard `flate2` zlib output (one dynamic Huffman block) as long as the compressed payload is padded to match the template's exact zlib payload size. The `deflate_template` approach was unnecessary and too fragile.

### 2. Modding Studio normalization bytes

Opening and re-saving in Modding Studio changes ~21 bytes beyond just the player fields. These include:
- **Hedman fixed to COL** (MS baseline always restores him to team 8)
- **Edit-log region** (0x1B97D1-0x1B9805): tracks the last player moved and their destination team
- **CRC counter** (0x1AB24B): increments with each edit (0x0B → 0x0C for no-edit re-save, 0x0D for one move, etc.)
- **Three unknown CRC regions** (0x1A4838, 0x1AB258, 0x1D5F2C): 4-byte values that change with every edit

S_MINIMAL (proteam+team_alt only, 2 bytes) was tested and **silently failed** in-game, confirming these extra bytes are validated by the game.

### 3. CRC regions are required but don't need to be reverse-engineered

The algorithm for the three CRC regions is unknown, but we can simply **copy them from a reference MS save** that has the same edits. The `--reference` flag does this automatically.

## Constraints

- **Input must be TRADEEDIT5 or a normalized derivative.** The byte offsets are absolute and specific to TRADEEDIT5's record layout.
- **Single-player moves only** for now (proven). Multi-move needs edit-log slot management.
- **CRC reference is required** (or use `--no-crcs` at your own risk — confirmed failure with flate2).

## CLI Usage

### move-player (the primary command)

```bash
roster-cli move-player _local/game-saves/xbox/TRADEEDIT5 \
  --player-first Sidney --player-last Crosby \
  --team COL \
  --reference "path/to/default_ms_crsb_col.db" \
  --output output/roster.bin
```

- `--player-first` / `--player-last`: name of player to move (Crosby, Ovechkin, Hedman currently supported)
- `--team`: destination team (name like `COL`, `CGY`, or numeric ID like `8`)
- `--reference`: path to a Modding Studio-processed `.db` or packed `.bin` to copy CRCs from
- `--no-crcs`: skip CRC copy (use only with deflate_template, not recommended)

### pack-fdeflate

Pack a raw `.db` into a `RosterFile` container:

```bash
roster-cli pack-fdeflate edited.db template.bin --output packed.bin
```

Pads the flate2 zlib output with zeros to match the template's payload size.

### unpack

Extract `default.db` from a packed roster save:

```bash
roster-cli unpack roster.bin --output default.db
```

### install

Use `tools/install_recomp_roster.py` to write the packed save into the game's save tree:

```bash
python tools/install_recomp_roster.py packed.bin \
  --timestamp 20260708230000 \
  --name MY_ROSTER \
  --template-header "path/to/existing.header"
```

## Verification

These Rust-built saves have been confirmed working in-game:

| Save | Player → Team | Method | Status |
|------|--------------|--------|--------|
| R_CRSB_COL | Crosby → COL | `move-player --reference` | Working |
| R_OVI_COL | Ovechkin → COL | `move-player --reference` | Working |
| T1_FROMT5 | Crosby → COL | Python byte-copy (earlier test) | Working |

## What's next

1. **Multi-move support**: edit-log slot management for moving multiple players
2. **Add more known players**: port the record lookup from `ea-tdb`/`roster-semantic` to discover players by name instead of hardcoded indices
3. **Normalization without reference**: explore whether CRCs can be omitted with different pack strategies (e.g., pack-stored) or computed from first principles

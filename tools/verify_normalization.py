#!/usr/bin/env python3
"""Extract MS normalization baseline and per-player edit templates."""
import zlib, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"

# TRADEEDIT5 raw
with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5 = zlib.decompress(f.read()[48:])

# ms_noedit (T5 opened + re-saved with NO EDITS)
with open(os.path.join(SRC, "default_ms_noedit.db"), "rb") as f:
    ms_noedit = f.read()

# ms_crsb_col (Crosby -> COL)
with open(os.path.join(SRC, "default_ms_crsb_col.db"), "rb") as f:
    ms_crsb_col = f.read()

# ms_ovi_col (Ovechkin -> COL)
with open(os.path.join(SRC, "default_ms_ovi_col.db"), "rb") as f:
    ms_ovi_col = f.read()

# ms_crsb_cgy (Crosby -> CGY)
with open(os.path.join(SRC, "default_ms_crsb_cgy.db"), "rb") as f:
    ms_crsb_cgy = f.read()

# ms_ovi_cgy (Ovechkin -> CGY)
with open(os.path.join(SRC, "default_ms_ovi_cgy.db"), "rb") as f:
    ms_ovi_cgy = f.read()

# crsb_col + ovi_cgy (two moves)
with open(os.path.join(SRC, "default_crsb_col_ovi_cgy.db"), "rb") as f:
    ms_double = f.read()

# crsb_cgy + ovi_col (two moves, opposite)
with open(os.path.join(SRC, "default_crsb_cgy_ovi_col.db"), "rb") as f:
    ms_double2 = f.read()

def normalize(db: bytearray) -> bytearray:
    """Apply MS baseline normalization to a TRADEEDIT5-based DB.
    
    This is the 21 bytes MS changes on a no-edit re-save.
    """
    result = bytearray(db)
    # Hedman: PIT(24) -> COL(8) (MS always restores him)
    base = 0x0A3168
    hed_rs = base + 1232 * 132
    result[hed_rs + 6] = 8    # team_alt
    result[hed_rs + 115] = 0x40  # proteam (team 8)
    
    # Edit-log baseline region
    result[0x1B97D1] = 0x00  # was 0x70
    result[0x1B97D2] = 0x00  # was 0x50
    result[0x1B97EC] = 0x07  # was 0x00
    result[0x1B97F1] = 0x70  # was 0x00
    result[0x1B97F2] = 0x50  # was 0x00
    result[0x1B97F4] = 0x98  # was 0x00
    
    # CRC counter
    result[0x1AB24B] = 0x0C  # was 0x0B
    
    # CRC values (from no-edit re-save)
    result[0x1A4838:0x1A483C] = ms_noedit[0x1A4838:0x1A483C]
    result[0x1AB258:0x1AB25C] = ms_noedit[0x1AB258:0x1AB25C]
    result[0x1D5F2C:0x1D5F30] = ms_noedit[0x1D5F2C:0x1D5F30]
    return result

def apply_team_move(db: bytearray, rec: int, team_id: int, marker_byte: int, ctrl_off: int, src_file=None) -> bytearray:
    """Apply a single player team move."""
    result = bytearray(db)
    base = 0x0A3168
    rs = base + rec * 132
    
    # Player data
    result[rs + 115] = (team_id & 0x1F) << 3  # proteam
    result[rs + 6] = team_id  # team_alt
    
    # Edit log: zero old entry
    result[ctrl_off] = 0x00
    result[ctrl_off + 1] = 0x00
    
    # Edit log: write new tracking
    result[0x1B97FC] = team_id - 1
    result[0x1B9801] = 0x41  # player ID prefix
    result[0x1B9802] = marker_byte
    result[0x1B9804] = team_id * 19
    result[0x1B9805] = 0x80  # constant
    
    # CRC counter
    result[0x1AB24B] += 1  # 0x0C -> 0x0D for 1 edit
    
    # CRCs from working MS file
    if src_file is not None:
        result[0x1A4838:0x1A483C] = src_file[0x1A4838:0x1A483C]
        result[0x1AB258:0x1AB25C] = src_file[0x1AB258:0x1AB25C]
        result[0x1D5F2C:0x1D5F30] = src_file[0x1D5F2C:0x1D5F30]
    return result

# ---- VERIFY: can we reproduce each MS file? ----
print("Verification against MS outputs...")

tests = [
    ("Crosby->COL", ms_crsb_col, lambda n: apply_team_move(n, 688, 8, 0x10, 0x1B97E1, ms_crsb_col)),
    ("Crosby->CGY", ms_crsb_cgy, lambda n: apply_team_move(n, 688, 5, 0x10, 0x1B97E1, ms_crsb_cgy)),
    ("Ovechkin->COL", ms_ovi_col, lambda n: apply_team_move(n, 695, 8, 0xD0, 0x1ACE71, ms_ovi_col)),
    ("Ovechkin->CGY", ms_ovi_cgy, lambda n: apply_team_move(n, 695, 5, 0xD0, 0x1ACE71, ms_ovi_cgy)),
]

for name, ms_target, builder in tests:
    norm = normalize(t5)
    our = builder(norm)
    diffs = [i for i in range(len(our)) if our[i] != ms_target[i]]
    status = "PERFECT" if len(diffs) == 0 else f"{len(diffs)} diffs"
    print(f"  {name}: {status}")
    if diffs:
        for off in diffs[:5]:
            print(f"    0x{off:06X}: ours=0x{our[off]:02X} ms=0x{ms_target[off]:02X}")

# Two-move tests
for name, ms_target, edits in [
    ("C->COL O->CGY", ms_double, [(688,8,0x10,0x1B97E1),(695,5,0xD0,0x1ACE71)]),
    ("C->CGY O->COL", ms_double2, [(688,5,0x10,0x1B97E1),(695,8,0xD0,0x1ACE71)]),
]:
    norm = normalize(t5)
    our = bytearray(norm)
    for rec, tid, marker, ctrl in edits:
        our = apply_team_move(our, rec, tid, marker, ctrl, ms_target)
        our[0x1AB24B] += 1  # increment for second edit
    our[0x1A4838:0x1A483C] = ms_target[0x1A4838:0x1A483C]
    our[0x1AB258:0x1AB25C] = ms_target[0x1AB258:0x1AB25C]
    our[0x1D5F2C:0x1D5F30] = ms_target[0x1D5F2C:0x1D5F30]
    
    diffs = [i for i in range(len(our)) if our[i] != ms_target[i]]
    status = "PERFECT" if len(diffs) == 0 else f"{len(diffs)} diffs"
    print(f"  {name}: {status}")
    if diffs:
        for off in diffs[:5]:
            print(f"    0x{off:06X}: ours=0x{our[off]:02X} ms=0x{ms_target[off]:02X}")

print("\nSaving normalized TRADEEDIT5 as baseline...")
norm = normalize(t5)
with open("tools/tmp/t5_normalized.db", "wb") as f:
    f.write(bytes(norm))
print("  -> tools/tmp/t5_normalized.db")

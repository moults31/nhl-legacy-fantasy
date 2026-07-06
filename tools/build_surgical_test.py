#!/usr/bin/env python3
"""Build a surgical test using deflate_template path (pack-fdeflate)."""
import struct, zlib as zl, os, subprocess, shutil

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"

# Step 1: Take default_ms_crsb_col.db (Crosby on COL, confirmed working)
with open(os.path.join(SRC, "default_ms_crsb_col.db"), "rb") as f:
    ms_crsb_col = bytearray(f.read())

RLB = 132
PROTEAM_OFF = 115
TEAM_ALT_OFF = 6
base = 0x0A3168
crosby_rec = 688

def set_player_team(db, rec, team_id):
    """Set proteam and team_alt for a player."""
    rs = base + rec * RLB
    pbyte = (team_id & 0x1F) << 3  # proteam in upper 5 bits
    db[rs + PROTEAM_OFF] = pbyte
    db[rs + TEAM_ALT_OFF] = team_id

# Build test files
TMP = "tools/tmp"
os.makedirs(TMP, exist_ok=True)

# S2: Crosby -> CGY (team 5) from COL template
s2 = bytearray(ms_crsb_col)
set_player_team(s2, crosby_rec, 5)
# CGY normalization: 0x1B97FC = 4, 0x1B9804 = 0x5D
s2[0x1B97FC] = 0x04
s2[0x1B9804] = 0x5D
with open(f"{TMP}/s2_crsb_cgy.db", "wb") as f:
    f.write(s2)

# S3: Crosby -> team 10 (VAN maybe? or DET? whatever, a different team) from COL template
s3 = bytearray(ms_crsb_col)
set_player_team(s3, crosby_rec, 10)
# Unknown normalization for team 10. Leave as-is (team 8 COL values)
# Team 8 -> 0x98 at 0x1B9804. 0x98 = 152. 152/8 = 19.
# 10 * 19 = 190 = 0xBE
# 0x1B97FC: team 8->7=0x07, team 5->4=0x04. So team_id-1.
s3[0x1B97FC] = 9  # team 10 - 1 = 9
s3[0x1B9804] = 0xBE  # 10 * 19
with open(f"{TMP}/s3_crsb_t10.db", "wb") as f:
    f.write(s3)

# S4: Ovechkin -> COL from ms_crsb_col template (Crosby stays on COL)
s4 = bytearray(ms_crsb_col)
set_player_team(s4, 695, 8)  # Ovechkin to COL
# For Ovi moves: 0x1ACE71/0x1ACE72 get zeroed
s4[0x1ACE71] = 0x00
s4[0x1ACE72] = 0x00
# Ovi marker: 0x1B9802 = 0xD0 (Ovechkin identifier)
s4[0x1B97FC] = 0x07  # COL
s4[0x1B9802] = 0xD0  # Ovechkin marker (not Crosby's 0x10)
s4[0x1B9804] = 0x98  # COL
s4[0x1B9805] = 0x80  # always set
with open(f"{TMP}/s4_ovi_col.db", "wb") as f:
    f.write(s4)

# Use the MS-edited COL DB as the TRADEEDIT5 template
# Actually, we need a .bin template. Let me use the packed ms_noedit 
# as the template since TRADEEDIT5 has different player assignments.
# Actually, TRADEEDIT5 IS the right template since its zlib structure
# is what the game accepts. Let me check if there's a packed version.

# First, let me pack ms_noedit as TMPL_MSNO (a working MS file to use as template)
with open(os.path.join(SRC, "default_ms_noedit.db"), "rb") as f:
    db = f.read()
tmp_db = os.path.abspath(f"{TMP}/tmpl_noedit.db")
with open(tmp_db, "wb") as f:
    f.write(db)

# Use TRADEEDIT5 as template
tmpl_out = os.path.abspath(f"{TMP}/TMPL_MSNO")
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-fdeflate", 
    tmp_db,
    os.path.abspath(f"{BIN}/TRADEEDIT5"),
    "--output", tmpl_out,
], capture_output=True, text=True, cwd=os.getcwd())
print("Packing TMPL_MSNO:")
print(f"  stdout: {result.stdout.strip()}")
if result.stderr.strip():
    stderr = result.stderr.strip()
    for line in stderr.split("\n"):
        if "error" in line.lower() or "wrote" in line.lower():
            print(f"  stderr: {line}")

# Now pack the surgical edits, using TMPL_MSNO as the template
for name in ["s2_crsb_cgy", "s3_crsb_t10", "s4_ovi_col"]:
    db_path = os.path.abspath(f"{TMP}/{name}.db")
    out_path = os.path.abspath(f"{BIN}/{name.upper()}")
    
    result = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "pack-fdeflate", 
        db_path,
        tmpl_out,
        "--output", out_path,
    ], capture_output=True, text=True, cwd=os.getcwd())
    print(f"\nPacking {name}:")
    print(f"  stdout: {result.stdout.strip()}")
    if result.stderr.strip():
        err = result.stderr.strip()
        if len(err) > 500:
            err = err[:500] + "..."
        print(f"  stderr: {err}")

print("\nDone.")

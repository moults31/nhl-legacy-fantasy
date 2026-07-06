#!/usr/bin/env python3
"""Clean up old saves and rebuild a clean test set."""
import os, shutil, subprocess

BASE = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC"
BIN = "_local/game-saves/xbox"
SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
TMP = "tools/tmp"
os.makedirs(TMP, exist_ok=True)

# --- 1. Clean up old saves ---
save_dir = os.path.join(BASE, "00000001")
headers_dir = os.path.join(BASE, "Headers", "00000001")

# Keep only the latest 5 (MS1/MS2/T0/T5 + our new ones), nuke everything else
KEEP_DISPLAY = {"MS1", "MS2", "T0BASELINE", "T5BASELINE", "M5_CRSB_CGY", "CSB_COL", "F2_NOEDIT"}

for dirpath in [save_dir, headers_dir]:
    for name in os.listdir(dirpath):
        if name == "PROFILE 20260702052022":
            continue
        path = os.path.join(dirpath, name)
        if os.path.isdir(path):
            # Check the header display name
            ts = name.split(" ", 1)[1] if " " in name else name
            header_path = os.path.join(headers_dir, f"{name}.header")
            keep = False
            if os.path.isfile(header_path):
                with open(header_path, "rb") as f:
                    data = f.read()
                # UTF-16 at 0x09
                display = data[0x09:0x1F].decode('utf-16-le').rstrip('\x00')
                if display in KEEP_DISPLAY:
                    keep = True
            
            if not keep:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
        
        # Clean matching header files
        elif path.endswith(".header"):
            with open(path, "rb") as f:
                data = f.read()
            display = data[0x09:0x1F].decode('utf-16-le').rstrip('\x00')
            if display not in KEEP_DISPLAY:
                os.remove(path)

print("Cleaned up old saves. Remaining:")
for name in sorted(os.listdir(save_dir)):
    path = os.path.join(save_dir, name)
    if os.path.isdir(path):
        header_path = os.path.join(headers_dir, f"{name}.header")
        if os.path.isfile(header_path):
            with open(header_path, "rb") as f:
                data = f.read()
            display = data[0x09:0x1F].decode('utf-16-le').rstrip('\x00')
            print(f"  {display:15} ({name})")
        else:
            print(f"  [no header]     ({name})")

# --- 2. Build clean test saves ---
RLB = 132
PROTEAM_OFF = 115
TEAM_ALT_OFF = 6
base = 0x0A3168

# Load baselines
with open(os.path.join(SRC, "default_ms_noedit.db"), "rb") as f:
    ms_noedit = bytearray(f.read())
with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    import zlib
    t5_db = bytearray(zlib.decompress(f.read()[48:]))

def set_player_team(db, rec, team_id):
    rs = base + rec * RLB
    db[rs + PROTEAM_OFF] = (team_id & 0x1F) << 3
    db[rs + TEAM_ALT_OFF] = team_id

def apply_edit_log(db, is_crosby, is_ovechkin, new_team):
    """Apply the edit-log bytes for a move."""
    tid = new_team
    if is_crosby: marker_byte = 0x10; ctrl_off = 0x1B97E1
    elif is_ovechkin: marker_byte = 0xD0; ctrl_off = 0x1ACE71
    else: return
    
    # Zero old entry
    db[ctrl_off] = 0x00
    db[ctrl_off + 1] = 0x00
    
    # Write new tracking
    db[0x1B97FC] = tid - 1  # team_id - 1
    db[0x1B9801] = 0x41  # player identifier bytes
    db[0x1B9802] = marker_byte
    db[0x1B9804] = tid * 19  # team * 19
    db[0x1B9805] = 0x80  # constant

# Build all tests
tests = {}

# T1: TRADEEDIT5 -> Crosby COL (FROM SCRATCH, no MS lineage!)
t1 = bytearray(t5_db)
set_player_team(t1, 688, 8)  # Crosby -> COL
# Hedman: on TRADEEDIT5 he's team 24 (PIT). MS saves have him on COL (8).
# Leave him unchanged for now - this is a single Crosby move
apply_edit_log(t1, True, False, 8)
# Increment CRC counter
t1[0x1AB24B] = 0x0D  # one edit
# Copy CRCs from a working MS save  
with open(os.path.join(SRC, "default_ms_crsb_col.db"), "rb") as f:
    ms_col = f.read()
t1[0x1A4838:0x1A483C] = ms_col[0x1A4838:0x1A483C]
t1[0x1AB258:0x1AB25C] = ms_col[0x1AB258:0x1AB25C]
t1[0x1D5F2C:0x1D5F30] = ms_col[0x1D5F2C:0x1D5F30]
tests["T1_CROSBY_COL"] = bytes(t1)

# Vary CRC counter to 0x0E for two-move case
with open(os.path.join(SRC, "default_crsb_col_ovi_cgy.db"), "rb") as f:
    ms_double = f.read()

# S2: from ms_noedit, Crosby -> CGY (like ms_crsb_cgy but our version)
s2 = bytearray(ms_noedit)
set_player_team(s2, 688, 5)
apply_edit_log(s2, True, False, 5)
s2[0x1AB24B] = 0x0D
with open(os.path.join(SRC, "default_ms_crsb_cgy.db"), "rb") as f:
    s2[0x1A4838:0x1A483C] = f.read()[0x1A4838:0x1A483C]
    f.seek(0)
    s2[0x1AB258:0x1AB25C] = f.read()[0x1AB258:0x1AB25C]
    f.seek(0)
    s2[0x1D5F2C:0x1D5F30] = f.read()[0x1D5F2C:0x1D5F30]
tests["S2_CRSB_CGY"] = bytes(s2)

# S4: from ms_noedit, Ovechkin -> COL
s4 = bytearray(ms_noedit)
set_player_team(s4, 695, 8)
apply_edit_log(s4, False, True, 8)
s4[0x1AB24B] = 0x0D
with open(os.path.join(SRC, "default_ms_ovi_col.db"), "rb") as f:
    s4[0x1A4838:0x1A483C] = f.read()[0x1A4838:0x1A483C]
    f.seek(0)
    s4[0x1AB258:0x1AB25C] = f.read()[0x1AB258:0x1AB25C]
    f.seek(0)
    s4[0x1D5F2C:0x1D5F30] = f.read()[0x1D5F2C:0x1D5F30]
tests["S4_OVI_COL"] = bytes(s4)

# Write DBs and pack
for name, db in tests.items():
    db_path = os.path.abspath(f"{TMP}/{name.lower()}.db")
    out_path = os.path.abspath(f"{BIN}/{name}")
    with open(db_path, "wb") as f:
        f.write(db)
    
    result = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "pack-fdeflate", db_path,
        os.path.abspath(f"{BIN}/TRADEEDIT5"),
        "--output", out_path,
    ], capture_output=True, text=True, cwd=os.getcwd())
    if "wrote" in result.stderr:
        size = result.stderr.split("(")[-1].split(" ")[0] if "(" in result.stderr else "?"
        print(f"  {name}: packed ({size} bytes)")
        
        # Install
        ts = f"2026070701{hash(name) % 100:02d}{hash(name) % 100:02d}"
        disp = name[:12]  # max ~12 chars UTF-16
        result2 = subprocess.run([
            "python", "tools/install_recomp_roster.py", out_path,
            "--timestamp", ts,
            "--name", disp,
            "--template-header", 
            r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
        ], capture_output=True, text=True, cwd=os.getcwd())
        print(f"    installed as {disp}")
    else:
        print(f"  {name}: ERROR - {result.stderr[:200]}")

print("\nDone. Verify (RB Refresh):")
for name in tests:
    print(f"  {name[:12]:15}")

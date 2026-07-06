#!/usr/bin/env python3
"""Build test saves with edits in different deflate blocks."""
import subprocess, sys

BIN_DIR = "_local/game-saves/xbox"
T5 = f"{BIN_DIR}/TRADEEDIT5"

def pack_and_install(db_path, out_name, ts, label):
    """Pack a DB and install it."""
    out_bin = f"{BIN_DIR}/{out_name}.bin"
    cmd = f"cargo run -p roster-cli --release -- pack --output {out_bin} {db_path} {T5}"
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if "wrote" not in r.stdout and "wrote" not in r.stderr:
        print(f"  PACK FAILED: {r.stderr}")
        return False
    
    cmd2 = f"python tools/install_recomp_roster.py {out_bin} --timestamp {ts} --name {label} --template-header {T5}"
    r2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
    if "installed" in r2.stdout:
        print(f"  Installed as {label} ({ts})")
        return True
    else:
        print(f"  INSTALL FAILED: {r2.stderr}")
        return False

# Read hedman_col.db
import zlib as zl
with open(f"{BIN_DIR}/hedman_col.db", "rb") as f:
    ms_db = bytearray(f.read())

# 1. Edit in block 12 (not block 6): find a byte to change
# Block 12 covers [0x16CBAA..0x1AFB45)
# Let me change a random byte that's not a known structure byte
ms_db[0x16EDB5] = 0x40  # random edit in block 12
with open(f"{BIN_DIR}/triage_b12.db", "wb") as f:
    f.write(ms_db)
pack_and_install(f"{BIN_DIR}/triage_b12.db", "TRG_B12", "20260308000202", "TRGB12")

# 2. Ovechkin edit (also in block 6)
ms_db = bytearray(open(f"{BIN_DIR}/hedman_col.db", "rb").read())
ms_db[0x0B9837] = 0x40  # Ovechkin
with open(f"{BIN_DIR}/triage_ov.db", "wb") as f:
    f.write(ms_db)
pack_and_install(f"{BIN_DIR}/triage_ov.db", "TRG_OV", "20260308000203", "TRGOV")

# 3. Install HYB_A and HYB_B
for fname, label, ts in [
    ("HYB_A.bin", "HYBA", "20260308000204"),
    ("HYB_B.bin", "HYBB", "20260308000205"),
]:
    cmd = f"python tools/install_recomp_roster.py {BIN_DIR}/{fname} --timestamp {ts} --name {label} --template-header {T5}"
    subprocess.run(cmd, shell=True)

print("\nDone. Test in-game:")
print("  TRGORIG: original DB base + Crosby -> COL")
print("  TRGB12:  MS DB base + edit in block 12")
print("  TRGOV:   MS DB base + Ovechkin -> COL") 
print("  HYBA:    T0 header + T1 zlib")
print("  HYBB:    T1 header + T0 zlib")

#!/usr/bin/env python3
"""Build save from the ORIGINAL backup, using itself as template."""
import subprocess, zlib as zl

BIN = "_local/game-saves/xbox"
BACKUP = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511\ROSTER 20260307213511"

with open(BACKUP, "rb") as f:
    orig = f.read()

# Save backup as a .bin in our working dir
with open(f"{BIN}/ORIG_BACKUP.bin", "wb") as f:
    f.write(orig)

# Decompress, edit Crosby, save
db = bytearray(zl.decompress(orig[48:]))
db[0x0B949B] = 0x40  # Crosby -> COL
with open(f"{BIN}/orig_crsb.db", "wb") as f:
    f.write(db)

# Pack using ORIG_BACKUP.bin as template
subprocess.run([
    "cargo", "run", "-p", "roster-cli", "--release", "--",
    "pack",
    "--output", f"{BIN}/ORIG_CRSB.bin",
    f"{BIN}/orig_crsb.db", f"{BIN}/ORIG_BACKUP.bin",
], check=False)

# Also: repack the ORIGINAL unchanged as a control
orig_db = zl.decompress(orig[48:])
with open(f"{BIN}/orig_unch.db", "wb") as f:
    f.write(orig_db)
subprocess.run([
    "cargo", "run", "-p", "roster-cli", "--release", "--",
    "pack",
    "--output", f"{BIN}/ORIG_UNCH.bin",
    f"{BIN}/orig_unch.db", f"{BIN}/ORIG_BACKUP.bin",
], check=False)

# Install
for label, ts in [
    ("ORIG_CRSB", "20260308000401"),
    ("ORIG_UNCH", "20260308000402"),
]:
    subprocess.run([
        "python", "tools/install_recomp_roster.py",
        f"{BIN}/{label}.bin",
        "--timestamp", ts,
        "--name", label,
        "--template-header", f"{BIN}/ORIG_BACKUP.bin",
    ], check=False)

print("""
  ORIG_CRSB (20260308000401): Original backup DB + Crosby -> COL
  ORIG_UNCH (20260308000402): Original backup DB, unchanged repack
""")

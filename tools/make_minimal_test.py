#!/usr/bin/env python3
"""Minimal edit test: only proteam + team_alt, no CRCs, flate2 pack."""
import zlib, subprocess, os, sys, struct, datetime

BIN = "_local/game-saves/xbox"
TOOLS = "tools/tmp"
os.makedirs(TOOLS, exist_ok=True)

# 1. Decompress TRADEEDIT5
with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    container = f.read()
    t5_raw = zlib.decompress(container[48:])

# 2. Minimal edit: Crosby proteam + team_alt -> COL(8)
#    Record 688 (0-indexed from ea-tdb), @0x0B942E(team_alt) 0x0B949B(proteam)
crosby_rs = 0x0A3168 + 688 * 132
data = bytearray(t5_raw)
data[crosby_rs + 6] = 8          # team_alt
data[crosby_rs + 115] = 0x40     # proteam (team 8 << 3)
num_changes = 2
print(f"Made {num_changes} bytes of changes (proteam + team_alt only)")

# 3. Save the DB
minimal_db = os.path.join(TOOLS, "minimal_crsb_col.db")
with open(minimal_db, "wb") as f:
    f.write(bytes(data))

# 4. Pack with flate2
out_bin = os.path.join(TOOLS, "S_MINIMAL")
os.makedirs(out_bin, exist_ok=True)
cmd = [
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-fdeflate", minimal_db, f"{BIN}/TRADEEDIT5",
    "--output", os.path.join(out_bin, "roster.bin"),
]
print(f"Running: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
print(result.stdout)
if result.returncode != 0:
    print(f"PACK FAILED: {result.stderr}")
    sys.exit(1)

# 5. Copy to _local/nhl-legacy-recomp/tools/tmp/
import shutil
dest = os.path.join(out_bin, "roster.bin")
print(f"Packed to {dest} ({os.path.getsize(dest)} bytes)")

# 6. Install for in-game test
ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
install_cmd = [
    "python", "tools/install_recomp_roster.py",
    dest,
    "--timestamp", ts,
    "--name", "S_MINIMAL",
]
print(f"Installing: {' '.join(install_cmd)}")
result2 = subprocess.run(install_cmd, capture_output=True, text=True, cwd=".")
print(result2.stdout)
if result2.returncode != 0:
    print(f"INSTALL FAILED: {result2.stderr}")

print(f"\nDone. Test in-game: look for S_MINIMAL in load menu, check Crosby's team.")

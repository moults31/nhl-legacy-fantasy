#!/usr/bin/env python3
"""Pack and install the resealed DB for in-game testing."""
import subprocess, os, datetime, shutil

TMP = "tools/tmp"
BIN = "_local/game-saves/xbox"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

# Pack resealed DB
out_bin = os.path.join(TMP, "R_RESEAL.bin")
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-fdeflate", f"{TMP}/resealed.db", f"{BIN}/TRADEEDIT5",
    "--output", out_bin
], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode != 0:
    print(f"PACK FAILED: {result.stderr}")
    exit(1)

# Install
ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
result = subprocess.run([
    "python", "tools/install_recomp_roster.py", out_bin,
    "--timestamp", ts,
    "--name", "R_RESEAL",
    "--template-header", HEADER
], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode != 0:
    print(f"INSTALL FAILED: {result.stderr}")
else:
    print(f"\nInstalled as R_RESEAL — load in-game and check Crosby's team!")

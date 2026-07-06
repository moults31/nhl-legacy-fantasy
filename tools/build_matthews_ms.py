#!/usr/bin/env python3
"""Build Matthews->ANA with MS-only CRC reseal."""
import zlib, subprocess, os, datetime

BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    packed = f.read()
    t5 = bytearray(zlib.decompress(packed[48:]))

# Normalization
t5[0x0CACAE] = 0x08; t5[0x0CAD1B] = 0x40
t5[0x1B97D1] = 0x00; t5[0x1B97D2] = 0x00
t5[0x1B97EC] = 0x07; t5[0x1B97F1] = 0x70
t5[0x1B97F2] = 0x50; t5[0x1B97F4] = 0x98
t5[0x1AB24B] = 0x0C

# Matthews->ANA (team 1)
mr = 0x0A3168 + 5593 * 132
t5[mr + 115] = (1 & 0x1F) << 3
t5[mr + 6] = 1

pre_db = os.path.join(TMP, "matthews_ms_pre.db")
with open(pre_db, "wb") as f:
    f.write(bytes(t5))

result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "reseal", pre_db, "--output", f"{TMP}/matthews_ms.db",
    "--ms-only"
], capture_output=True, text=True)
print(result.stdout.strip())

result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-fdeflate", f"{TMP}/matthews_ms.db", f"{BIN}/TRADEEDIT5",
    "--output", f"{TMP}/M_MATT_MS.bin"
], capture_output=True, text=True)
print(result.stdout.strip())

ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
result = subprocess.run([
    "python", "tools/install_recomp_roster.py", f"{TMP}/M_MATT_MS.bin",
    "--timestamp", ts, "--name", "M_MATT_MS",
    "--template-header", HEADER
], capture_output=True, text=True)
print(result.stdout.strip())
print("\nM_MATT_MS: Matthews->ANA with MS-only reseal. No edit-log changes.")

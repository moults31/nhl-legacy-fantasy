#!/usr/bin/env python3
"""Build Crosby->CGY + Ovechkin->CGY multi-move save."""
import zlib, subprocess, os, datetime

BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    packed = f.read()
    t5 = bytearray(zlib.decompress(packed[48:]))

# Normalization (baseline MS re-save)
t5[0x0CACAE] = 0x08; t5[0x0CAD1B] = 0x40  # Hedman
t5[0x1B97D1] = 0x00; t5[0x1B97D2] = 0x00
t5[0x1B97EC] = 0x07; t5[0x1B97F1] = 0x70
t5[0x1B97F2] = 0x50; t5[0x1B97F4] = 0x98
t5[0x1AB24B] = 0x0C

# Move 1: Crosby->CGY (team 5)
cr = 0x0A3168 + 688 * 132
t5[cr + 115] = (5 & 0x1F) << 3   # proteam
t5[cr + 6] = 5                     # team_alt
t5[0x1B97E1] = 0x00                # zero old tracking
t5[0x1B97E2] = 0x00
t5[0x1B97FC] = 4                   # team-1 (CGY=5)
t5[0x1B9801] = 0x41               # prefix
t5[0x1B9802] = 0x10               # Crosby marker
t5[0x1B9804] = 0x5D               # CGY team*19 (off-by-2)
t5[0x1B9805] = 0x80               # constant

# Move 2: Ovechkin->CGY (team 5)
or_ = 0x0A3168 + 695 * 132
t5[or_ + 115] = (5 & 0x1F) << 3   # proteam
t5[or_ + 6] = 5                     # team_alt
t5[0x1ACE71] = 0x00                # zero old tracking
t5[0x1ACE72] = 0x00
t5[0x1B980C] = 4                   # team-1 (CGY=5) in slot 2
t5[0x1B9811] = 0x41               # prefix in slot 2
t5[0x1B9812] = 0xD0               # Ovechkin marker in slot 2
t5[0x1B9814] = 0x5D               # CGY team*19 in slot 2
t5[0x1B9815] = 0x80               # constant in slot 2

t5[0x1AB24B] = 0x0E                # CRC counter: 0x0C + 2

# Save and reseal (MS-only)
pre_db = os.path.join(TMP, "multi_crsb_ovi_cgy_pre.db")
with open(pre_db, "wb") as f:
    f.write(bytes(t5))

result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "reseal", pre_db, "--output", f"{TMP}/multi_crsb_ovi_cgy.db",
    "--ms-only"
], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode != 0:
    print(f"RESEAL FAILED: {result.stderr}")
    exit(1)

# Pack
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-fdeflate", f"{TMP}/multi_crsb_ovi_cgy.db", f"{BIN}/TRADEEDIT5",
    "--output", f"{TMP}/M_CG_CG.bin"
], capture_output=True, text=True)
print(result.stdout.strip())

# Install
ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
result = subprocess.run([
    "python", "tools/install_recomp_roster.py", f"{TMP}/M_CG_CG.bin",
    "--timestamp", ts, "--name", "M_CG_CG",
    "--template-header", HEADER
], capture_output=True, text=True)
print(result.stdout.strip())

if result.returncode == 0:
    print("\nInstalled as M_CG_CG — test in-game! Crosby and Ovechkin should both be on CGY.")

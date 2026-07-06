#!/usr/bin/env python3
"""Test: proteam+team_alt only for Matthews->ANA, with correct CRCs. No edit-log."""
import zlib, subprocess, os, datetime

BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    container = f.read()
    t5 = bytearray(zlib.decompress(container[48:]))

# Matthews: record 5593, current team 28 (TB), target team 1 (ANA)
# proteam at record + 115, team_alt at record + 6
matthews_rs = 0x0A3168 + 5593 * 132
print(f"Matthews record offset: 0x{matthews_rs:X}")
print(f"Current proteam: 0x{t5[matthews_rs+115]:02X} (team {t5[matthews_rs+115]>>3})")
print(f"Current team_alt: {t5[matthews_rs+6]}")

# Apply Norm + Matthews edit
# Normalization first
t5[0x0CACAE] = 0x08; t5[0x0CAD1B] = 0x40
t5[0x1B97D1] = 0x00; t5[0x1B97D2] = 0x00
t5[0x1B97EC] = 0x07; t5[0x1B97F1] = 0x70
t5[0x1B97F2] = 0x50; t5[0x1B97F4] = 0x98
t5[0x1AB24B] = 0x0C

# Matthews->ANA (team 1)
t5[matthews_rs + 115] = (1 & 0x1F) << 3  # = 0x08
t5[matthews_rs + 6] = 1

# Write raw DB for reseal
pre_db = os.path.join(TMP, "matthews_pre.db")
with open(pre_db, "wb") as f:
    f.write(bytes(t5))

# reseal
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "reseal", pre_db, "--output", f"{TMP}/matthews_resealed.db"
], capture_output=True, text=True)
print(result.stdout.strip())

# pack
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-fdeflate", f"{TMP}/matthews_resealed.db", f"{BIN}/TRADEEDIT5",
    "--output", f"{TMP}/M_MATTHEWS.bin"
], capture_output=True, text=True)
print(result.stdout.strip())

# install
ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
result = subprocess.run([
    "python", "tools/install_recomp_roster.py", f"{TMP}/M_MATTHEWS.bin",
    "--timestamp", ts, "--name", "M_MATTHEWS",
    "--template-header", HEADER
], capture_output=True, text=True)
print(result.stdout.strip())

if result.returncode == 0:
    print("\nInstalled as M_MATTHEWS — test in-game! Matthews should be on ANA.")

# Also try a full reseal of just the MS CRCs (not all CRCs)
# The full reseal will change ALL table CRCs, which may or may not cause issues.
# Let's also make a version with only reseal_ms_crcs
print("\n\nAlso building MS-only reseal version...")
import struct
def read_u32_be(d, o): return struct.unpack(">I", d[o:o+4])[0]

# reseal_ms_crcs is available in the CLI too - actually we exposed it as 
# reseal_ms_crcs, not a CLI command. Let me use Python for this.
# But first, test full reseal version.

# Actually the full reseal changes all CRCs — let me also use reseal_ms_crcs from Rust.
# I'll call the Rust function via a small test binary. Or better, let me just use
# the reseal command but then check if it works.

# Actually, the full reseal rewrites ALL CRCs, not just the 3 MS ones. This changes
# the file in ways MS doesn't. Let me make one with reseal_ms_crcs too.

# For reseal_ms_crcs, I need to call it from Rust. Let me write a quick inline test.
# Actually, let me just add a --ms-only flag to the reseal command. But that's a 
# Rust change. For now, let's test the full reseal first and see if it works.
print("Full reseal version ready as M_MATTHEWS.")

#!/usr/bin/env python3
"""Build Matthews->ANA EXACTLY as MS does it (including zeroing 0x1AE750)."""
import zlib, subprocess, os, datetime

BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    packed = f.read()
    t5 = bytearray(zlib.decompress(packed[48:]))

# First: normalize (MS no-edit baseline)
t5[0x0CACAE] = 0x08; t5[0x0CAD1B] = 0x40  # Hedman
t5[0x1B97D1] = 0x00; t5[0x1B97D2] = 0x00
t5[0x1B97EC] = 0x07; t5[0x1B97F1] = 0x70
t5[0x1B97F2] = 0x50; t5[0x1B97F4] = 0x98
t5[0x1AB24B] = 0x0C

# Matthews->ANA (team 1). MS sets team_alt=0 and proteam=0x00...
# Wait, that seems wrong for team 1. Let me double check.
# Actually, let me just copy exactly what MS does: 
# team_alt: 0x1C -> 0x00
# proteam: 0xE0 -> 0x00
# And zero the 3 bytes at 0x1AE750

mr = 0x0A3168 + 5593 * 132
t5[mr + 6] = 0      # team_alt = 0 (MS value)
t5[mr + 115] = 0x00  # proteam = 0x00 (MS value)

# Zero 0x1AE750-0x1AE752
t5[0x1AE750] = 0x00
t5[0x1AE751] = 0x00
t5[0x1AE752] = 0x00

# Save and build
pre_db = os.path.join(TMP, "matt_exact_pre.db")
with open(pre_db, "wb") as f:
    f.write(bytes(t5))

# Use reseal (full) since we changed gap bytes too
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "reseal", pre_db, "--output", f"{TMP}/matt_exact.db",
    "--ms-only"
], capture_output=True, text=True)
print(result.stdout.strip())

result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-fdeflate", f"{TMP}/matt_exact.db", f"{BIN}/TRADEEDIT5",
    "--output", f"{TMP}/M_EXACT.bin"
], capture_output=True, text=True)
print(result.stdout.strip())

# Verify CRC values match MS
import struct
def u32(d, o): return struct.unpack(">I", d[o:o+4])[0]
SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
with open(os.path.join(SRC, "default_ms_matt_ana.db"), "rb") as f:
    ms = f.read()
with open(f"{TMP}/matt_exact.db", "rb") as f:
    ours = f.read()

diffs = [(i, ours[i], ms[i]) for i in range(len(ours)) if ours[i] != ms[i]]
if len(diffs) == 0:
    print("PERFECT: byte-identical to MS output!")
else:
    print(f"{len(diffs)} diffs vs MS:")
    for off, o, m in diffs[:10]:
        print(f"  0x{off:06X}: ours=0x{o:02X} ms=0x{m:02X}")

ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
result = subprocess.run([
    "python", "tools/install_recomp_roster.py", f"{TMP}/M_EXACT.bin",
    "--timestamp", ts, "--name", "M_EXACT",
    "--template-header", HEADER
], capture_output=True, text=True)
print(result.stdout.strip())
print("\nInstalled as M_EXACT — exact MS replica of Matthews->ANA.")

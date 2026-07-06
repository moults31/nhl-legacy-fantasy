#!/usr/bin/env python3
"""Test whether ea-tdb reseal_checksums produces the same CRC values as MS.

Pipeline: TRADEEDIT5 -> normalize -> edit -> reseal -> compare with MS.
Also test: does the game accept a resealed (no reference) save?
"""
import zlib, subprocess, os, shutil, datetime, struct

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
os.makedirs(TMP, exist_ok=True)

def read_u32_be(data, off):
    return struct.unpack(">I", data[off:off+4])[0]

# 1. Load the already-normalized+edited DB from our Rust tool (no-CRC version)
# First build it if needed
norm_db = os.path.join(TMP, "for_reseal_test.db")
subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "unpack", f"{BIN}/TRADEEDIT5", "--output", norm_db
], check=True, capture_output=True)

# Apply normalization + edit in Python (same as move_player.rs)
with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    packed = f.read()
    t5 = bytearray(zlib.decompress(packed[48:]))

# Crosby record: base + 688 * 132
crosby_rs = 0x0A3168 + 688 * 132

# Normalization (21 bytes - same as move_player.rs)
t5[0x0CACAE] = 0x08  # Hedman team_alt
t5[0x0CAD1B] = 0x40  # Hedman proteam
t5[0x1B97D1] = 0x00
t5[0x1B97D2] = 0x00
t5[0x1B97EC] = 0x07
t5[0x1B97F1] = 0x70
t5[0x1B97F2] = 0x50
t5[0x1B97F4] = 0x98
t5[0x1AB24B] = 0x0C  # CRC counter

# Crosby edit
t5[crosby_rs + 115] = 0x40  # proteam COL
t5[crosby_rs + 6] = 8       # team_alt COL
t5[0x1B97E1] = 0x00         # zero old tracking
t5[0x1B97E2] = 0x00
t5[0x1B97FC] = 7            # team - 1 (COL = 8)
t5[0x1B9801] = 0x41         # player ID prefix
t5[0x1B9802] = 0x10         # Crosby marker
t5[0x1B9804] = 0x98         # 8 * 19 (but wait, CGY was off... for COL 8, it's 0x98)
t5[0x1B9805] = 0x80         # constant
t5[0x1AB24B] = 0x0D         # CRC counter: 0x0C + 1

# Write the pre-reseal DB
pre_db = os.path.join(TMP, "pre_reseal.db")
with open(pre_db, "wb") as f:
    f.write(bytes(t5))

print(f"Pre-reseal DB: {len(t5)} bytes, CRC_A=0x{read_u32_be(t5, 0x1A4838):08X}, CRC_B=0x{read_u32_be(t5, 0x1AB258):08X}, CRC_C=0x{read_u32_be(t5, 0x1D5F2C):08X}")

# 2. Run reseal
resealed_db = os.path.join(TMP, "resealed.db")
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "reseal", pre_db, "--output", resealed_db
], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode != 0:
    print(f"RESEAL FAILED: {result.stderr}")
    exit(1)

# 3. Compare with MS reference
with open(resealed_db, "rb") as f:
    resealed = f.read()

with open(os.path.join(SRC, "default_ms_crsb_col.db"), "rb") as f:
    ms = f.read()

print(f"\nResealed CRCs:")
print(f"  CRC_A (0x1A4838) = 0x{read_u32_be(resealed, 0x1A4838):08X}  MS = 0x{read_u32_be(ms, 0x1A4838):08X}  {'MATCH' if resealed[0x1A4838:0x1A483C] == ms[0x1A4838:0x1A483C] else 'MISMATCH'}")
print(f"  CRC_B (0x1AB258) = 0x{read_u32_be(resealed, 0x1AB258):08X}  MS = 0x{read_u32_be(ms, 0x1AB258):08X}  {'MATCH' if resealed[0x1AB258:0x1AB25C] == ms[0x1AB258:0x1AB25C] else 'MISMATCH'}")
print(f"  CRC_C (0x1D5F2C) = 0x{read_u32_be(resealed, 0x1D5F2C):08X}  MS = 0x{read_u32_be(ms, 0x1D5F2C):08X}  {'MATCH' if resealed[0x1D5F2C:0x1D5F30] == ms[0x1D5F2C:0x1D5F30] else 'MISMATCH'}")

# 4. Check overall diff
diffs = [(i, resealed[i], ms[i]) for i in range(len(resealed)) if resealed[i] != ms[i]]
print(f"\nTotal diffs vs MS: {len(diffs)}")
if diffs:
    for off, r, m in diffs[:10]:
        print(f"  0x{off:06X}: resealed=0x{r:02X} ms=0x{m:02X}")

# 5. Pack and install for in-game test
if len(diffs) == 0 or all(any(s <= i < e for s, e in [(0x1A4838, 0x1A483C), (0x1AB258, 0x1AB25C), (0x1D5F2C, 0x1D5F30)]) for i, _, _ in diffs):
    out_bin = os.path.join(TMP, "R_RESEAL.bin")
    result = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "pack-fdeflate", resealed_db, f"{BIN}/TRADEEDIT5",
        "--output", out_bin
    ], capture_output=True, text=True)
    print(f"\nPacked: {result.stdout.strip()}")
    if result.returncode != 0:
        print(f"PACK FAILED: {result.stderr}")
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        subprocess.run([
            "python", "tools/install_recomp_roster.py", out_bin,
            "--timestamp", ts,
            "--name", "R_RESEAL",
            "--template-header",
            os.path.expandvars(r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header")
        ], check=True)
        print("Installed as R_RESEAL — test in-game!")
else:
    print("\nNon-CRC diffs exist — not installing for test yet")

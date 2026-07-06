#!/usr/bin/env python3
"""Full pipeline test: normalize -> edit -> reseal (Rust) -> pack -> verify vs MS."""
import zlib, subprocess, os, datetime, struct

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"

def read_u32_be(data, off):
    return struct.unpack(">I", data[off:off+4])[0]

# 1. Build normalized + edited DB (use Rust move-player --no-crcs)
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "move-player", f"{BIN}/TRADEEDIT5",
    "--player-first", "Sidney", "--player-last", "Crosby",
    "--team", "COL", "--no-crcs",
    "--output", f"{TMP}/pre_reseal2.bin"
], capture_output=True, text=True)
print(result.stdout.strip())

# 2. Unpack to get the DB
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "unpack", f"{TMP}/pre_reseal2.bin", "--output", f"{TMP}/pre_reseal2.db"
], capture_output=True, text=True)
print(result.stdout.strip())

# 3. Reseal
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "reseal", f"{TMP}/pre_reseal2.db", "--output", f"{TMP}/resealed2.db"
], capture_output=True, text=True)
print(result.stdout.strip())

# 4. Compare CRCs with MS
with open(f"{TMP}/resealed2.db", "rb") as f:
    resealed = f.read()
with open(os.path.join(SRC, "default_ms_crsb_col.db"), "rb") as f:
    ms = f.read()

print("\n=== CRC COMPARISON ===")
for name, off in [("CRC_A (RBQQ prior)", 0x1A4838), ("CRC_B (ulGe hdr)", 0x1AB258), ("CRC_C (caBZ prior)", 0x1D5F2C)]:
    r = read_u32_be(resealed, off)
    m = read_u32_be(ms, off)
    print(f"  {name}: ours=0x{r:08X} ms=0x{m:08X} {'MATCH!' if r == m else 'MISMATCH'}")

# 5. Count total diffs
diffs = [i for i in range(len(resealed)) if resealed[i] != ms[i]]
crc_regions = [(0x1A4838, 0x1A483C), (0x1AB258, 0x1AB25C), (0x1D5F2C, 0x1D5F30)]
non_crc = [i for i in diffs if not any(s <= i < e for s, e in crc_regions)]
print(f"\nTotal diffs: {len(diffs)} ({len(diffs)-len(non_crc)} CRC, {len(non_crc)} other)")
if non_crc:
    print("Non-CRC diffs:")
    for off in non_crc[:10]:
        print(f"  0x{off:06X}: ours=0x{resealed[off]:02X} ms=0x{ms[off]:02X}")

# 6. Pack and install for in-game test
out_bin = os.path.join(TMP, "R_RESEAL2.bin")
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-fdeflate", f"{TMP}/resealed2.db", f"{BIN}/TRADEEDIT5",
    "--output", out_bin
], capture_output=True, text=True)
print(f"\nPack: {result.stdout.strip()}")

ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)
result = subprocess.run([
    "python", "tools/install_recomp_roster.py", out_bin,
    "--timestamp", ts,
    "--name", "R_RESEAL2",
    "--template-header", HEADER
], capture_output=True, text=True)
print(result.stdout.strip())
print("\nInstalled as R_RESEAL2 — test in-game!")

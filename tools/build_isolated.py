#!/usr/bin/env python3
"""Build test saves isolating the zlib re-encoder vs byte edit question."""
import struct, subprocess, zlib as zl

BIN = "_local/game-saves/xbox"

# Read hedman_col.db and TRADEEDIT5
with open(f"{BIN}/hedman_col.db", "rb") as f:
    ms_db = bytearray(f.read())
with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5 = f.read()

# Test 1: Flate2-compressed, no template re-encoder
# Edit Crosby proteam: 0xF0 -> 0x40 (bits 3-7: 01000=8=COL, bits 0-2: 000 unchanged)
db1 = bytearray(ms_db)
db1[0x0B949B] = 0x40
with open(f"{BIN}/try_flate2.db", "wb") as f:
    f.write(db1)

# Use pack-fdeflate (standard flate2) instead of template-guided
subprocess.run([
    "cargo", "run", "-p", "roster-cli", "--release", "--",
    "pack-fdeflate",
    "--output", f"{BIN}/TRY_FL2.bin",
    f"{BIN}/try_flate2.db", f"{BIN}/TRADEEDIT5",
], check=False)

# Test 2: Edit ONLY proteam bits (preserve WfTt explicitly)
# 0xF0 = 11110000. Upper 5 = proteam=11110=30. Lower 3 = WfTt=000.
# Want proteam=8=01000. New byte = 01000000 = 0x40. WfTt stays 000. ✓ same.
# Let me try another approach: edit in a player where WfTt is NOT zero.
# Find a player whose original byte has non-zero WfTt and is in block 6.
# Actually, let me try a DIFFERENT byte offset entirely.

# Test 3: Edit a byte that is NOT in a structurally critical position
# Pick a byte far from known field starts (mid-table data)
# Use a byte in block 12, region [0x16CBAA..0x1AFB45)
db3 = bytearray(ms_db)
db3[0x170000] ^= 0x01  # flip one bit in the middle of a table
with open(f"{BIN}/try_bitflip.db", "wb") as f:
    f.write(db3)

# Use template-guided pack
subprocess.run([
    "cargo", "run", "-p", "roster-cli", "--release", "--",
    "pack",
    "--output", f"{BIN}/TRY_FLIP.bin",
    f"{BIN}/try_bitflip.db", f"{BIN}/TRADEEDIT5",
], check=False)

# Test 4: Direct byte-patch of T0_CLEAN.bin's zlib
# Actually, let's try something simpler: hex-edit T0_CLEAN.db (the decompressed DB)
# to change Crosby's proteam, then pack with TRADEEDIT5 template.
# This is exactly what we've been doing, but let's verify.
db4 = bytearray(ms_db)
db4[0x0B949B] = 0x40  # standard Crosby edit
with open(f"{BIN}/try_std.db", "wb") as f:
    f.write(db4)
subprocess.run([
    "cargo", "run", "-p", "roster-cli", "--release", "--",
    "pack",
    "--output", f"{BIN}/TRY_STD.bin",
    f"{BIN}/try_std.db", f"{BIN}/TRADEEDIT5",
], check=False)

# Install all
for label, ts in [
    ("TRY_FL2", "20260308000301"),
    ("TRY_FLIP", "20260308000302"), 
    ("TRY_STD", "20260308000303"),
]:
    subprocess.run([
        "python", "tools/install_recomp_roster.py",
        f"{BIN}/{label}.bin",
        "--timestamp", ts,
        "--name", label,
        "--template-header", f"{BIN}/TRADEEDIT5",
    ], check=False)

print("""
Test saves:
  TRY_FL2 (20260308000301): Flate2 compression, no template re-encoder
  TRY_FLIP (20260308000302): Random bit flip in block 12 (not a player edit)
  TRY_STD (20260308000303): Standard Crosby edit, template re-encoder
""")

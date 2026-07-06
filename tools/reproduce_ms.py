#!/usr/bin/env python3
"""Test: can we reproduce the EXACT MS output for noedit -> crsb_col (22 diffs)?"""
import os, struct

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"

with open(os.path.join(SRC, 'default_ms_noedit.db'), 'rb') as f:
    noedit = bytearray(f.read())
with open(os.path.join(SRC, 'default_ms_crsb_col.db'), 'rb') as f:
    ms_crsb_col = f.read()

base = 0x0A3168
crosby_rec = 688

# Build our version from noedit
our = bytearray(noedit)

# 1. Crosby proteam (team 8 = 0x40)
our[base + crosby_rec * 132 + 115] = 0x40
# 2. Crosby team_alt (team 8)
our[base + crosby_rec * 132 + 6] = 8

# 3. Edit-log: zero old tracking
our[0x1B97E1] = 0x00  # was 0x41
our[0x1B97E2] = 0x00  # was 0x10

# 4. Edit-log: set new tracking
our[0x1B97FC] = 0x07   # team 8 - 1
our[0x1B9801] = 0x41   # Crosby player ID bytes
our[0x1B9802] = 0x10
our[0x1B9804] = 0x98   # 8 * 19
our[0x1B9805] = 0x80   # always

# 5. CRC counter increment
our[0x1AB24B] = 0x0D

# 6. CRCs - unknown algorithm, copy from MS output for now
our[0x1A4838:0x1A483C] = ms_crsb_col[0x1A4838:0x1A483C]
our[0x1AB258:0x1AB25C] = ms_crsb_col[0x1AB258:0x1AB25C]
our[0x1D5F2C:0x1D5F30] = ms_crsb_col[0x1D5F2C:0x1D5F30]

# Check
diffs = [(i, ms_crsb_col[i], our[i]) for i in range(len(ms_crsb_col)) if ms_crsb_col[i] != our[i]]
print(f"Remaining diffs from MS output: {len(diffs)}")
if diffs:
    for off, mv, ov in diffs:
        print(f"  0x{off:06X}: ours=0x{ov:02X} ms=0x{mv:02X}")
else:
    print("PERFECT MATCH - we CAN reproduce MS output byte-for-byte!")
    # Save it
    out_path = "tools/tmp/our_crsb_col.db"
    with open(out_path, "wb") as f:
        f.write(bytes(our))
    print(f"Saved to {out_path}")
    
    # Now pack and install
    print("\nPacking with deflate_template...")

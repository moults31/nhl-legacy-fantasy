#!/usr/bin/env python3
"""Compare header bytes across saves."""
import struct

backup = r'C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511\ROSTER 20260307213511'
with open(backup, 'rb') as f:
    orig = f.read()[:48]
with open('_local/game-saves/xbox/TRADEEDIT5', 'rb') as f:
    t5 = f.read()[:48]
with open('_local/game-saves/xbox/T0_CLEAN.bin', 'rb') as f:
    t0 = f.read()[:48]
with open('_local/game-saves/xbox/T1_CRSB.bin', 'rb') as f:
    t1 = f.read()[:48]

print("Byte-by-byte header comparison (0x00-0x2F):")
print(f"{'Offset':>6}  {'ORIG':>8}  {'T5':>8}  {'T0':>8}  {'T1':>8}")
for i in range(0x30):
    o = orig[i]
    a = t5[i]
    b = t0[i]
    c = t1[i]
    marker = ""
    if not (o == a == b == c):
        marker = " ***"
    print(f"0x{i:04X}   0x{o:02X}     0x{a:02X}     0x{b:02X}     0x{c:02X}{marker}")

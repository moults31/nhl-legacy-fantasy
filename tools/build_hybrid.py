#!/usr/bin/env python3
"""Build hybrid containers: T0 header + T1 zlib, and vice versa."""
import struct
import shutil

# Read both
with open("_local/game-saves/xbox/T0_CLEAN.bin", "rb") as f:
    t0 = bytearray(f.read())
with open("_local/game-saves/xbox/T1_CRSB.bin", "rb") as f:
    t1 = bytearray(f.read())

# HYB_A: T0 header + T1 zlib
hyb_a = bytearray(t0)
hyb_a[48:] = t1[48:]
with open("_local/game-saves/xbox/HYB_A.bin", "wb") as f:
    f.write(hyb_a)
print(f"HYB_A: T0 header + T1 zlib -> {len(hyb_a)} bytes")

# HYB_B: T1 header + T0 zlib
hyb_b = bytearray(t1)
hyb_b[48:] = t0[48:]
with open("_local/game-saves/xbox/HYB_B.bin", "wb") as f:
    f.write(hyb_b)
print(f"HYB_B: T1 header + T0 zlib -> {len(hyb_b)} bytes")

# Verify zlib decompresses correctly
import zlib as zl
for name, data in [("HYB_A", hyb_a), ("HYB_B", hyb_b)]:
    header = data[:48]
    z = data[48:]
    try:
        db = zl.decompress(z)
        print(f"{name}: zlib OK, DB size={len(db)}, Crosby=0x{db[0x0B949B]:02X}")
    except Exception as e:
        print(f"{name}: zlib FAILED: {e}")

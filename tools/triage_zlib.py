#!/usr/bin/env python3
"""Deep comparison of T0 (works) vs T1 (fails) zlib to find any structural differences."""
import zlib as zl
import struct

with open("_local/game-saves/xbox/T0_CLEAN.bin", "rb") as f:
    t0_z = f.read()[48:]
with open("_local/game-saves/xbox/T1_CRSB.bin", "rb") as f:
    t1_z = f.read()[48:]

# 1. Adler-32 comparison
t0_adler = struct.unpack(">I", t0_z[-4:])[0]
t1_adler = struct.unpack(">I", t1_z[-4:])[0]
t0_db = zl.decompress(t0_z)
t1_db = zl.decompress(t1_z)
t0_adler_correct = zl.adler32(t0_db)
t1_adler_correct = zl.adler32(t1_db)
print(f"T0 Adler: in-stream=0x{t0_adler:08X} computed=0x{t0_adler_correct:08X} match={t0_adler == t0_adler_correct}")
print(f"T1 Adler: in-stream=0x{t1_adler:08X} computed=0x{t1_adler_correct:08X} match={t1_adler == t1_adler_correct}")

# 2. Zlib header bytes
print(f"\nT0 zlib[0:6]: {t0_z[:6].hex()} (expect 78 9c ...)")
print(f"T1 zlib[0:6]: {t1_z[:6].hex()} (expect 78 9c ...)")

# 3. Compare deflate stream structure: block boundaries
# Use inspect_deflate_blocks to compare block positions
# (We'll do this in Rust, but let's check block 6 range first)
# Block 6 starts at bit 2,312,817 and is 349,142/349,141 bits
# That's bytes 289,102 to roughly 332,745

# 4. Check if byte-level compare shows patterns
m = min(len(t0_z), len(t1_z))
diff_ranges = []
in_diff = False
diff_start = 0
for i in range(m):
    if t0_z[i] != t1_z[i]:
        if not in_diff:
            diff_start = i
            in_diff = True
    elif in_diff:
        diff_ranges.append((diff_start, i))
        in_diff = False
if in_diff:
    diff_ranges.append((diff_start, m))

print(f"\nDiff ranges in zlib ({len(diff_ranges)} contiguous ranges):")
for s, e in diff_ranges[:10]:
    print(f"  bytes [{s}..{e}) len={e-s}")

# 5. Check if the ENTIRE deflate stream after block 6 differs
# Deep compare: find where the FIRST divergent byte appears
for i in range(m):
    if t0_z[i] != t1_z[i]:
        print(f"\n  First diff at zlib byte {i}: T0=0x{t0_z[i]:02X} T1=0x{t1_z[i]:02X}")
        # Show 32 bytes of context
        ctx = max(0, i-8)
        print(f"  T0[{ctx}..{i+24}]: {t0_z[ctx:i+24].hex()}")
        print(f"  T1[{ctx}..{i+24}]: {t1_z[ctx:i+24].hex()}")
        break

# 6. Count total unique bytes in diff
total = sum(1 for i in range(m) if t0_z[i] != t1_z[i])
print(f"\nTotal differing zlib bytes: {total} / {m} ({total*100/m:.1f}%)")

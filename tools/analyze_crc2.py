#!/usr/bin/env python3
"""Brute-force CRC algorithm discovery and MS edit-log analysis."""
import struct, zlib, os, re

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"

with open(os.path.join(SRC, "default.db"), "rb") as f:
    baseline = f.read()

# Load all files
edits = {}
for fn in os.listdir(SRC):
    if not fn.endswith(".db") or ".bak" in fn:
        continue
    n = fn.replace("default_", "").replace(".db", "")
    for key, pat in [
        ("ms_noedit", r"ms_noedit"),
        ("crsb_col", r"ms_crsb_col"),
        ("crsb_cgy", r"ms_crsb_cgy"),
        ("ovi_col", r"ms_ovi_col"),
        ("ovi_cgy", r"ms_ovi_cgy"),
        ("crsbcol_ovicgy", r"crsb_col_ovi_cgy"),
        ("crsbcgy_ovicol", r"crsb_cgy_ovi_col"),
    ]:
        if re.search(pat, n):
            with open(os.path.join(SRC, fn), "rb") as f:
                edits[key] = f.read()
            break

# ============================================================
# APPROACH: Try EA-specific CRC = CRC32 of table data segments
# ============================================================

# The TDB format has tables. Let me find table boundaries.
# The file starts with TDB header then tables.
# Let me parse the TDB file header to find table offsets and sizes.

# TDB file header at offset 0: 
# magic = "DB\x00\x08" (4 bytes) - actually let me check
print("TDB header analysis:")
print(f"  Magic: {baseline[:8].hex()} = {baseline[:8]!r}")

# Let's look at the beginning of the file for table descriptors
# TDB format: header with table count, then table descriptors
# Each table descriptor has: name, offset, size, record count, etc.

# Read the header
# The DB magic is usually followed by version, then table count
# Let me try to parse it
# Actually looking at ea-tdb crate code would be better, but let me try

# The TDB format uses a 32-bit table count at some offset
# Let me look at offsets 8-16 for things that look like counts
for off in range(8, 32, 4):
    val = struct.unpack("<I", baseline[off:off+4])[0]
    print(f"  u32 @ 0x{off:02X} = {val} (0x{val:08X})")

# Table descriptors: after header, there should be N table entries
# Each entry: name (4 bytes), plus metadata
# Let me find table names in the beginning of the file
print("\n  Looking for table name strings in first 16KB...")
for off in range(0, 0x4000, 4):
    b = baseline[off:off+4]
    if all(0x20 <= c < 0x7f for c in b):
        print(f"    0x{off:06X}: {b!r}")

# Actually, let me look at what ea-tdb crate knows
print("\n--- Looking at crucial regions to identify tables ---")
print("\nRegion around 0x1A4838 (CRC_A):")
# Print surrounding bytes to see what table this is in
for off in range(0x1A4800, 0x1A4880, 16):
    hexstr = " ".join(f"{baseline[off+i]:02X}" for i in range(16))
    asciistr = "".join(chr(b) if 32 <= b < 127 else "." for b in baseline[off:off+16])
    marker = " <-- CRC_A" if off <= 0x1A4838 < off+16 else ""
    print(f"  0x{off:06X}: {hexstr}  {asciistr}{marker}")

print("\nRegion around 0x1AB258 (CRC_C):")
for off in range(0x1AB240, 0x1AB2A0, 16):
    hexstr = " ".join(f"{baseline[off+i]:02X}" for i in range(16))
    asciistr = "".join(chr(b) if 32 <= b < 127 else "." for b in baseline[off:off+16])
    marker = " <-- CRC_C" if off <= 0x1AB258 < off+16 else ""
    print(f"  0x{off:06X}: {hexstr}  {asciistr}{marker}")

# ============================================================
# APPROACH: differential CRC analysis
# ============================================================
print("\n--- DIFFERENTIAL CRC: crsb_col vs ms_noedit ---")
db0 = edits['ms_noedit']
db1 = edits['crsb_col']

for name, addr in [("CRC_A", 0x1A4838), ("CRC_C", 0x1AB258), ("CRC_D", 0x1D5F2C)]:
    v0 = struct.unpack("<I", db0[addr:addr+4])[0]
    v1 = struct.unpack("<I", db1[addr:addr+4])[0]
    delta = v1 ^ v0
    delta_s = v1 - v0
    if delta_s < 0:
        delta_s += 0x100000000
    print(f"  {name}: 0x{v0:08X} -> 0x{v1:08X}  xor=0x{delta:08X}  diff={delta_s}")

# Show all changed bytes
diffs = [(i, db0[i], db1[i]) for i in range(len(db0)) if db0[i] != db1[i]]
print(f"\n  All {len(diffs)} bytes changed (noedit -> crsb_col):")
for off, v0, v1 in diffs:
    print(f"    0x{off:06X}: 0x{v0:02X} -> 0x{v1:02X}")

# CRC_D: try crc32 and other hash of SPECIFIC regions
print("\n--- CRC_D: region analysis ---")
for key in ['ms_noedit', 'crsb_col', 'ovi_col', 'crsbcol_ovicgy']:
    db = edits[key]
    stored = struct.unpack("<I", db[0x1D5F2C:0x1D5F30])[0]
    # Try: crc32 of everything from TDB start to CRC_D (excluding the CRC itself)
    prefix = db[:0x1D5F2C]
    c32 = zlib.crc32(prefix) & 0xFFFFFFFF
    a32 = zlib.adler32(prefix) & 0xFFFFFFFF
    # Try: crc32 of everything from 0x1AB25C to CRC_D
    mid = db[0x1AB25C:0x1D5F2C]
    c32_mid = zlib.crc32(mid) & 0xFFFFFFFF
    print(f"  {key:20}: stored={stored:08X} crc32(pref)={c32:08X} adler32(pref)={a32:08X} crc32(mid)={c32_mid:08X}")

# ============================================================
# APPROACH: checksum might be CRC32 of TDB records or table sections
# ============================================================
# Let me check: is CRC_D a crc32 of everything that's NOT the CRC_D?
print("\n--- CRC_D: crc32 of full file minus CRC region ---")
for key in ['ms_noedit', 'crsb_col', 'crsbcol_ovicgy']:
    db = edits[key]
    stored = struct.unpack("<I", db[0x1D5F2C:0x1D5F30])[0]
    # whole file minus the 4 CRC bytes
    data = db[:0x1D5F2C] + db[0x1D5F30:]
    c32 = zlib.crc32(data) & 0xFFFFFFFF
    print(f"  {key:20}: stored={stored:08X} crc32(file-except-CRC)={c32:08X}")

# ============================================================
# APPROACH: check if CRC values are simply taken from a base and XOR'd 
# with the changed data's CRC
# ============================================================
print("\n--- CRC_A as masked/accumulated CRC ---")
# CRC_A changes between noedit and crsb_col
# The only changes to the file are player data and some normalization bytes
# Let me compute crc32 of just the changed bytes and see if it relates to the CRC delta
changed = bytes(db1[i] for i, _, _ in sorted(diffs, key=lambda x: x[0]))
changed_crc = zlib.crc32(changed) & 0xFFFFFFFF
print(f"  crc32(changed bytes in crsb_col) = 0x{changed_crc:08X}")
print(f"  CRC_A delta = 0x{struct.unpack('<I',db0[0x1A4838:0x1A483C])[0] ^ struct.unpack('<I',db1[0x1A4838:0x1A483C])[0]:08X}")

# Try if CRC = ~crc32(something)
for key in ['ms_noedit', 'crsb_col']:
    db = edits[key]
    stored = struct.unpack("<I", db[0x1A4838:0x1A483C])[0]
    c32_neg = ~(zlib.crc32(db[:0x1A4838])) & 0xFFFFFFFF
    print(f"  {key}: CRC_A=0x{stored:08X}  ~crc32(prefix)=0x{c32_neg:08X}")

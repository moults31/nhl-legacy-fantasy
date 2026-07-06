#!/usr/bin/env python3
"""CRC Algorithm reverse-engineering for MS-edited TDB files."""
import struct, zlib, os, re, hashlib

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

# CRC regions (confirmed from analysis)
CRC_REGIONS = {
    "CRC_A": 0x1A4838,  # 4 bytes, varies per save
    "CRC_B": 0x1AB24B,  # 1 byte (was 0x0C -> 0x0D/0x0E/0x0F), group included 1AB258-1AB25B (4 bytes)
    "CRC_C": 0x1AB258,  # 4 bytes, varies: ms_noedit=baseline, ovi=crsb variants, double unique
    "CRC_D": 0x1D5F2C,  # 4 bytes, unique per save
}

# Actually CRC_B at 0x1AB24B is just 1 byte, but let me separate
# 0x1AB24B: single byte, ranges 0x0C-0x0F (seems like a counter: 0C=noedit, 0D=single, 0E/0F=double)
# 0x1AB258: 4 bytes

print("=" * 80)
print("CRC ANALYSIS: Reverse-engineering checksum algorithm")
print("=" * 80)

# CRC_A at 0x1A4838 - try CRC32 over various ranges
print("\n--- CRC_A at 0x1A4838 ---")

for key in sorted(edits):
    db = edits[key]
    crc_val = struct.unpack("<I", db[0x1A4838:0x1A483C])[0]
    
    # Try CRC32 of region before CRC_A
    crc_before = zlib.crc32(db[:0x1A4838]) & 0xFFFFFFFF
    # Try CRC32 of region between A and end (removing the CRC bytes)
    crc_rest = zlib.crc32(db[0x1A483C:]) & 0xFFFFFFFF
    # Try CRC32 of everything except the CRC
    data_no_crc = db[:0x1A4838] + db[0x1A483C:]
    crc_all = zlib.crc32(data_no_crc) & 0xFFFFFFFF
    
    match_before = "✓" if crc_before == crc_val else ""
    match_rest = "✓" if crc_rest == crc_val else ""
    match_all = "✓" if crc_all == crc_val else ""
    
    bs = db[:0x1A4838]
    print(f"  {key:20}: stored=0x{crc_val:08X} crc(prefix {len(bs)}B)=0x{crc_before:08X}{match_before} crc(suffix)=0x{crc_rest:08X}{match_rest} crc(all)=0x{crc_all:08X}{match_all}")

# Try Adler-32
print("\n--- CRC_A: Adler-32 variants ---")
for key in ['ms_noedit', 'crsb_col', 'crsbcol_ovicgy']:
    db = edits[key]
    stored = struct.unpack("<I", db[0x1A4838:0x1A483C])[0]
    prefix = db[:0x1A4838]
    a32 = zlib.adler32(prefix) & 0xFFFFFFFF
    a32_bytes = ((zlib.adler32(prefix) >> 16) << 16) | (zlib.adler32(prefix) & 0xFFFF)
    # Try custom: sum of all bytes mod 2^32
    custom = sum(prefix) & 0xFFFFFFFF
    print(f"  {key}: stored=0x{stored:08X} adler32=0x{a32:08X} byte_sum=0x{custom:08X}")

# CRC_C at 0x1AB258
# Interesting: ALL single-player edits share the SAME value (0x88FB0E87)
# Two-player edits have different values
# ms_noedit = baseline
print("\n--- CRC_C at 0x1AB258 ---")
for key in sorted(edits):
    db = edits[key]
    stored = struct.unpack("<I", db[0x1AB258:0x1AB25C])[0]
    # Define region cover
    region_start = 0x1A483C  # after CRC_A
    region_end = 0x1AB258    # before CRC_C
    region_data = db[region_start:region_end]
    crc_region = zlib.crc32(region_data) & 0xFFFFFFFF
    print(f"  {key:20}: stored=0x{stored:08X} crc(region [{region_start:06X}-{region_end:06X}])={(('0x%08X'%crc_region)+' ✓' if crc_region==stored else ('0x%08X'%crc_region))}")

# CRC_D at 0x1D5F2C
print("\n--- CRC_D at 0x1D5F2C ---")
for key in ['ms_noedit', 'crsb_col', 'crsbcol_ovicgy']:
    db = edits[key]
    stored = struct.unpack("<I", db[0x1D5F2C:0x1D5F30])[0]
    # Region between CRC_C and CRC_D
    region = db[0x1AB25C:0x1D5F2C]
    crc_region = zlib.crc32(region) & 0xFFFFFFFF
    region2 = db[:0x1D5F2C]
    crc_region2 = zlib.crc32(region2) & 0xFFFFFFFF
    print(f"  {key:20}: stored=0x{stored:08X} crc([AB258+4-D5F2C])=0x{crc_region:08X} crc(prefix)=0x{crc_region2:08X}")

# NEW: Try finding if CRCs are TDB-internal checksums (not CRC32, maybe custom EA)
# Look for patterns in how CRC values change relative to data changes
print("\n--- CRC DIFFERENTIAL ANALYSIS ---")
print("Comparing crsb_col (1 move) vs ms_noedit (0 moves):")
db0 = edits['ms_noedit']
db1 = edits['crsb_col']

for name, addr in [("CRC_A", 0x1A4838), ("CRC_C", 0x1AB258), ("CRC_D", 0x1D5F2C)]:
    v0 = struct.unpack("<I", db0[addr:addr+4])[0]
    v1 = struct.unpack("<I", db1[addr:addr+4])[0]
    delta = v1 ^ v0
    print(f"  {name}: 0x{v0:08X} → 0x{v1:08X}  (xor=0x{delta:08X})")

# Find all data bytes that changed between ms_noedit and crsb_col
diffs = [(i, db0[i], db1[i]) for i in range(len(db0)) if db0[i] != db1[i]]
print(f"\n  Bytes changed (noedit→crsb_col): {len(diffs)}")
for off, v0, v1 in diffs:
    print(f"    0x{off:06X}: 0x{v0:02X} → 0x{v1:02X}")

# Now try to see if CRC_A change corresponds to something specific
# The only PLAYER data change is Crosby proteam 0xF0→0x40 and team_alt 0x1E→0x08
# The normalization bytes also change
print("\n--- CRC_A: attempt bit-diff analysis ---")
# XOR the CRC with the changed bytes
crc_v0 = struct.unpack("<I", db0[0x1A4838:0x1A483C])[0]
crc_v1 = struct.unpack("<I", db1[0x1A4838:0x1A483C])[0]
print(f"  crc_a(noedit) = 0x{crc_v0:08X}  crc_a(crsb_col) = 0x{crc_v1:08X}")
print(f"  crc_a XOR = 0x{crc_v0 ^ crc_v1:08X}")
# Also check if it's crc32 of JUST the changed bytes
changed_bytes = bytes(db1[i] for i, _, _ in diffs)
print(f"  crc32(changed_bytes) = 0x{zlib.crc32(changed_bytes):08X}")

# Check if CRC is a running XOR checksum starting from file beginning
print("\n--- RUNNING XOR CHECKSUM ---")
for key in ['ms_noedit', 'crsb_col', 'crsbcol_ovicgy']:
    db = edits[key]
    xorsum = 0
    for i in range(0, 0x1A4838 + 4, 4):
        xorsum ^= struct.unpack("<I", db[i:i+4])[0]
    xorsum &= 0xFFFFFFFF
    stored = struct.unpack("<I", db[0x1A4838:0x1A483C])[0]
    print(f"  {key:20}: stored=0x{stored:08X} xor_all_u32=0x{xorsum:08X}")

# Check if it's a simple 32-bit add-checksum
print("\n--- ADDITIVE CHECKSUM ---")
for key in ['ms_noedit', 'crsb_col', 'crsbcol_ovicgy']:
    db = edits[key]
    checksum = 0
    for i in range(0, 0x1A4838 + 4):
        checksum += db[i]
    checksum &= 0xFFFFFFFF
    stored = struct.unpack("<I", db[0x1A4838:0x1A483C])[0]
    print(f"  {key:20}: stored=0x{stored:08X} byte_sum=0x{checksum:08X}")

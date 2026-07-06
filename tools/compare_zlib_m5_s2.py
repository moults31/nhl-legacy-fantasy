#!/usr/bin/env python3
"""Compare M5_CRSB_CGY (works) vs S2_CRSB_CGY (fails) zlib structure."""
import zlib, struct

BIN = "_local/game-saves/xbox"

for name in ["M5_CRSB_CGY", "S2_CRSB_CGY"]:
    with open(f"{BIN}/{name}", "rb") as f:
        data = f.read()
    
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")
    
    # Unpack and decompress
    db = zlib.decompress(data[48:])
    print(f"  decompressed: {len(db)} bytes")
    
    # Check players
    base = 0x0A3168
    for rec, pname in [(688,'Crosby'),(695,'Ovechkin'),(1232,'Hedman')]:
        rs = base + rec*132
        pt = (db[rs+115]>>3)&0x1F
        ta = db[rs+6]
        print(f"  {pname}: proteam={pt} team_alt={ta}")
    
    # Zlib analysis
    z = data[48:]
    print(f"  zlib header: {z[:2].hex()}")
    
    # Check zlib compressed size
    compressed = z[2:-4]  # strip zlib header and adler32
    adler = struct.unpack(">I", z[-4:])[0]
    expected_adler = zlib.adler32(db) & 0xFFFFFFFF
    print(f"  adler32: stored=0x{adler:08X}  computed=0x{expected_adler:08X}  match={adler==expected_adler}")
    print(f"  compressed payload: {len(compressed)} bytes")
    
    # Check deflate structure: block count, block types, boundary bytes
    raw = compressed
    print(f"  first 16 deflate bytes: {raw[:16].hex()}")

# Now do deep comparison of the two zlib streams
with open(f"{BIN}/M5_CRSB_CGY", "rb") as f:
    m5_data = f.read()
with open(f"{BIN}/S2_CRSB_CGY", "rb") as f:
    s2_data = f.read()

m5_db = zlib.decompress(m5_data[48:])
s2_db = zlib.decompress(s2_data[48:])

print(f"\n{'='*60}")
print("UNPACKED DB COMPARISON")
print(f"{'='*60}")
assert len(m5_db) == len(s2_db)
diffs = [(i, m5_db[i], s2_db[i]) for i in range(len(m5_db)) if m5_db[i] != s2_db[i]]
print(f"Decompressed DBs differ at {len(diffs)} positions:")
for off, mv, sv in diffs:
    print(f"  0x{off:06X}: S2=0x{sv:02X} M5=0x{mv:02X}")

# Now compare the RAW ZLIB streams before decompression
print(f"\n{'='*60}")
print("RAW ZLIB COMPARISON (compressed data)")
print(f"{'='*60}")

m5_z = m5_data[48:]
s2_z = s2_data[48:]
assert len(m5_z) == len(s2_z), f"zlib lengths differ: {len(m5_z)} vs {len(s2_z)}"
print(f"Zlib payloads: both {len(m5_z)} bytes")

m5_raw = m5_z[2:]  # skip zlib header
s2_raw = s2_z[2:]

# Find first diff in compressed data
first_diff = None
for i in range(len(m5_raw)):
    if m5_raw[i] != s2_raw[i]:
        first_diff = i
        break

print(f"First compressed diff at offset {first_diff} (zlib+{first_diff})")
if first_diff is not None:
    # Show a window around the first diff
    start = max(0, first_diff - 8)
    end = min(len(m5_raw), first_diff + 32)
    print(f"  M5[{start}:{end}]: {m5_raw[start:end].hex()}")
    print(f"  S2[{start}:{end}]: {s2_raw[start:end].hex()}")
    
    # Also show all regions where they differ
    diff_regions = []
    in_diff = False
    region_start = 0
    for i in range(len(m5_raw)):
        if m5_raw[i] != s2_raw[i]:
            if not in_diff:
                region_start = i
                in_diff = True
        else:
            if in_diff:
                diff_regions.append((region_start, i))
                in_diff = False
    if in_diff:
        diff_regions.append((region_start, len(m5_raw)))
    
    print(f"\n  Deflate diff regions ({len(diff_regions)}):")
    for rs, re_ in diff_regions:
        length = re_ - rs
        print(f"    [{rs}-{re_}) ({length} bytes): M5={m5_raw[rs:min(rs+16,re_)].hex()} S2={s2_raw[rs:min(rs+16,re_)].hex()}")

# Also check: does S4_OVI_COL (which also fails) have a very different zlib structure?
print(f"\n{'='*60}")
print("S4 OVI COL zlib structure")
print(f"{'='*60}")
with open(f"{BIN}/S4_OVI_COL", "rb") as f:
    s4 = f.read()
s4_db = zlib.decompress(s4[48:])
s4_z = s4[48:]
print(f"  decompressed: {len(s4_db)} bytes")
print(f"  zlib header: {s4_z[:2].hex()}")
print(f"  first 16 deflate: {s4_z[2:18].hex()}")

# Check player state  
base = 0x0A3168
for rec, pname in [(688,'Crosby'),(695,'Ovechkin'),(1232,'Hedman')]:
    rs = base + rec*132
    pt = (s4_db[rs+115]>>3)&0x1F
    ta = s4_db[rs+6]
    print(f"  {pname}: proteam={pt} team_alt={ta}")

#!/usr/bin/env python3
"""Precisely compare deflate structures: working MS_CO_CC vs our failing surgical saves."""
import zlib, struct

BIN = "_local/game-saves/xbox"

def count_deflate_blocks(data):
    """Proper deflate block counter. Returns (block_count, block_types)."""
    # data starts at zlib payload (after 78 9c)
    blocks = []
    bit_pos = 0
    while True:
        bfinal = (data[bit_pos//8] >> (bit_pos % 8)) & 1
        btype = ((data[bit_pos//8] >> ((bit_pos % 8) + 1)) & 1) | ((data[bit_pos//8] >> ((bit_pos % 8) + 2)) & 2)
        bit_pos += 3
        types = {0:"stored", 1:"fixed", 2:"dynamic"}
        blocks.append(types.get(btype, f"unknown({btype})"))
        if bfinal:
            break
        if btype == 0:  # stored
            bit_pos = (bit_pos + 7) // 8 * 8
            if bit_pos//8 + 4 > len(data):
                break
            length = struct.unpack_from("<H", data, bit_pos//8)[0]
            bit_pos += 32  # length + nlen
            bit_pos += length * 8
        elif btype == 1:  # fixed - just count it, can't skip
            break  # can't skip dynamic/fixed blocks easily
        elif btype == 2:  # dynamic
            break
    return len(blocks), blocks[:10]

# Check all 5 key files
for name in ["MS_CO_CC.bin", "MS_CC_OC.bin", "S2_CRSB_CGY", "S3_CRSB_T10", "S4_OVI_COL", "TRADEEDIT5"]:
    path = f"{BIN}/{name}"
    with open(path, "rb") as f:
        data = f.read()
    zlib_start = data[48:]
    assert zlib_start[:2] == b"\x78\x9c", f"{name}: no zlib magic, got {zlib_start[:2].hex()}"
    raw = zlib_start[2:]  # after zlib header
    n, types = count_deflate_blocks(raw)
    
    # Also check decompressed size and some bytes
    db = zlib.decompress(data[48:])
    print(f"{name:20}: {n:>3} blocks  types={types}  zlib_sz={len(zlib_start)}  db_sz={len(db)}")

# Also check: does TRADEEDIT5's zlib differ from what pack() produces?
# Let's decompress TRADEEDIT5 and a newly packed file to compare
print("\n--- Checking if pack() produces identical zlib for unchanged DB ---")
with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5 = f.read()
t5_db = zlib.decompress(t5[48:])

# Simulate pack(): it passes Some(template_zlib) to compress_zlib
# which calls deflate_template::compress_zlib_from_template
# If the DB is unchanged, pack() returns template verbatim (line 24-26)
print("pack() returns template verbatim for unchanged DB (checked at pack.rs:24)")

# Now let's try packing with NO template (stored blocks)
print("\n--- Testing stored-block compression ---")
import subprocess, os

# Create a stored-block version directly
tmp_db = os.path.abspath("tools/tmp/test_stored.db")
with open(tmp_db, "wb") as f:
    f.write(t5_db)

result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-stored", tmp_db,
    os.path.abspath(f"{BIN}/TRADEEDIT5"),
    "--output", os.path.abspath(f"{BIN}/TEST_STORED"),
], capture_output=True, text=True, cwd=os.getcwd())
print(f"pack-stored: {result.stderr.strip()[-200:]}")

# Check TEST_STORED block count
with open(f"{BIN}/TEST_STORED", "rb") as f:
    data = f.read()
raw = data[50:]  # after zlib header
n, types = count_deflate_blocks(raw)
db = zlib.decompress(data[48:])
base = 0x0A3168
print(f"TEST_STORED: {n} blocks, types={types}")
for rec, pname in [(688,'Crosby'),(695,'Ovi'),(1232,'Hedman')]:
    rs = base + rec*132
    pt = (db[rs+115]>>3)&0x1F
    ta = db[rs+6]
    print(f"  {pname}: proteam={pt} team_alt={ta}")

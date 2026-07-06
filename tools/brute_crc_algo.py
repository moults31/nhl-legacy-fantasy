#!/usr/bin/env python3
"""Brute-force the CRC algorithm for the 3 MS CRC fields.

Given: we know the exact input bytes (TRADEEDIT5 with normalization+edit)
and the expected output (MS reference CRC values).

Try: standard CRC-32 BE (poly 0x04C11DB7) over each gap region.
If that fails, try other polynomials, endianness, initial values.
"""
import zlib, struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5_raw = bytearray(zlib.decompress(f.read()[48:]))

with open(os.path.join(SRC, "default_ms_noedit.db"), "rb") as f:
    ms_noedit = f.read()

with open(os.path.join(SRC, "default_ms_crsb_col.db"), "rb") as f:
    ms_crsb = f.read()

def read_u32_be(data, off):
    return struct.unpack(">I", data[off:off+4])[0]

def poly_to_table(poly, reflect_in=False, reflect_out=False):
    """Build CRC-32 lookup table for a given polynomial."""
    table = []
    for i in range(256):
        crc = i << 24 if not reflect_in else i
        for _ in range(8):
            if reflect_in:
                if crc & 1:
                    crc = (crc >> 1) ^ poly
                else:
                    crc >>= 1
            else:
                if crc & 0x80000000:
                    crc = (crc << 1) ^ poly
                else:
                    crc <<= 1
        table.append(crc & 0xFFFFFFFF)
    return table

def crc32_custom(data, poly, init=0, final_xor=0, reflect_in=False, reflect_out=False):
    """Compute CRC-32 with custom parameters."""
    table = poly_to_table(poly, reflect_in, reflect_out)
    crc = init ^ 0xFFFFFFFF if not reflect_in else init
    for byte in data:
        if reflect_in:
            crc = (crc >> 8) ^ table[(crc ^ byte) & 0xFF]
        else:
            crc = ((crc << 8) ^ table[((crc >> 24) ^ byte) & 0xFF]) & 0xFFFFFFFF
    if reflect_out:
        crc = reflect32(crc)
    return crc ^ final_xor

def crc32_ea(data, seed=0):
    """EA's two-bytes-per-iteration CRC-32 (poly 0x04C11DB7).
    
    This is the algorithm from ea-tdb::Crc32Be.
    """
    POLY = 0x04C11DB7
    table = poly_to_table(POLY, reflect_in=False, reflect_out=False)
    
    crc = seed ^ 0xFFFFFFFF
    data_len = len(data)
    i = 0
    
    # Process in pairs where possible
    while i + 1 < data_len:
        a = data[i]
        b = data[i + 1]
        crc = (table[((crc >> 24) ^ a) & 0xFF] ^ (crc << 8)) & 0xFFFFFFFF
        crc = (table[((crc >> 24) ^ b) & 0xFF] ^ (crc << 8)) & 0xFFFFFFFF
        i += 2
    
    # Process remaining single byte
    if i < data_len:
        crc = (table[((crc >> 24) ^ data[i]) & 0xFF] ^ (crc << 8)) & 0xFFFFFFFF
    
    return crc ^ 0xFFFFFFFF

def reflect32(x):
    x = ((x & 0x55555555) << 1) | ((x >> 1) & 0x55555555)
    x = ((x & 0x33333333) << 2) | ((x >> 2) & 0x33333333)
    x = ((x & 0x0F0F0F0F) << 4) | ((x >> 4) & 0x0F0F0F0F)
    x = ((x & 0x00FF00FF) << 8) | ((x >> 8) & 0x00FF00FF)
    return ((x & 0x0000FFFF) << 16) | ((x >> 16) & 0x0000FFFF)

# Build the modified DB (normalization + Crosby edit)
db = bytearray(t5_raw)
crosby_rs = 0x0A3168 + 688 * 132

# Normalization
db[0x0CACAE] = 0x08
db[0x0CAD1B] = 0x40
db[0x1B97D1] = 0x00
db[0x1B97D2] = 0x00
db[0x1B97EC] = 0x07
db[0x1B97F1] = 0x70
db[0x1B97F2] = 0x50
db[0x1B97F4] = 0x98
db[0x1AB24B] = 0x0C

# Crosby edit (but leave CRCs at original values for now)
db[crosby_rs + 115] = 0x40
db[crosby_rs + 6] = 8
db[0x1B97E1] = 0x00
db[0x1B97E2] = 0x00
db[0x1B97FC] = 7
db[0x1B9801] = 0x41
db[0x1B9802] = 0x10
db[0x1B9804] = 0x98
db[0x1B9805] = 0x80
db[0x1AB24B] = 0x0D

# Now compute table boundaries (from TRADEEDIT5 layout)
table_count = read_u32_be(t5_raw, 16)
TABLE_DATA_START = 24 + table_count * 8
TABLE_INFO_SIZE = 40
FIELD_DESC_SIZE = 16

entries = []
for i in range(table_count):
    off = 24 + i * 8
    tid = t5_raw[off:off+4].decode("ascii", errors="replace")
    data_off = read_u32_be(t5_raw, off + 4)
    entries.append((tid, data_off))

def table_info(tid_name):
    for i, (tid, data_off) in enumerate(entries):
        if tid == tid_name:
            return TABLE_DATA_START + data_off
    return None

# Region definitions (end of previous table = start of next table's info,
# since the TDB chain CRC covers from end of previous records to start of next)
# Actually, the TDB chain CRC covers: from END of previous table's last record
# to START of this table's info. Let's trace this exactly.

# RBQQ.prior_crc covers: end of cPbu records -> start of RBQQ info
# = cPbu gap end (next table info start) -> RBQQ info_start
# Actually: the prior_crc covers from where the LAST table's records ended
# to where THIS table's info starts.

# Let me use the reseal_checksums logic:
# For each table i:
#   prior_crc = !crc(data, gap_size, last_end)
# where last_end is the end of the previous table (info + TABLE_INFO_SIZE, or 
# records_end for the initial chain).

# In ea-tdb reseal:
#   let mut prior = !crc.crc32_be(0, data, dir_len, 24);
#   // Then for table 0: write prior_crc = prior (gap from dir end to table start)
#   // Then compute next prior = !crc(data, gap, last_end)
# where last_end = info_off + TABLE_INFO_SIZE

# Wait, let me re-read the reseal code more carefully.

print("=== Computing CRC_A (RBQQ.prior_crc @ 0x1A4838) ===")
rbqq_info = table_info("RBQQ")
cpbu_info = table_info("cPbu")
sozv_info = table_info("sozv")

# The gap for RBQQ.prior_crc: from where cPbu's records end to RBQQ's info start
# But cPbu records end at... hmm
# Let me use the actual file bytes to figure the gap.

# Actually, the TDB chain CRC works like this:
# prior_crc[i] = NOT(CRC(data[gap_start..gap_end], seed=0))
# where gap = (end of previous table's last record) to (start of table i's info)
# and "end of previous table's last record" = prev_info + TABLE_INFO_SIZE + num_fields*16 + cur_records*rec_len

# Let me compute this properly for each table

def compute_gap_bounds():
    """Return list of (gap_start, gap_end) for each table's prior_crc gap."""
    gaps = []
    table_data_start = 24 + table_count * 8
    
    # First table: gap from directory end to table start
    dir_end = table_data_start
    first_info = table_data_start + entries[0][1]
    gaps.append((dir_end, first_info))
    
    for i in range(1, len(entries)):
        # End of previous table's data
        prev_tid, prev_data_off = entries[i-1]
        prev_info = table_data_start + prev_data_off
        
        prev_num_fields = t5_raw[prev_info + 20]
        prev_rec_len = read_u32_be(t5_raw, prev_info + 8)
        prev_cur = struct.unpack(">H", t5_raw[prev_info+18:prev_info+20])[0]
        
        prev_data_end = prev_info + TABLE_INFO_SIZE + prev_num_fields * FIELD_DESC_SIZE + prev_cur * prev_rec_len
        
        # Start of current table info
        curr_info = table_data_start + entries[i][1]
        
        gaps.append((prev_data_end, curr_info))
    
    return gaps

gaps = compute_gap_bounds()

# Find which gap belongs to RBQQ and caBZ
rbqq_idx = next(i for i, (tid, _) in enumerate(entries) if tid == "RBQQ")
cabz_idx = next(i for i, (tid, _) in enumerate(entries) if tid == "caBZ")
ulge_idx = next(i for i, (tid, _) in enumerate(entries) if tid == "ulGe")

print(f"RBQQ is table {rbqq_idx}, gap = [{gaps[rbqq_idx][0]:#010X}, {gaps[rbqq_idx][1]:#010X})")
print(f"caBZ is table {cabz_idx}, gap = [{gaps[cabz_idx][0]:#010X}, {gaps[cabz_idx][1]:#010X})")

# Compute CRC_A: RBQQ.prior_crc = !crc32_ea(data, gap_start, gap_len)
gap_start, gap_end = gaps[rbqq_idx]
gap_data = bytes(db[gap_start:gap_end])
crc_a_computed = (~crc32_ea(gap_data, 0)) & 0xFFFFFFFF

ms_crc_a = read_u32_be(ms_crsb, 0x1A4838)
raw_crc_a = read_u32_be(db, 0x1A4838)

print(f"\nCRC_A (RBQQ.prior_crc):")
print(f"  Raw (stale): 0x{raw_crc_a:08X}")
print(f"  MS target:   0x{ms_crc_a:08X}")
print(f"  Computed:    0x{crc_a_computed:08X} {'MATCH!' if crc_a_computed == ms_crc_a else 'MISMATCH'}")
print(f"  Gap: [{gap_start:#010X}, {gap_end:#010X}) = {gap_end - gap_start} bytes")

# Compute CRC_B: ulGe.header_crc = !crc32_ea(data, info+4, 32)
ulge_info = table_info("ulGe")
header_data = bytes(db[ulge_info + 4 : ulge_info + 36])
crc_b_computed = (~crc32_ea(header_data, 0)) & 0xFFFFFFFF

ms_crc_b = read_u32_be(ms_crsb, 0x1AB258)
raw_crc_b = read_u32_be(db, 0x1AB258)

print(f"\nCRC_B (ulGe.header_crc):")
print(f"  Raw (stale): 0x{raw_crc_b:08X}")
print(f"  MS target:   0x{ms_crc_b:08X}")
print(f"  Computed:    0x{crc_b_computed:08X} {'MATCH!' if crc_b_computed == ms_crc_b else 'MISMATCH'}")
print(f"  Header: [{ulge_info+4:#010X}, {ulge_info+36:#010X})")

# Compute CRC_C: caBZ.prior_crc
gap_start, gap_end = gaps[cabz_idx]
gap_data = bytes(db[gap_start:gap_end])
crc_c_computed = (~crc32_ea(gap_data, 0)) & 0xFFFFFFFF

ms_crc_c = read_u32_be(ms_crsb, 0x1D5F2C)
raw_crc_c = read_u32_be(db, 0x1D5F2C)

print(f"\nCRC_C (caBZ.prior_crc):")
print(f"  Raw (stale): 0x{raw_crc_c:08X}")
print(f"  MS target:   0x{ms_crc_c:08X}")
print(f"  Computed:    0x{crc_c_computed:08X} {'MATCH!' if crc_c_computed == ms_crc_c else 'MISMATCH'}")
print(f"  Gap: [{gap_start:#010X}, {gap_end:#010X}) = {gap_end - gap_start} bytes")

# If mismatched, try different CRC algorithms
print("\n=== BRUTE FORCE (if needed) ===")
algorithms = [
    ("EA CRC32BE (poly 0x04C11DB7, 2-byte/iter)", lambda d: crc32_ea(d, 0)),
    ("Std BE (poly 0x04C11DB7)", lambda d: crc32_custom(d, 0x04C11DB7, 0, 0xFFFFFFFF, False, False)),
    ("Reflected (poly 0xEDB88320)", lambda d: crc32_custom(d, 0xEDB88320, 0xFFFFFFFF, 0xFFFFFFFF, True, True)),
    ("zlib crc32", lambda d: zlib.crc32(d) & 0xFFFFFFFF),
    ("CRC-32/MPEG2 (poly 0x04C11DB7, init=0xFFFFFFFF)", lambda d: crc32_custom(d, 0x04C11DB7, 0xFFFFFFFF, 0, False, False)),
    ("CRC-32/BZIP2", lambda d: crc32_custom(d, 0x04C11DB7, 0xFFFFFFFF, 0xFFFFFFFF, False, False)),
]

for name, func in algorithms:
    # Test on CRC_A gap
    val = (~func(gap_data)) & 0xFFFFFFFF
    a_ok = val == ms_crc_a
    # Test on CRC_C gap
    gap_start_c, gap_end_c = gaps[cabz_idx]
    val_c = (~func(bytes(db[gap_start_c:gap_end_c]))) & 0xFFFFFFFF
    c_ok = val_c == ms_crc_c
    if a_ok or c_ok:
        print(f"  {name}: CRC_A={'OK' if a_ok else '--'} CRC_C={'OK' if c_ok else '--'}")

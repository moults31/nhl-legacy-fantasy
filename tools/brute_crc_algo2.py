#!/usr/bin/env python3
"""Fix gap boundaries for prior_crc computation.

prior_crc covers: [prev_table_info + 40, this_table_info)
NOT: [prev_table_records_end, this_table_info)
"""
import zlib, struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5_raw = bytearray(zlib.decompress(f.read()[48:]))

with open(os.path.join(SRC, "default_ms_crsb_col.db"), "rb") as f:
    ms_crsb = f.read()

with open(os.path.join(SRC, "default_ms_noedit.db"), "rb") as f:
    ms_noedit = f.read()

def read_u32_be(data, off):
    return struct.unpack(">I", data[off:off+4])[0]

# EA CRC-32 BE (poly 0x04C11DB7, two-bytes-per-iteration)
def crc32_ea(data, seed=0):
    POLY = 0x04C11DB7
    table = []
    for i in range(256):
        crc = i << 24
        for _ in range(8):
            if crc & 0x80000000:
                crc = (crc << 1) ^ POLY
            else:
                crc <<= 1
        table.append(crc & 0xFFFFFFFF)
    
    crc = seed ^ 0xFFFFFFFF
    data_len = len(data)
    i = 0
    while i + 1 < data_len:
        a = data[i]
        b = data[i + 1]
        crc = (table[((crc >> 24) ^ a) & 0xFF] ^ (crc << 8)) & 0xFFFFFFFF
        crc = (table[((crc >> 24) ^ b) & 0xFF] ^ (crc << 8)) & 0xFFFFFFFF
        i += 2
    if i < data_len:
        crc = (table[((crc >> 24) ^ data[i]) & 0xFF] ^ (crc << 8)) & 0xFFFFFFFF
    return crc ^ 0xFFFFFFFF

table_count = read_u32_be(t5_raw, 16)
TABLE_DATA_START = 24 + table_count * 8
TABLE_INFO_SIZE = 40

entries = []
for i in range(table_count):
    off = 24 + i * 8
    tid = t5_raw[off:off+4].decode("ascii", errors="replace")
    data_off = read_u32_be(t5_raw, off + 4)
    info_off = TABLE_DATA_START + data_off
    entries.append((tid, info_off))

# Build the modified DB (normalization + Crosby edit, stale CRCs)
db = bytearray(t5_raw)
crosby_rs = 0x0A3168 + 688 * 132

db[0x0CACAE] = 0x08; db[0x0CAD1B] = 0x40
db[0x1B97D1] = 0x00; db[0x1B97D2] = 0x00
db[0x1B97EC] = 0x07; db[0x1B97F1] = 0x70
db[0x1B97F2] = 0x50; db[0x1B97F4] = 0x98
db[0x1AB24B] = 0x0C
db[crosby_rs + 115] = 0x40; db[crosby_rs + 6] = 8
db[0x1B97E1] = 0x00; db[0x1B97E2] = 0x00
db[0x1B97FC] = 7; db[0x1B9801] = 0x41
db[0x1B9802] = 0x10; db[0x1B9804] = 0x98
db[0x1B9805] = 0x80; db[0x1AB24B] = 0x0D

def table_info(tid_name):
    for tid, info_off in entries:
        if tid == tid_name:
            return info_off
    return None

# Compute CRC_A: RBQQ.prior_crc
# gap = RBQQ_info - (cPbu_info + 40) ... but wait, it's not always cPbu.
# For the chain, prior_crc[i] covers gap from: (entries[i-1].info + 40) to (entries[i].info)
# And prior_crc[0] covers gap from: (dir_end) to (entries[0].info)

rbqq_idx = next(i for i, (tid, _) in enumerate(entries) if tid == "RBQQ")
cpbu_idx = rbqq_idx - 1
cpbu_info = entries[cpbu_idx][1]
rbqq_info = entries[rbqq_idx][1]

# Correct gap: from cPbu header end to RBQQ info start
gap_a_start = cpbu_info + TABLE_INFO_SIZE
gap_a_end = rbqq_info
gap_a_data = bytes(db[gap_a_start:gap_a_end])
crc_a_computed = (~crc32_ea(gap_a_data, 0)) & 0xFFFFFFFF
ms_crc_a = read_u32_be(ms_crsb, 0x1A4838)

print(f"CRC_A (RBQQ.prior_crc):")
print(f"  Gap: [{gap_a_start:#010X}, {gap_a_end:#010X}) = {gap_a_end - gap_a_start} bytes")
print(f"  Computed: 0x{crc_a_computed:08X}")
print(f"  MS target: 0x{ms_crc_a:08X}")
print(f"  {'MATCH!' if crc_a_computed == ms_crc_a else 'MISMATCH'}")

# CRC_B: ulGe.header_crc (already verified)
ulge_info = table_info("ulGe")
header_data = bytes(db[ulge_info + 4 : ulge_info + 36])
crc_b_computed = (~crc32_ea(header_data, 0)) & 0xFFFFFFFF
ms_crc_b = read_u32_be(ms_crsb, 0x1AB258)
print(f"\nCRC_B (ulGe.header_crc):")
print(f"  Computed: 0x{crc_b_computed:08X}")
print(f"  MS target: 0x{ms_crc_b:08X}")
print(f"  {'MATCH!' if crc_b_computed == ms_crc_b else 'MISMATCH'}")

# CRC_C: caBZ.prior_crc
cabz_idx = next(i for i, (tid, _) in enumerate(entries) if tid == "caBZ")
ulge_idx = cabz_idx - 1
ulge_info2 = entries[ulge_idx][1]
cabz_info = entries[cabz_idx][1]

gap_c_start = ulge_info2 + TABLE_INFO_SIZE
gap_c_end = cabz_info
gap_c_data = bytes(db[gap_c_start:gap_c_end])
crc_c_computed = (~crc32_ea(gap_c_data, 0)) & 0xFFFFFFFF
ms_crc_c = read_u32_be(ms_crsb, 0x1D5F2C)

print(f"\nCRC_C (caBZ.prior_crc):")
print(f"  Gap: [{gap_c_start:#010X}, {gap_c_end:#010X}) = {gap_c_end - gap_c_start} bytes")
print(f"  Computed: 0x{crc_c_computed:08X}")
print(f"  MS target: 0x{ms_crc_c:08X}")
print(f"  {'MATCH!' if crc_c_computed == ms_crc_c else 'MISMATCH'}")

# Also verify on no-edit MS
if crc_a_computed == ms_crc_a and crc_c_computed == ms_crc_c:
    print("\n=== ALL MATCH! Verifying on other test cases ===")
    test_files = [
        ("default_ms_noedit.db", "no-edit"),
        ("default_ms_crsb_col.db", "Crosby->COL"),
        ("default_ms_ovi_col.db", "Ovechkin->COL"),
        ("default_ms_crsb_cgy.db", "Crosby->CGY"),
    ]
    for fname, label in test_files:
        with open(os.path.join(SRC, fname), "rb") as f:
            ms = f.read()
        
        # Compute expected CRCs from MS file
        ms_crc_a = read_u32_be(ms, 0x1A4838)
        ms_crc_b = read_u32_be(ms, 0x1AB258)
        ms_crc_c = read_u32_be(ms, 0x1D5F2C)
        
        our_a = (~crc32_ea(bytes(ms[gap_a_start:gap_a_end]), 0)) & 0xFFFFFFFF
        our_b = (~crc32_ea(bytes(ms[ulge_info+4:ulge_info+36]), 0)) & 0xFFFFFFFF
        our_c = (~crc32_ea(bytes(ms[gap_c_start:gap_c_end]), 0)) & 0xFFFFFFFF
        
        ok = our_a == ms_crc_a and our_b == ms_crc_b and our_c == ms_crc_c
        print(f"  {label}: {'ALL OK' if ok else 'FAIL'}")
        if not ok:
            for name, our, ms_val in [("A", our_a, ms_crc_a), ("B", our_b, ms_crc_b), ("C", our_c, ms_crc_c)]:
                if our != ms_val:
                    print(f"    CRC_{name}: ours=0x{our:08X} ms=0x{ms_val:08X}")

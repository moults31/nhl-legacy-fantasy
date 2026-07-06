#!/usr/bin/env python3
"""Compare Rust ea-tdb CRC with Python implementation to find mismatch."""
import zlib, struct, os, subprocess

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5_raw = bytearray(zlib.decompress(f.read()[48:]))

with open(os.path.join(SRC, "default_ms_crsb_col.db"), "rb") as f:
    ms_crsb = f.read()

def read_u32_be(data, off):
    return struct.unpack(">I", data[off:off+4])[0]

# --- Rust-equivalent nibble-at-a-time CRC ---
CRC_POLY_BE = 0x04C11DB7

def build_table_rust():
    """Rust ea-tdb table build algorithm."""
    table = [0] * 256
    carry = 0x80000000
    i = 1
    while i < 256:
        table[i] = carry
        carry = (carry << 1) & 0xFFFFFFFF
        if carry == 0:  # we overflowed
            # Actually check: if the PREVIOUS carry had the top bit set
            pass
        # The Rust code: carry = if carry & 0x8000_0000 != 0 { (carry << 1) ^ poly } else { carry << 1 }
        # Wait, that checks the PRE-SHIFT carry. Let me re-read.
        j = 1
        while j < i:
            table[i + j] = table[i] ^ table[j]
            j += 1
        i <<= 1
    return table

def crc32_rust_style(data, seed=0):
    """Rust ea-tdb crc32_be implementation."""
    table = build_table_rust()
    crc = seed ^ 0xFFFFFFFF
    i = 0
    remaining = len(data)
    while remaining > 0:
        byte = data[i]
        i += 1
        remaining -= 1
        crc ^= (byte << 24) & 0xFFFFFFFF
        idx = ((crc << 4) >> 28) & 0xFF
        crc ^= table[idx]
        idx = ((crc << 4) >> 28) & 0xFF
        crc ^= table[idx]
    return crc ^ 0xFFFFFFFF

# Build tables
# My Python table (standard byte-based)
def build_byte_table(poly):
    table = []
    for i in range(256):
        crc = i << 24
        for _ in range(8):
            if crc & 0x80000000:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
        table.append(crc & 0xFFFFFFFF)
    return table

# My Python CRC (two bytes per iter)
def crc32_ea_python(data, seed=0):
    table = build_byte_table(CRC_POLY_BE)
    crc = seed ^ 0xFFFFFFFF
    dl = len(data)
    i = 0
    while i + 1 < dl:
        a = data[i]
        b = data[i + 1]
        crc = (table[((crc >> 24) ^ a) & 0xFF] ^ (crc << 8)) & 0xFFFFFFFF
        crc = (table[((crc >> 24) ^ b) & 0xFF] ^ (crc << 8)) & 0xFFFFFFFF
        i += 2
    if i < dl:
        crc = (table[((crc >> 24) ^ data[i]) & 0xFF] ^ (crc << 8)) & 0xFFFFFFFF
    return crc ^ 0xFFFFFFFF

# Test with known values
test_data = b"123456789"
print("=== CRC implementations ===")
print(f"  Rust style: 0x{crc32_rust_style(test_data, 0):08X}")
print(f"  Python ea:  0x{crc32_ea_python(test_data, 0):08X}")
print(f"  Expected:   0x38823B6E")
print(f"  zlib crc32: 0x{zlib.crc32(test_data) & 0xFFFFFFFF:08X}")

# Now compute CRC_B (ulGe.header_crc) with both implementations
table_count = read_u32_be(t5_raw, 16)
TABLE_DATA_START = 24 + table_count * 8

entries = []
for i in range(table_count):
    off = 24 + i * 8
    tid = t5_raw[off:off+4].decode("ascii", errors="replace")
    data_off = read_u32_be(t5_raw, off + 4)
    info_off = TABLE_DATA_START + data_off
    entries.append((tid, info_off))

ulge_info = next(info for tid, info in entries if tid == "ulGe")

# Apply edits to DB
db = bytearray(t5_raw)
r = 0x0A3168 + 688 * 132
db[0x0CACAE]=0x08; db[0x0CAD1B]=0x40
db[0x1B97D1]=0x00; db[0x1B97D2]=0x00
db[0x1B97EC]=0x07; db[0x1B97F1]=0x70
db[0x1B97F2]=0x50; db[0x1B97F4]=0x98
db[0x1AB24B]=0x0C
db[r+115]=0x40; db[r+6]=8
db[0x1B97E1]=0x00; db[0x1B97E2]=0x00
db[0x1B97FC]=7; db[0x1B9801]=0x41
db[0x1B9802]=0x10; db[0x1B9804]=0x98
db[0x1B9805]=0x80; db[0x1AB24B]=0x0D

header = bytes(db[ulge_info+4:ulge_info+36])
print(f"\nulGe header CRC:")
print(f"  Rust style: 0x{crc32_rust_style(header, 0):08X}")
print(f"  Python ea:  0x{crc32_ea_python(header, 0):08X}")
print(f"  MS target:  0x{read_u32_be(ms_crsb, 0x1AB258):08X}")

# Also test the gap CRC
cpbu_info = next(info for tid, info in entries if tid == "cPbu")
rbqq_info = next(info for tid, info in entries if tid == "RBQQ")
gap = bytes(db[cpbu_info+40:rbqq_info])
print(f"\ncPbu->RBQQ gap CRC (CRC_A):")
print(f"  Rust style: 0x{~crc32_rust_style(gap, 0) & 0xFFFFFFFF:08X}")
print(f"  Python ea:  0x{~crc32_ea_python(gap, 0) & 0xFFFFFFFF:08X}")
print(f"  MS target:  0x{read_u32_be(ms_crsb, 0x1A4838):08X}")

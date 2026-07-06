#!/usr/bin/env python3
"""Map TDB structure around CRC offsets to identify what each CRC covers."""
import zlib, struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"

# Decompress TRADEEDIT5
with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5 = zlib.decompress(f.read()[48:])

def read_u32_be(data, off):
    return struct.unpack(">I", data[off:off+4])[0]

CRC_A = 0x1A4838
CRC_B = 0x1AB258
CRC_C = 0x1D5F2C

# Parse TDB header
magic = t5[0:4]
endian = read_u32_be(t5, 4)
source_size = read_u32_be(t5, 8)
reserved = read_u32_be(t5, 12)
table_count = read_u32_be(t5, 16)
header_crc = read_u32_be(t5, 20)
dir_start = 24

print(f"Magic: {magic.hex()} ({magic})")
print(f"Endian marker: {endian}")
print(f"Source size: {source_size} (0x{source_size:X})")
print(f"Table count: {table_count}")
print(f"Header CRC @0x14: 0x{header_crc:08X}")
print(f"Directory at offset 0x{dir_start:X}")
print()

# Parse directory entries
print("=== DIRECTORY ===")
entries = []
for i in range(table_count):
    off = dir_start + i * 8
    tid = t5[off:off+4].decode("ascii", errors="replace")
    data_off = read_u32_be(t5, off + 4)
    entries.append((tid, data_off))
    print(f"  [{i:2d}] '{tid}' @ data_offset 0x{data_off:08X}")

TABLE_INFO_SIZE = 40
FIELD_DESC_SIZE = 16

crcs = [
    ("CRC_A", CRC_A, "0x1A4838"),
    ("CRC_B", CRC_B, "0x1AB258"),
    ("CRC_C", CRC_C, "0x1D5F2C"),
]

print("\n=== CRC LOCATIONS IN TDB STRUCTURE ===")

for crc_name, crc_off, crc_hex in crcs:
    value = read_u32_be(t5, crc_off)
    print(f"\n--- {crc_name} @ {crc_hex} = 0x{value:08X} ---")
    
    for i, (tid, data_off) in enumerate(entries):
        table_data_start = 24 + table_count * 8
        info_off = table_data_start + data_off
        
        if crc_off < info_off:
            print(f"  Before table '{tid}' (info @ 0x{info_off:X})")
            continue
        
        if i + 1 < len(entries):
            next_info = table_data_start + entries[i+1][1]
        else:
            next_info = len(t5)
        
        if info_off <= crc_off < next_info:
            prior_crc = read_u32_be(t5, info_off)
            rec_len_bytes = read_u32_be(t5, info_off + 8)
            rec_len_bits = read_u32_be(t5, info_off + 12)
            cur_recs = struct.unpack(">H", t5[info_off+18:info_off+20])[0]
            max_recs = struct.unpack(">H", t5[info_off+16:info_off+18])[0]
            num_fields = t5[info_off + 20]
            table_hdr_crc = read_u32_be(t5, info_off + 36)
            
            records_start = info_off + TABLE_INFO_SIZE + num_fields * FIELD_DESC_SIZE
            
            print(f"  In table '{tid}'")
            print(f"    Info @ 0x{info_off:08X}, Records @ 0x{records_start:08X}")
            print(f"    rec_len_bytes = {rec_len_bytes}, fields = {num_fields}")
            print(f"    Records: {cur_recs}/{max_recs}, end @ 0x{records_start + cur_recs * rec_len_bytes:08X}")
            
            rel_off = crc_off - info_off
            print(f"    CRC relative to info: +0x{rel_off:X}")
            
            if crc_off >= records_start:
                rec_idx = (crc_off - records_start) // rec_len_bytes
                rec_remainder = (crc_off - records_start) % rec_len_bytes
                print(f"    In record {rec_idx} @ byte +{rec_remainder}")
            else:
                print(f"    In table header/metadata region")
            break

# Check CRC_B at 0x1AB258 more closely
print(f"\n=== CRC_B CONTEXT (0x1AB258) ===")
print(f"  -32: {t5[CRC_B-32:CRC_B].hex(' ')}")
print(f"  CRC: {t5[CRC_B:CRC_B+4].hex(' ')}")
print(f"  +4:  {t5[CRC_B+4:CRC_B+36].hex(' ')}")

# Known TDB CRCs for comparison
print(f"\n=== KNOWN TDB CRCs ===")
print(f"  Header @ 0x14: 0x{read_u32_be(t5, 0x14):08X}")
for i, (tid, data_off) in enumerate(entries):
    table_data_start = 24 + table_count * 8
    info_off = table_data_start + data_off
    prior = read_u32_be(t5, info_off)
    hdr = read_u32_be(t5, info_off + 36)
    print(f"  '{tid}': prior=0x{prior:08X}  hdr=0x{hdr:08X}")
eof_off = len(t5) - 4
print(f"  EOF @ 0x{eof_off:X}: 0x{read_u32_be(t5, eof_off):08X}")

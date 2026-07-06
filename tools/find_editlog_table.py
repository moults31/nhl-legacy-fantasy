#!/usr/bin/env python3
"""Find the edit-log master table and map record indices to edit-log slots."""
import zlib, struct, os

BIN = "_local/game-saves/xbox"

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5 = bytearray(zlib.decompress(f.read()[48:]))

def read_u32_be(d, o): return struct.unpack(">I", d[o:o+4])[0]

table_count = read_u32_be(t5, 16)
TABLE_DATA_START = 24 + table_count * 8

# Parse directory
entries = []
for i in range(table_count):
    off = 24 + i * 8
    tid = t5[off:off+4].decode("ascii", errors="replace")
    data_off = read_u32_be(t5, off + 4)
    info = TABLE_DATA_START + data_off
    entries.append((tid, info, data_off))

# Find tables near the edit-log regions (0x1ACE00-0x1ACF00 and 0x1B9700-0x1B9800)
print("=== TABLES NEAR EDIT-LOG REGIONS ===")
for tid, info, _ in entries:
    rec_len = read_u32_be(t5, info + 8)
    cur_recs = struct.unpack(">H", t5[info+18:info+20])[0]
    num_fields = t5[info + 20]
    rec_start = info + 40 + num_fields * 16
    rec_end = rec_start + cur_recs * rec_len
    
    # Check if this table covers 0x1ACE00 or 0x1B9700
    if (rec_start <= 0x1ACF00 and rec_end >= 0x1ACE00) or \
       (rec_start <= 0x1B9800 and rec_end >= 0x1B9700):
        print(f"\n  '{tid}' @ 0x{info:06X}")
        print(f"    Records: 0x{rec_start:06X} - 0x{rec_end:06X}, len={rec_len}, count={cur_recs}")
        
        # See which records contain the edit-log bytes
        for r in range(cur_recs):
            r_off = rec_start + r * rec_len
            if r_off <= 0x1ACE00 < r_off + rec_len:
                print(f"    Record {r} covers 0x1ACE00 region")
            if r_off <= 0x1B9700 < r_off + rec_len:
                print(f"    Record {r} covers 0x1B9700 region")

# Also dump ALL tables for context
print("\n=== ALL TABLES ===")
for i, (tid, info, _) in enumerate(entries):
    rec_len = read_u32_be(t5, info + 8)
    cur_recs = struct.unpack(">H", t5[info+18:info+20])[0]
    max_recs = struct.unpack(">H", t5[info+16:info+18])[0]
    num_fields = t5[info + 20]
    rec_start = info + 40 + num_fields * 16
    rec_end = rec_start + cur_recs * rec_len
    print(f"  [{i:2d}] '{tid}': info=0x{info:06X} recs={cur_recs}/{max_recs} len={rec_len} fields={num_fields} data=[0x{rec_start:06X}, 0x{rec_end:06X})")

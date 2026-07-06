#!/usr/bin/env python3
"""Analyze which table and field TDB byte offset 0x1AE750 falls into.

TRADEEDIT5 is the packed roster container (48-byte header + zlib payload).
TRADEEDIT5.db is the already-decompressed TDB payload.
We use the decompressed .db as our baseline.
"""
import struct, os

DB = r"C:\Users\galileo\code\nhl-legacy-fantasy\_local\game-saves\xbox\TRADEEDIT5.db"

def u32(d, o):
    return struct.unpack(">I", d[o:o+4])[0]

def u16(d, o):
    return struct.unpack(">H", d[o:o+2])[0]

with open(DB, "rb") as f:
    db = f.read()

print(f"TRADEEDIT5.db: {len(db)} bytes ({len(db):#X})")

# === TDB Header (0x00 - 0x17) ===
magic = db[0:4]
endian_marker = u32(db, 4)
source_size = u32(db, 8)
reserved = u32(db, 12)
table_count = u32(db, 16)
header_crc = u32(db, 20)

print(f"\n=== TDB HEADER ===")
print(f"  magic:       {magic.hex()} ('{magic.decode('ascii', errors='replace')}')")
print(f"  endian:      0x{endian_marker:08X} ({'Big' if endian_marker==1 else 'Little' if endian_marker==0 else '?'})")
print(f"  source_size: 0x{source_size:08X} ({source_size})")
print(f"  reserved:    0x{reserved:08X}")
print(f"  table_count: {table_count}")
print(f"  header_crc:  0x{header_crc:08X}")

DIRECTORY_OFFSET = 0x18
DIRECTORY_ENTRY_SIZE = 8
TABLE_DATA_START = DIRECTORY_OFFSET + table_count * DIRECTORY_ENTRY_SIZE

print(f"\n  directory:   0x{DIRECTORY_OFFSET:X} - 0x{TABLE_DATA_START:X} ({TABLE_DATA_START - DIRECTORY_OFFSET} bytes)")
print(f"  table_data_start: 0x{TABLE_DATA_START:X}")

# === Parse Directory ===
print(f"\n=== DIRECTORY ({table_count} tables) ===")
entries = []  # (table_id, abs_offset_of_info_block)
for i in range(table_count):
    off = DIRECTORY_OFFSET + i * DIRECTORY_ENTRY_SIZE
    tid = db[off:off+4].decode("ascii", errors="replace")
    data_off = u32(db, off + 4)
    abs_info = TABLE_DATA_START + data_off
    entries.append((tid, abs_info))
    print(f"  [{i:2d}] {tid}  data_off=0x{data_off:06X}  abs=0x{abs_info:06X}")

TABLE_INFO_SIZE = 40
FIELD_DESCRIPTOR_SIZE = 16

# === Build table layout map ===
print(f"\n=== TABLE LAYOUTS ===")
table_index = []
for idx, (tid, abs_info) in enumerate(entries):
    info = {}
    info['tid'] = tid
    info['idx'] = idx
    info['info_off'] = abs_info
    info['record_len'] = u32(db, abs_info + 8)
    info['record_len_bits'] = u32(db, abs_info + 12)
    info['max_recs'] = u16(db, abs_info + 20)
    info['cur_recs'] = u16(db, abs_info + 22)
    info['num_fields'] = db[abs_info + 28]
    info['index_count'] = db[abs_info + 29]
    
    desc_off = abs_info + TABLE_INFO_SIZE
    info['desc_off'] = desc_off
    
    rec_off = desc_off + info['num_fields'] * FIELD_DESCRIPTOR_SIZE
    info['rec_off'] = rec_off
    
    rec_end = rec_off + info['cur_recs'] * info['record_len']
    info['rec_end'] = rec_end
    
    # gap after this table's records ends
    next_info = entries[idx+1][1] if idx+1 < len(entries) else len(db)
    info['gap_start'] = rec_end
    info['gap_end'] = next_info
    info['gap_size'] = next_info - rec_end
    
    table_index.append(info)
    
    # Print compact summary
    print(f"  [{idx:2d}] {tid:4s}  info=0x{abs_info:06X}  descs=0x{desc_off:06X}  "
          f"recs=0x{rec_off:06X}..0x{rec_end:06X}  "
          f"({info['cur_recs']}×{info['record_len']}B  {info['num_fields']}fields)  "
          f"gap={info['gap_size']}B")

# === Locate 0x1AE750 ===
TARGET = 0x1AE750
print(f"\n=== LOCATING OFFSET 0x{TARGET:X} ===")

found_in_table = False
for info in table_index:
    if info['rec_off'] <= TARGET < info['rec_end']:
        found_in_table = True
        tid = info['tid']
        idx = info['idx']
        rec_byte_off = TARGET - info['rec_off']
        rec_idx = rec_byte_off // info['record_len']
        byte_in_rec = rec_byte_off % info['record_len']
        
        print(f"\n  *** FOUND in table '{tid}' (index {idx}) ***")
        print(f"  Table info at:   0x{info['info_off']:06X}")
        print(f"  Records start at: 0x{info['rec_off']:06X}")
        print(f"  Records end at:   0x{info['rec_end']:06X}")
        print(f"  Record length:    {info['record_len']} bytes ({info['record_len_bits']} bits)")
        print(f"  Current records:  {info['cur_recs']}")
        print(f"  Target offset:    0x{TARGET:X}")
        print(f"  Byte into records region: +0x{rec_byte_off:X} ({rec_byte_off})")
        print(f"  Record index:     {rec_idx}  (0-based)")
        print(f"  Byte within record: +0x{byte_in_rec:X} ({byte_in_rec})")
        
        # Read field descriptors for this table
        desc_off = info['desc_off']
        print(f"\n  Field descriptors ({info['num_fields']} fields):")
        field_idx = None
        field_bounds = []
        for fi in range(info['num_fields']):
            fo = desc_off + fi * FIELD_DESCRIPTOR_SIZE
            kind = u32(db, fo)
            rec_bit_off = u32(db, fo + 4)
            fid = db[fo+8:fo+12].decode("ascii", errors="replace")
            bit_width = u32(db, fo + 12)
            
            byte_start = rec_bit_off // 8
            byte_end = (rec_bit_off + bit_width + 7) // 8
            field_bounds.append((fid, byte_start, byte_end, rec_bit_off, bit_width, kind))
            
            marker = ""
            if byte_start <= byte_in_rec < byte_end:
                marker = " <-- TARGET BYTE FALLS HERE"
                field_idx = fi
            
            print(f"    [{fi:2d}] {fid:4s}  kind=0x{kind:02X}  bit_off={rec_bit_off:4d}  "
                  f"bit_width={bit_width:3d}  bytes=[{byte_start:3d}..{byte_end:3d}){marker}")
        
        if field_idx is not None:
            fid, bs, be, rbo, bw, kd = field_bounds[field_idx]
            bit_offset_in_field = (byte_in_rec - bs) * 8 + (rec_bit_off % 8)
            print(f"\n  => RESULT: Table '{tid}', record {rec_idx}, "
                  f"field '{fid}' (index {field_idx})")
            print(f"     Byte offset 0x{TARGET:X} = record {rec_idx} byte +{byte_in_rec}")
            print(f"     Field '{fid}': bit_off={rbo}, bit_width={bw}, bytes [{bs}..{be})")
            
            # Read the actual field value for context
            rec_start = info['rec_off'] + rec_idx * info['record_len']
            field_bytes = db[rec_start + bs: rec_start + be]
            print(f"     Raw bytes at record {rec_idx}: {field_bytes.hex()}")
            print(f"     Bytes at 0x{TARGET:X}: {db[TARGET:TARGET+3].hex()}")
        else:
            print(f"\n  => Byte +{byte_in_rec} in record falls in un-fielded area or padding")
            print(f"     Bytes at 0x{TARGET:X}: {db[TARGET:TARGET+8].hex()}")
            # Show surrounding field boundaries
            for fid, bs, be, rbo, bw, kd in field_bounds:
                if be <= byte_in_rec or bs > byte_in_rec:
                    continue
            print(f"     Field boundaries around offset +{byte_in_rec}:")
            for fid, bs, be, rbo, bw, kd in field_bounds:
                if abs(bs - byte_in_rec) < 8 or abs(be - byte_in_rec) < 8:
                    rel = "before" if bs > byte_in_rec else "after"
                    print(f"       {fid}: bytes [{bs}..{be}) {rel} this byte")
        
        break

if not found_in_table:
    print("\n  *** NOT in any table's records region ***")
    for info in table_index:
        if info['gap_start'] <= TARGET < info['gap_end']:
            tid = info['tid']
            idx = info['idx']
            gap_off = TARGET - info['gap_start']
            print(f"  Falls in gap after '{tid}' (table {idx})")
            print(f"    Table records end: 0x{info['gap_start']:06X}")
            print(f"    Gap: [0x{info['gap_start']:06X}, 0x{info['gap_end']:06X}) = {info['gap_size']} bytes")
            print(f"    Target is at gap offset +0x{gap_off:X} ({gap_off} bytes into gap)")
            
            # Which table comes next
            next_idx = idx + 1
            if next_idx < len(entries):
                next_tid, next_abs = entries[next_idx]
                print(f"    Next table: '{next_tid}' at 0x{next_abs:06X}")
            
            print(f"\n    Bytes at 0x{TARGET:X}: {db[TARGET:TARGET+8].hex()}")
            # Show surrounding context
            print(f"    Context [-8..+8]: {db[TARGET-8:TARGET+8].hex()}")
            break
    else:
        print(f"  Offset 0x{TARGET:X} is beyond all table data")
        print(f"  Last table ends at: 0x{table_index[-1]['rec_end']:06X}")

# === Additional: check CRC region context ===
print(f"\n=== CRC / KNOWN REGIONS AROUND 0x{TARGET:X} ===")
crc_regions = {
    "CRC_A (RBQQ.prior)": (0x1A4838, 0x1A483C),
    "CRC_B (ulGe.header)": (0x1AB258, 0x1AB25C),
    "CRC_C (caBZ.prior)": (0x1D5F2C, 0x1D5F30),
    "cPbu records": None,
    "RBQQ info": None,
    "ulGe info": None,
    "caBZ info": None,
}
for tid, abs_info in entries:
    if tid == "cPbu":
        crc_regions["cPbu info"] = abs_info
    elif tid == "RBQQ":
        crc_regions["RBQQ info"] = abs_info
    elif tid == "ulGe":
        crc_regions["ulGe info"] = abs_info
    elif tid == "caBZ":
        crc_regions["caBZ info"] = abs_info

for name, val in sorted(crc_regions.items(), key=lambda x: x[1] or 0):
    if val is None:
        continue
    if isinstance(val, tuple):
        print(f"  {name}: 0x{val[0]:06X}-0x{val[1]:06X}  (dist from target: {val[0] - TARGET:+d})")
    else:
        print(f"  {name}: 0x{val:06X}  (dist from target: {val - TARGET:+d})")

# Check if target is near the cPbu table's end / RBQQ table's start
for info in table_index:
    if info['tid'] == "cPbu":
        print(f"\n  cPbu records end at 0x{info['rec_end']:06X}  (dist: {TARGET - info['rec_end']:+d})")
    if info['tid'] == "RBQQ":
        print(f"  RBQQ info at 0x{info['info_off']:06X}  (dist: {info['info_off'] - TARGET:+d})")

#!/usr/bin/env python3
"""Diff default.db vs default_ms_matt_ana.db to understand the real MS pattern."""
import zlib, struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"

with open(os.path.join(SRC, "default.db"), "rb") as f:
    noedit = f.read()

with open(os.path.join(SRC, "default_ms_matt_ana.db"), "rb") as f:
    matt_ana = f.read()

diffs = [(i, noedit[i], matt_ana[i]) for i in range(len(noedit)) if noedit[i] != matt_ana[i]]
print(f"Total diffs: {len(diffs)}")

crc_regions = [(0x1A4838, 0x1A483C), (0x1AB258, 0x1AB25C), (0x1D5F2C, 0x1D5F30)]

for off, old, new in diffs:
    rs = off - 0x0A3168 if off >= 0x0A3168 and off < 0x1A3008 else -1
    if rs >= 0:
        rec = rs // 132
        byte_in_rec = rs % 132
        print(f"  0x{off:06X} (rec {rec} byte +{byte_in_rec}): 0x{old:02X} -> 0x{new:02X}")
    elif any(s <= off < e for s, e in crc_regions):
        print(f"  0x{off:06X} (CRC region): 0x{old:02X} -> 0x{new:02X}")
    else:
        print(f"  0x{off:06X}: 0x{old:02X} -> 0x{new:02X}")

# Verify CRC computation
def crc32_be_table():
    poly = 0x04C11DB7
    table = []
    for i in range(256):
        crc = i << 24
        for _ in range(8):
            crc = (crc << 1) ^ poly if crc & 0x80000000 else crc << 1
        table.append(crc & 0xFFFFFFFF)
    return table

def crc32_be(data):
    table = crc32_be_table()
    crc = 0xFFFFFFFF
    for b in data:
        crc = ((crc << 8) ^ table[((crc >> 24) ^ b) & 0xFF]) & 0xFFFFFFFF
    return crc ^ 0xFFFFFFFF

def stored_crc(data):
    return (~crc32_be(data)) & 0xFFFFFFFF

def read_u32(d, o): return struct.unpack(">I", d[o:o+4])[0]

table_count = read_u32(noedit, 16)
TABLE_DATA_START = 24 + table_count * 8

entries = []
for i in range(table_count):
    off = 24 + i * 8
    tid = noedit[off:off+4].decode("ascii", errors="replace")
    data_off = read_u32(noedit, off + 4)
    entries.append((tid, TABLE_DATA_START + data_off))

cpbu = next(info for tid, info in entries if tid == "cPbu")
rbqq = next(info for tid, info in entries if tid == "RBQQ")
ulge = next(info for tid, info in entries if tid == "ulGe")
cabz = next(info for tid, info in entries if tid == "caBZ")

# CRC_A: RBQQ.prior (cPbu header end -> RBQQ info)
print(f"\n=== CRC VERIFICATION ===")
gap_a = noedit[cpbu+40:rbqq]
print(f"CRC_A gap: [0x{cpbu+40:X}, 0x{rbqq:X}) = {len(gap_a)} bytes")
our_a = stored_crc(gap_a)
ms_a = read_u32(noedit, 0x1A4838)
print(f"  No-edit:  our=0x{our_a:08X}  ms=0x{ms_a:08X}  {'OK' if our_a==ms_a else 'MISMATCH'}")

gap_a2 = matt_ana[cpbu+40:rbqq]
our_a2 = stored_crc(gap_a2)
ms_a2 = read_u32(matt_ana, 0x1A4838)
print(f"  Matt_ana: our=0x{our_a2:08X}  ms=0x{ms_a2:08X}  {'OK' if our_a2==ms_a2 else 'MISMATCH'}")

# CRC_C: caBZ.prior (ulGe header end -> caBZ info)
gap_c = noedit[ulge+40:cabz]
our_c = stored_crc(gap_c)
ms_c = read_u32(noedit, 0x1D5F2C)
print(f"CRC_C gap: [0x{ulge+40:X}, 0x{cabz:X}) = {len(gap_c)} bytes")
print(f"  No-edit:  our=0x{our_c:08X}  ms=0x{ms_c:08X}  {'OK' if our_c==ms_c else 'MISMATCH'}")

gap_c2 = matt_ana[ulge+40:cabz]
our_c2 = stored_crc(gap_c2)
ms_c2 = read_u32(matt_ana, 0x1D5F2C)
print(f"  Matt_ana: our=0x{our_c2:08X}  ms=0x{ms_c2:08X}  {'OK' if our_c2==ms_c2 else 'MISMATCH'}")

# Check if any bytes in ulGe->caBZ gap changed
print(f"\n=== ulGe->caBZ GAP DIFFS ===")
for off, old, new in diffs:
    if ulge+40 <= off < cabz:
        print(f"  0x{off:06X}: 0x{old:02X} -> 0x{new:02X}")

# What is at 0x1AE750? Find which table's gap it's in
print(f"\n=== 0x1AE750 LOCATION ===")
for i, (tid, info) in enumerate(entries):
    rec_len = read_u32(noedit, info + 8)
    cur_recs = struct.unpack(">H", noedit[info+18:info+20])[0]
    num_fields = noedit[info + 20]
    rec_start = info + 40 + num_fields * 16
    rec_end = rec_start + cur_recs * rec_len
    if rec_start <= 0x1AE750 < rec_end:
        print(f"  In '{tid}' table, records region")
    elif i > 0 and entries[i-1][1] + 40 <= 0x1AE750 < info:
        prev_tid = [t for t, ii in entries if ii == entries[i-1][1]][0]
        print(f"  In '{prev_tid}'->'{tid}' gap @ offset 0x{0x1AE750 - (entries[i-1][1]+40):X}")

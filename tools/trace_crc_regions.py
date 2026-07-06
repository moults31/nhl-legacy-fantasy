#!/usr/bin/env python3
"""Trace exactly which TDB gaps MS edits touch, and what covers each CRC."""
import zlib, struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5_raw = zlib.decompress(f.read()[48:])

with open(os.path.join(SRC, "default_ms_noedit.db"), "rb") as f:
    ms_noedit = f.read()

with open(os.path.join(SRC, "default_ms_crsb_col.db"), "rb") as f:
    ms_crsb = f.read()

def read_u32_be(data, off):
    return struct.unpack(">I", data[off:off+4])[0]

table_count = read_u32_be(t5_raw, 16)
TABLE_DATA_START = 24 + table_count * 8
TABLE_INFO_SIZE = 40
FIELD_DESC_SIZE = 16

# Parse directory
entries = []
for i in range(table_count):
    off = 24 + i * 8
    tid = t5_raw[off:off+4].decode("ascii", errors="replace")
    data_off = read_u32_be(t5_raw, off + 4)
    entries.append((tid, data_off))

def table_bounds(tid_name):
    """Return (info_off, records_start, records_end) for a table."""
    for i, (tid, data_off) in enumerate(entries):
        if tid == tid_name:
            info_off = TABLE_DATA_START + data_off
            rec_len = read_u32_be(t5_raw, info_off + 8)
            cur = struct.unpack(">H", t5_raw[info_off+18:info_off+20])[0]
            num_fields = t5_raw[info_off + 20]
            rec_start = info_off + TABLE_INFO_SIZE + num_fields * FIELD_DESC_SIZE
            rec_end = rec_start + cur * rec_len
            return info_off, rec_start, rec_end
    return None

# Key tables
cpbu = table_bounds("cPbu")
rbqq = table_bounds("RBQQ")
ulge = table_bounds("ulGe")
cabz = table_bounds("caBZ")

print("=== TABLE BOUNDARIES ===")
for name, bounds in [("cPbu", cpbu), ("RBQQ", rbqq), ("ulGe", ulge), ("caBZ", cabz)]:
    if bounds:
        info, rs, re = bounds
        gap_after = None
        for i, (tid, _) in enumerate(entries):
            if tid == name and i + 1 < len(entries):
                next_info = TABLE_DATA_START + entries[i+1][1]
                gap_after = (re, next_info, next_info - re)
                break
        print(f"  {name}: info=0x{info:06X} records=[0x{rs:06X}, 0x{re:06X}) size={re-rs}")
        if gap_after:
            print(f"         gap after: [0x{gap_after[0]:06X}, 0x{gap_after[1]:06X}) size={gap_after[2]}")

print("\n=== NORMALIZATION BYTES BY REGION ===")
NORM_BYTES = [
    (0x0CACAE, "Hedman team_alt"),
    (0x0CAD1B, "Hedman proteam"),
    (0x1B97D1, "edit-log zero 1"),
    (0x1B97D2, "edit-log zero 2"),
    (0x1B97EC, "edit-log restore"),
    (0x1B97F1, "edit-log marker 1"),
    (0x1B97F2, "edit-log marker 2"),
    (0x1B97F4, "edit-log team byte"),
    (0x1AB24B, "CRC counter"),
]

EDIT_BYTES_CRSB = [
    (0x0B949B, "Crosby proteam"),
    (0x0B942E, "Crosby team_alt"),
    (0x1B97E1, "edit-log zero old 1"),
    (0x1B97E2, "edit-log zero old 2"),
    (0x1B97FC, "edit-log team-1"),
    (0x1B9801, "edit-log prefix"),
    (0x1B9802, "edit-log marker"),
    (0x1B9804, "edit-log team*19"),
    (0x1B9805, "edit-log constant"),
]

for off, desc in NORM_BYTES + EDIT_BYTES_CRSB:
    region = "???"
    if cpbu and cpbu[1] <= off < cpbu[2]:
        region = f"cPbu record {(off - cpbu[1]) // 132}"
    elif rbqq:
        if rbqq[0] <= off < rbqq[2]:
            region = "RBQQ table"
        elif cpbu and cpbu[2] <= off < rbqq[0]:
            region = f"cPbu->RBQQ gap (off={off-cpbu[2]})"
    if ulge:
        if ulge[0] <= off < ulge[2]:
            region = f"ulGe table (off={off-ulge[0]})"
        elif rbqq and rbqq[2] <= off < ulge[0]:
            region = f"RBQQ->ulGe gap"
    if cabz:
        if cabz[0] <= off < cabz[2]:
            region = f"caBZ table"
        elif ulge and ulge[2] <= off < cabz[0]:
            region = f"ulGe->caBZ gap (off={off-ulge[2]})"
    print(f"  0x{off:06X} ({desc}): {region}")

# Now: check if MS changes ANY bytes in the ulGe->caBZ gap that we missed
print("\n=== MS NO-EDIT: unexpected changes in ulGe->caBZ gap ===")
if ulge and cabz:
    gap_start = ulge[2]
    gap_end = cabz[0]
    for off in range(gap_start, gap_end):
        if t5_raw[off] != ms_noedit[off]:
            print(f"  0x{off:06X}: raw=0x{t5_raw[off]:02X} ms=0x{ms_noedit[off]:02X}")

# And check the ulGe table info region for MS changes
print("\n=== MS NO-EDIT: changes in ulGe table header region ===")
if ulge:
    info_start = ulge[0]
    for off in range(info_start, info_start + 40):
        if t5_raw[off] != ms_noedit[off]:
            desc = ""
            if off == info_start: desc = "prior_crc"
            elif off == info_start + 36: desc = "header_crc"
            print(f"  0x{off:06X} (ulGe+{off-info_start} {desc}): raw=0x{t5_raw[off]:02X} ms=0x{ms_noedit[off]:02X}")

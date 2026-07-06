#!/usr/bin/env python3
"""Compare MS-edited DB vs raw-byte-edit DB to find all MS-specific changes."""
import struct, zlib as zl

BIN = "_local/game-saves/xbox"

# Load MS-edited DB1 vs TRADEEDIT5 with raw equivalent edits
with open(f"{BIN}/ms_crsbcol_ovicgy.db", "rb") as f:
    ms1 = f.read()
with open(f"{BIN}/ms_crsbcgy_ovicol.db", "rb") as f:
    ms2 = f.read()
with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5_db = zl.decompress(f.read()[48:])

# MS1: Crosby->COL (0x40), Ovechkin->CGY (0x28)
raw1 = bytearray(t5_db)
raw1[0x0B949B] = 0x40
raw1[0x0B9837] = 0x28
raw1 = bytes(raw1)

# MS2: Crosby->CGY (0x28), Ovechkin->COL (0x40)
raw2 = bytearray(t5_db)
raw2[0x0B949B] = 0x28
raw2[0x0B9837] = 0x40
raw2 = bytes(raw2)

for label, ms, raw in [("MS1", ms1, raw1), ("MS2", ms2, raw2)]:
    assert len(ms) == len(raw)
    diffs = [(i, ms[i], raw[i]) for i in range(len(ms)) if ms[i] != raw[i]]
    crc_ms = struct.unpack("<I", ms[0x14:0x18])[0]
    crc_raw = struct.unpack("<I", raw[0x14:0x18])[0]
    print(f"{label}: {len(diffs)} diffs (TDB CRC: MS=0x{crc_ms:08X} raw=0x{crc_raw:08X})")
    for off, mv, rv in diffs:
        print(f"  0x{off:06X}: MS=0x{mv:02X} raw=0x{rv:02X}")

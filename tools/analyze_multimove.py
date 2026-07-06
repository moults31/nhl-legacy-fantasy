#!/usr/bin/env python3
"""Analyze multi-move MS saves to understand edit-log slotting."""
import zlib, struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5 = zlib.decompress(f.read()[48:])

files = [
    ("no-edit", "default_ms_noedit.db"),
    ("Crosby->COL", "default_ms_crsb_col.db"),
    ("Ovechkin->COL", "default_ms_ovi_col.db"),
    ("Crosby->CGY", "default_ms_crsb_cgy.db"),
    ("Ovechkin->CGY", "default_ms_ovi_cgy.db"),
    ("C->COL O->CGY", "default_crsb_col_ovi_cgy.db"),
    ("C->CGY O->COL", "default_crsb_cgy_ovi_col.db"),
]

dbs = {}
for label, fname in files:
    with open(os.path.join(SRC, fname), "rb") as f:
        dbs[label] = f.read()

print("=== EDIT-LOG REGION (0x1B97D0-0x1B9820) ===")
for label, _ in files:
    db = dbs[label]
    print(f"\n{label}:")
    print(f"  CRC counter @0x1AB24B: 0x{db[0x1AB24B]:02X}")
    for base in [0x1B97D0, 0x1B97E0, 0x1B97F0, 0x1B9800, 0x1B9810]:
        chunk = db[base:base+0x10]
        if any(b != 0 for b in chunk):
            team = db[base] + 1
            marker = (db[base+5] << 8) | db[base+6]
            print(f"  Slot @ {hex(base)}: team={team} marker=0x{marker:04X} raw={chunk.hex(' ')}")

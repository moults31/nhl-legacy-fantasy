#!/usr/bin/env python3
"""Verify all test .bin files decompress correctly."""
import zlib as zl
import sys

names = ['T0_CLEAN', 'T1_CRSB', 'T1_OV', 'T2_CRSBOV', 'T3_ALL']
all_ok = True

for name in names:
    with open(f'_local/game-saves/xbox/{name}.bin', 'rb') as f:
        hdr = f.read(48)
        raw = f.read()
    db = zl.decompress(raw)
    magic = db[:4]
    c = db[0x0B949B]
    o = db[0x0B9837]
    h = db[0x0CAD1B]
    ok = magic == b'KJDH'
    if not ok:
        all_ok = False
    print(f'{name}: magic={magic.hex()} C=0x{c:02X} O=0x{o:02X} H=0x{h:02X} size={len(db)} {"OK" if ok else "FAIL"}')

sys.exit(0 if all_ok else 1)

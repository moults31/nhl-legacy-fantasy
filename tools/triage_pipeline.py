#!/usr/bin/env python3
"""Test: does re-encoding the ORIGINAL backup save work better than MS-edited DB?"""
import struct, zlib as zl

BACKUP = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511\ROSTER 20260307213511"

with open(BACKUP, "rb") as f:
    orig = f.read()

orig_db = zl.decompress(orig[48:])
print(f"Original DB: {len(orig_db)} bytes")

# Apply ONE edit: Crosby to COL
db = bytearray(orig_db)
db[0x0B949B] = 0x40
with open("_local/game-saves/xbox/triage_orig_crsb.db", "wb") as f:
    f.write(db)
print(f"Wrote triage_orig_crsb.db: Crosby proteam=0x{db[0x0B949B]:02X}")

# Also: check if the original DB and MS DB have the same field_0x2c
orig_f2c = struct.unpack(">I", orig[0x2c:0x30])[0]
print(f"Original field_0x2c: 0x{orig_f2c:08X}")

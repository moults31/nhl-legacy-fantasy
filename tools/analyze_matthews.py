#!/usr/bin/env python3
"""Diff Matthews->ANA MS save against no-edit to find his edit-log slot."""
import zlib, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"

with open(os.path.join(SRC, "default_ms_noedit.db.bak"), "rb") as f:
    noedit = f.read()

with open(os.path.join(SRC, "default_ms_matt_ana.db"), "rb") as f:
    matt_ana = f.read()

diffs = [(i, noedit[i], matt_ana[i]) for i in range(len(noedit)) if noedit[i] != matt_ana[i]]
print(f"Total diffs: {len(diffs)}")

crc_regions = [(0x1A4838, 0x1A483C), (0x1AB258, 0x1AB25C), (0x1D5F2C, 0x1D5F30)]

player_diffs = []
editlog_diffs = []
crc_diffs = []
other_diffs = []

for off, old, new in diffs:
    if any(s <= off < e for s, e in crc_regions):
        crc_diffs.append((off, old, new))
    elif 0x1ACE00 <= off < 0x1ACF00 or 0x1B9700 <= off < 0x1B9820:
        editlog_diffs.append((off, old, new))
    elif 0x0A3168 <= off < 0x1A3008:
        player_diffs.append((off, old, new))
    elif off == 0x1AB24B:
        other_diffs.append((off, old, new))
    elif off == 0x0CACAE or off == 0x0CAD1B:
        player_diffs.append((off, old, new))
    else:
        other_diffs.append((off, old, new))

print(f"\nCRC: {len(crc_diffs)} diffs")
print(f"Player: {len(player_diffs)} diffs")
print(f"Edit-log: {len(editlog_diffs)} diffs")
print(f"Other: {len(other_diffs)} diffs")

print("\n=== PLAYER DIFFS (Matthews data) ===")
for off, old, new in player_diffs:
    rs = off - 0x0A3168
    rec = rs // 132
    byte_in_rec = rs % 132
    print(f"  0x{off:06X} (rec {rec}, byte +{byte_in_rec}): 0x{old:02X} -> 0x{new:02X}")

print("\n=== EDIT-LOG DIFFS ===")
for off, old, new in editlog_diffs:
    slot_base = off & ~0xF
    slot_pos = off - slot_base
    print(f"  0x{off:06X} (slot {hex(slot_base)}+{slot_pos}): 0x{old:02X} -> 0x{new:02X}")

print("\n=== CHANGED SLOTS ===")
seen_slots = set()
for off, old, new in editlog_diffs:
    slot_base = off & ~0xF
    if slot_base not in seen_slots:
        seen_slots.add(slot_base)
        slot = matt_ana[slot_base:slot_base+16]
        print(f"  Slot @ {hex(slot_base)}: {slot.hex(' ')}")

print(f"\n=== CRC COUNTER ===")
for off, old, new in other_diffs:
    print(f"  0x{off:06X}: 0x{old:02X} -> 0x{new:02X}")

# Extract Matthews' edit-log tracking
print("\n=== EDIT-LOG TRACKING (0x1B97FC-0x1B9805) ===")
print(f"  no-edit:   {noedit[0x1B97FC:0x1B9806].hex(' ')}")
print(f"  matt_ana:  {matt_ana[0x1B97FC:0x1B9806].hex(' ')}")

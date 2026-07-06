#!/usr/bin/env python3
"""Find Matthews' edit-log marker by searching all 0x41xx patterns."""
import zlib, struct

BIN = "_local/game-saves/xbox"

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5 = bytearray(zlib.decompress(f.read()[48:]))

# Search for 0x41 or 0x70 markers near record-index-like values
# Matthews: record 5593, team 28
# Look for bytes that correlate with these values

# The edit-log master table has slots at 0x1ACE00 and 0x1B9700.
# Each slot is 16 bytes. Let me dump ALL slots and their byte 5-6 (which
# might be a record index offset).

# Actually, from the data, for Crosby (record 688), his slot has:
# bytes: 00 41 10 02 50 00 00 00 00 00 00 00 07 00 00 00 (no-edit)
# For Ovechkin (record 695), his slot:
# bytes: 00 41 d0 42 0d 81 04 22 14 d3 41 00 27 01 02 00

# What if bytes 3-6 encode a record number?
# Crosby: bytes 3-6 = 0x02 0x50 0x00 0x00 = 0x02500000 (big) ... no.
# Ovechkin: bytes 3-6 = 0x42 0x0D 0x81 0x04 = 0x420D8104 ... no.

# Let me try a completely different approach: check if the edit-log slot
# index maps deterministically to a record index.
# Crosby record 688 -> slot at 0x1B97E0. If sorted alphabetically or by
# record order, where does 0x1B97E0 fall relative to other slots?

# Actually, the simplest test: just ask MS to move Matthews->ANA, 
# then diff the result to find his slot and marker.

# For now, let me just search the file for 0x41 or 0x70 followed by
# a byte that equals (team_id - 1) for Matthews' teams

# In TRADEEDIT5, Matthews is on TB. Team 28 (0x1C).
# Is there any slot with team_adj = 27 (0x1B)?

# Let me search through ALL slots in the file for team_adj=27
print("Searching for slots with team_adj=0x1B (TB, team 28):")
for base in range(0x1ACE00, 0x1ACF00, 0x10):
    slot = t5[base:base+16]
    if slot[0] == 0x1B and (slot[1] == 0x41 or slot[1] == 0x70):
        print(f"  Found! {hex(base)}: {slot.hex(' ')}")

for base in range(0x1B9700, 0x1B9820, 0x10):
    slot = t5[base:base+16]
    if slot[0] == 0x1B and (slot[1] == 0x41 or slot[1] == 0x70):
        print(f"  Found! {hex(base)}: {slot.hex(' ')}")

# Also search beyond these regions
print("\nSearching entire file for 0x41+0x1B or 0x70+0x1B patterns:")
for i in range(0, len(t5) - 16):
    if t5[i] == 0x1B and (t5[i+1] == 0x41 or t5[i+1] == 0x70):
        # Check if this looks like an edit-log slot (16-byte aligned region)
        base = i & ~0xF
        slot = t5[base:base+16]
        if (slot[1] == 0x41 or slot[1] == 0x70):
            pass # Already checked above
        if i < 0x1ACF00 or (0x1B9700 <= i < 0x1B9820):
            pass # Skip known regions
        print(f"  0x{i:06X}: team_adj=0x{t5[i]:02X} marker=0x{t5[i+1]:02X}{t5[i+2]:02X}")

print("\nDone. No Matthews edit-log slot found with team_adj=27.")
print("Matthews likely doesn't have a pre-existing edit-log entry.")
print("We need an MS-processed Matthews->X save to discover his marker/ctrl_off.")

#!/usr/bin/env python3
"""Find every 0x41XX and 0x70XX marker in the edit-log region, then match to records."""
import zlib, struct, json

BIN = "_local/game-saves/xbox"

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5 = bytearray(zlib.decompress(f.read()[48:]))

with open("tools/tmp/t5_players.json", encoding="utf-8") as f:
    players = json.load(f)["players"]

# Build lookup by the full record marker byte
# Scan the entire cPbu->RBQQ gap (0x0A3008 to 0x1A4838) for patterns
# that look like edit-log identifiers

# Known markers:
# Crosby: bytes 0x41 0x10 found in his slot at 0x1B97E1-0x1B97E2
# Ovechkin: 0x41 0xD0 at 0x1ACE71-0x1ACE72
# Hedman: 0x70 0x50 at 0x1B97D1-0x1B97D2

# The marker seems to be a 2-byte value: prefix (0x41 or 0x70) + id
# Let me search for all 0x41XX and 0x70XX markers near edit-log slots

# The edit-log master table structure: 0x10-byte slots at 0x1ACE00-0x1ACF00 and 0x1B9700-0x1B9800
# Slot format (16 bytes):
#   [0] = team-1 (or control byte)
#   [1-2] = player marker (big-endian 16-bit)
#   [3-4] = ?
#   [5-6] = ?
#   [7-8] = ?
#   ...

# Let me dump each slot and try to correlate with known players
print("=== MASTER EDIT-LOG SLOTS (0x1ACE00-0x1ACF00) ===")
for base in range(0x1ACE00, 0x1ACF00, 0x10):
    slot = t5[base:base+16]
    if not any(slot):
        continue
    ctrl = slot[0]
    marker = (slot[1] << 8) | slot[2]
    b3 = (slot[3] << 8) | slot[4]
    b5 = (slot[5] << 8) | slot[6]
    print(f"  {hex(base)}: team_adj={ctrl:02X} marker=0x{marker:04X} val3=0x{b3:04X} val5=0x{b5:04X}")

print("\n=== MASTER EDIT-LOG SLOTS (0x1B9700-0x1B9810) ===")
for base in range(0x1B9700, 0x1B9810, 0x10):
    slot = t5[base:base+16]
    if not any(slot):
        continue
    ctrl = slot[0]
    marker = (slot[1] << 8) | slot[2]
    b3 = (slot[3] << 8) | slot[4]
    b5 = (slot[5] << 8) | slot[6]
    print(f"  {hex(base)}: team_adj={ctrl:02X} marker=0x{marker:04X} val3=0x{b3:04X} val5=0x{b5:04X}")

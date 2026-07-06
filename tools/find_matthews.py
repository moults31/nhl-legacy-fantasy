#!/usr/bin/env python3
"""Find player record indices and tracking bytes."""
import json, zlib

# Load export
with open("tools/tmp/t5_players.json", encoding="utf-8") as f:
    data = json.load(f)

# Find Matthews
for p in data["players"]:
    if "MATTHEWS" in p["last_name"].upper() and p["first_name"].upper() == "AUSTON":
        print(f"Matthews: record={p['record']} first={p['first_name']} last={p['last_name']} team={p['proteam']}")

# Find some other notable players to add
targets = [
    ("CONNOR", "MCDAVID"),
    ("NATHAN", "MACKINNON"),
    ("LEON", "DRAISAITL"),
    ("DAVID", "PASTRNAK"),
    ("NIKITA", "KUCHEROV"),
]
for first, last in targets:
    for p in data["players"]:
        if p["first_name"].upper() == first and p["last_name"].upper() == last:
            print(f"{first} {last}: record={p['record']} team={p['proteam']}")

# Now find tracking bytes. Load TRADEEDIT5 and look at ctrl_off regions
with open("_local/game-saves/xbox/TRADEEDIT5", "rb") as f:
    t5 = zlib.decompress(f.read()[48:])

# For Matthews, find the byte at ctrl_off = 0x1ACE71 + (rec - 688)*0x10 offset pattern
# Actually, the ctrl_off comes from the player's record. Let me find the pattern.
# From the known players:
# Crosby rec=688, ctrl_off=0x1B97E1, marker=0x10
# Ovechkin rec=695, ctrl_off=0x1ACE71, marker=0xD0
# Hedman rec=1232, ctrl_off=0x1B97D1, marker=0x50

# These don't follow a simple formula. Let me look at the region to understand the structure.
# The ctrl_off region at 0x1ACE71 and 0x1B97D1 seem like fixed edit-log slots.

# For a new player like Matthews, we need to discover their ctrl_off and marker.
# Let me search for patterns in the edit-log region
# The edit data for each player appears to be stored in a table-like structure
# Let me search for Matthews' current team tracking

# Matthews team in TRADEEDIT5 = ?
matthews = [p for p in data["players"] if p["first_name"].upper() == "AUSTON" and p["last_name"].upper() == "MATTHEWS"][0]
print(f"\nMatthews: record={matthews['record']}, current team={matthews['proteam']}")

# The ctrl_off and marker are specific to the edit-log table structure.
# We need MS output for a Matthews move to discover these.
# But we can try to reverse-engineer the table.

# The edit-log appears to have entries for each movable player. Let me dump
# the area around known entries to find the pattern.
print("\nEdit-log region dump (0x1ACE60-0x1ACE90, 0x1B97C0-0x1B9820):")
print("Ovechkin ctrl area (0x1ACE71):")
print(f"  {t5[0x1ACE60:0x1ACE90].hex(' ')}")
print("\nHedman/Crosby ctrl area (0x1B97D0):")
print(f"  {t5[0x1B97C0:0x1B9820].hex(' ')}")

# The pattern: each player gets a 0x10-byte entry in an edit-log table
# Entry format seems to be:
# byte 0: team_id - 1
# byte 1: 0x41 (constant prefix)
# byte 2-3: player marker (uint16 big-endian)
# byte 4: team_id * 19
# byte 5: 0x80 (constant)

# For Crosby: marker 0x10 at 0x1B97E2 (byte 2)
# For Ovechkin: marker 0xD0 at 0x1ACE72

# Let me dump ALL non-zero entries in the 0x1ACE00-0x1ACEFF range
print("\nEntries in 0x1ACE00-0x1ACEFF:")
for base in range(0x1ACE00, 0x1ACF00, 0x10):
    if any(t5[base+i] != 0 for i in range(16)):
        marker = (t5[base+2] << 8) | t5[base+3]
        print(f"  {hex(base)}: team_adj={t5[base]:02X} marker=0x{marker:04X} full={t5[base:base+16].hex(' ')}")

# And the 0x1B9700-0x1B9800 range  
print("\nEntries in 0x1B9700-0x1B9800:")
for base in range(0x1B9700, 0x1B9801, 0x10):
    if any(t5[base+i] != 0 for i in range(16)):
        marker = (t5[base+2] << 8) | t5[base+3]
        print(f"  {hex(base)}: team_adj={t5[base]:02X} marker=0x{marker:04X} full={t5[base:base+16].hex(' ')}")

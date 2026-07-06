"""Verify: the 3 saved bytes come from byte 118 of player's cPbu record."""
import struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
with open(os.path.join(SRC, 'default_orig.db'), 'rb') as f:
    orig = f.read()

BASE = 0x0A3168
PLAYERS = [
    ("McDavid", 3498, "LAK", "01 12 10"),
    ("Draisaitl", 3436, "LAK", "01 0e 20"),
    ("Matthews", 5593, "CBJ", "01 9b 90"),
]

for name, rec, target, expected_hex in PLAYERS:
    RS = BASE + rec * 132
    byte118 = orig[RS+118:RS+121]
    byte118_hex = byte118.hex(' ')
    match = "MATCH" if byte118_hex == expected_hex else "DIFF"
    print(f"{name} (rec {rec}): byte 118-120 = [{byte118_hex}]  expected [{expected_hex}]  {match}")

# Also check: does ANY eGlu record have the same bytes at +4 to +6?
ULGE = 0x1AB73C
for name, rec, target, expected_hex in PLAYERS:
    RS = BASE + rec * 132
    byte118 = orig[RS+118:RS+121]
    byte118_hex = byte118.hex(' ')
    
    found_in_eglu = False
    for off in range(ULGE, min(ULGE + 3600 * 16, len(orig)), 16):
        if off + 7 > len(orig): break
        if orig[off+4:off+7] == byte118:
            rec_idx = (off - ULGE) // 16
            print(f"  {name}'s bytes [{byte118_hex}] FOUND at eGlu rec {rec_idx}")
            found_in_eglu = True
            break
    if not found_in_eglu:
        print(f"  {name}'s bytes [{byte118_hex}] NOT in eGlu")

# Check: for McDavid->CBJ, verify eGlu rec 2788 bytes match McDavid's cPbu byte118
off2788 = ULGE + 2788 * 16
print(f"\neGlu rec 2788 bytes 4-6: [{orig[off2788+4:off2788+7].hex(' ')}]")
# And McDavid rec 3498 byte118
RS3498 = BASE + 3498 * 132
print(f"McDavid rec 3498 byte 118-120: [{orig[RS3498+118:RS3498+121].hex(' ')}]")
print(f"Same? {orig[off2788+4:off2788+7] == orig[RS3498+118:RS3498+121]}")

# Also check: what field is at byte 118 in cPbu?
# Record size = 132 bytes. Let me look at byte range 114-124 for a known player
print(f"\nMcDavid bytes 114-124: {orig[RS3498+114:RS3498+125].hex(' ')}")
print(f"  +114..+115: team-related?")
print(f"  +115: proteam slot (0x{(orig[RS3498+115]>>3)&0x1f:02x})")  
print(f"  +116..+117: unknown")
print(f"  +118..+120: tracking id [{orig[RS3498+118:RS3498+121].hex(' ')}]")
print(f"  +121..+124: unknown")

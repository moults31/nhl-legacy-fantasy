
"""Find player 6670 and analyze ctrl_off relationship."""
import csv

path = r'C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511\default_orig.csv'

with open(path, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Find ubPc table
ubPc_start = None
for i, line in enumerate(lines):
    if line.strip() == 'ubPc':
        ubPc_start = i
        break

ubPc_fields = lines[ubPc_start+1].strip().split(',')
pid_idx = ubPc_fields.index('wBIz')
first_idx = ubPc_fields.index('HdeP')
last_idx = ubPc_fields.index('QbMR')
team_idx = ubPc_fields.index('dXSB')

data_start = ubPc_start + 3

# Build player ID -> info map for quick lookup
player_map = {}
for i in range(data_start, len(lines)):
    line = lines[i].strip()
    if not line:
        break
    vals = line.split(',')
    if len(vals) > pid_idx:
        pid = vals[pid_idx]
        if pid:
            player_map[pid] = {
                'rec': i - data_start,
                'first': vals[first_idx] if first_idx < len(vals) else '?',
                'last': vals[last_idx] if last_idx < len(vals) else '?',
                'team': vals[team_idx] if team_idx < len(vals) else '?',
            }

# Find player 6670
if '6670' in player_map:
    p = player_map['6670']
    print(f"Player ID 6670: {p['first']} {p['last']}, Team={p['team']}")

# Find what Matthews looks like (record 5592)
if '13516' in player_map:
    p = player_map['13516']
    print(f"Player ID 13516 (Matthews): {p['first']} {p['last']}, Team={p['team']}, Record={p['rec']}")

# Now the key question: how does ctrl_off relate to Player ID?
# Known: Crosby(3109) -> ctrl_off=0x1B97E1, marker=0x10
# Known: Ovechkin(3116) -> ctrl_off=0x1ACE71, marker=0xD0
# Known: Hedman(4664) -> ctrl_off=0x1B97D1, marker=0x50

# ctrl_off values are in the edit-log region:
# 0x1B97D1, 0x1B97E1 are 16 bytes apart (same table gap)
# 0x1ACE71 is different

# Let me look at what's at 0x1ACE71:
# That's in the ulGe table data region (0x1AB73C to 0x1B97EC)
# ulGe record starts at 0x1AB73C, each record is 16 bytes
# Offset 0x1ACE71 - 0x1AB73C = 0x1735 = 5941
# 5941 / 16 = 371.3125... not aligned to record boundary
# 5941 % 16 = 5. So it's byte 5 of record 371 in ulGe

# For Crosby: ctrl_off=0x1B97E1 is in the edit-log gap
# For Hedman: ctrl_off=0x1B97D1 is also in the edit-log gap
# For Ovechkin: ctrl_off=0x1ACE71 is in ulGe record 371

# This is confusing because the ctrl_off values seem inconsistent.

# Actually, let me check: in TRADEEDIT5, what are the bytes at these offsets?
# I should look at the raw binary rather than the CSV

# For now, let me calculate the eGlu record for user-visible info
# Find eGlu table
eGlu_start = None
for i, line in enumerate(lines):
    if line.strip() == 'eGlu':
        eGlu_start = i
        break

eGlu_fields = lines[eGlu_start+1].strip().split(',')
eglu_xswt_idx = eGlu_fields.index('XSWT')
eglu_team_idx = eGlu_fields.index('dXSB')
eglu_svrt_idx = eGlu_fields.index('sVRt')
eglu_data = eGlu_start + 3

# Find all eGlu records with known player IDs
eglu_map = {}
for i in range(eglu_data, len(lines)):
    line = lines[i].strip()
    if not line or (len(line) == 4 and line.isascii() and line.isalpha()):
        break
    vals = line.split(',')
    if len(vals) > eglu_xswt_idx:
        pid = vals[eglu_xswt_idx]
        if pid and pid != '0':
            eglu_map[pid] = {
                'rec': i - eglu_data,
                'team': vals[eglu_team_idx] if eglu_team_idx < len(vals) else '?',
                'jersey': vals[eglu_svrt_idx] if eglu_svrt_idx < len(vals) else '?',
            }

# Cross-ref Crosby, Ovechkin
for pid, label in [('3109', 'Crosby'), ('3116', 'Ovechkin'), ('4664', 'Hedman'), ('13516', 'Matthews')]:
    if pid in eglu_map:
        e = eglu_map[pid]
        print(f"{label} (PID {pid}): in eGlu rec {e['rec']}, team={e['team']}, jersey={e['jersey']}")
    else:
        print(f"{label} (PID {pid}): NOT in eGlu")

# Let's also see if ctrl_off correlates with eGlu record * 16 + eGlu_base
# eGlu records start at TDB offset 0x1AB73C
# eGlu record N = TDB offset 0x1AB73C + N*16
# For Crosby: need to figure out ctrl_off - is it eGlu_record*16 + base?
# 0x1B97D1 - 0x1AB73C = 0xE095 = 57493 decimal, not near any record multiple of 16

# Wait, these offsets (0x1B97D1, 0x1B97E1) are in the PADDING region after ulGe,
# not in the ulGe records themselves. So they're in a DIFFERENT data structure
# that uses 16-byte slots for trade/edit tracking.

# The edit-log slots seem to map to player record positions, where:
# Slot 0 (0x1B97D1): Hedman  
# Slot 1 (0x1B97E1): Crosby
# These slots PRE-EXIST in TRADEEDIT5 and reference specific players

# For NEW players (like Matthews), there's no pre-existing edit-log slot.
# That's why we couldn't move Matthews - we need to know how to CREATE a new slot.

# But wait, Ovechkin's ctrl_off=0x1ACE71 is in the ulGe records, not the edit-log gap.
# Maybe this means Ovechkin's edit-log slot is referenced differently.

# Let me check: what player has PID=6670? That's the one at eGlu record 769
if '6670' in player_map:
    p = player_map['6670']
    print(f"\neGlu record 769 player: PID=6670, {p['first']} {p['last']}, Team={p['team']}")

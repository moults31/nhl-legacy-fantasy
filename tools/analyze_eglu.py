
"""Find Matthews in Rosters and Lines (eGlu) table."""
import csv, os

path = r'C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511\default_orig.csv'

with open(path, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Find eGlu table (line 24159)
eGlu_start = None
for i, line in enumerate(lines):
    if line.strip() == 'eGlu':
        eGlu_start = i
        break

if eGlu_start is None:
    print("eGlu not found")
    exit()

print(f"eGlu starts at line {eGlu_start+1}")

# Fields from header
eGlu_fields = lines[eGlu_start+1].strip().split(',')
team_idx = eGlu_fields.index('dXSB')
xswt_idx = eGlu_fields.index('XSWT')  # Player ID
svrt_idx = eGlu_fields.index('sVRt')  # Jersey
pos_idx = eGlu_fields.index('PKtc') if 'PKtc' in eGlu_fields else 8

# Data rows
data_start = eGlu_start + 3
n_records = 0

# Find Matthews by Player ID 13516
target_pid = '13516'
for i in range(data_start, len(lines)):
    line = lines[i].strip()
    if not line or (len(line) == 4 and line.isascii() and line.isalpha() and i > data_start + 2):
        break
    n_records += 1
    vals = line.split(',')
    if len(vals) <= xswt_idx:
        continue
    if vals[xswt_idx] == target_pid:
        rec = n_records - 1
        print(f"\nMatthews found at eGlu record {rec} (line {i+1}):")
        print(f"  Team (dXSB) = {vals[team_idx]}")
        print(f"  Player ID (XSWT) = {vals[xswt_idx]}")
        print(f"  Jersey (sVRt) = {vals[svrt_idx]}")
        for fi, fn in enumerate(eGlu_fields):
            if fi < len(vals) and vals[fi] not in ('', '0'):
                print(f"    {fn} = {vals[fi]}")

# Also find the record that was zeroed (rec 769)
print(f"\nRecord 769 for context (the one that got zeroed in MS output):")
rec_769_line = data_start + 769
if rec_769_line < len(lines):
    vals_769 = lines[rec_769_line].strip().split(',')
    print(f"  Team (dXSB) = {vals_769[team_idx]}")
    print(f"  Player ID (XSWT) = {vals_769[xswt_idx]}")
    print(f"  Jersey (sVRt) = {vals_769[svrt_idx]}")

# Now find Crosby (Player ID 3109) and Ovechkin (3116) in eGlu
for target, pid, name in [('3109', 'Crosby', 'PIT'), ('3116', 'Ovechkin', 'WSH'), ('4664', 'Hedman', 'TBL')]:
    for i in range(data_start, len(lines)):
        line = lines[i].strip()
        if not line or (len(line) == 4 and line.isascii() and line.isalpha() and i > data_start + 2):
            break
        vals = line.split(',')
        if len(vals) <= xswt_idx:
            continue
        if vals[xswt_idx] == target:
            rec = i - data_start
            print(f"\n{name} found at eGlu record {rec}: Team={vals[team_idx]}, PID={vals[xswt_idx]}, Jersey={vals[svrt_idx]}")
            break

print(f"\nTotal eGlu records: {n_records}")

# Now look at the edit-log bytes. In the binary TDB the edit log is at 0x1B97D8-0x1B9808
# Each entry has: [4 bytes ctrl_off?][4 bytes marker?][4 bytes team?][4 bytes something?]
# Let me look up what XSWT (Player ID) values correspond to our known ctrl_off values:
# Crosby: ctrl_off=0x0E(=14), marker=0x30(=48)
# Ovechkin: ctrl_off=0x30(=48), marker=0x80(=128)
# Hedman: ctrl_off=0xB8(=184), marker=0x30(=48)

# Hypothesis: ctrl_off is a byte offset within the eGlu records region
# Let me calculate: eGlu starts at TDB offset 0x1AB73C, record size = 16 bytes
# Record 0 = 0x1AB73C
# Record 14 = 0x1AB73C + 14*16 = 0x1AB73C + 0xE0 = 0x1AB81C
# Record 48 = 0x1AB73C + 48*16 = 0x1AB73C + 0x300 = 0x1ABA3C
# Record 184 = 0x1AB73C + 184*16 = 0x1AB73C + 0xB80 = 0x1AC2BC

# Let's check what's at those eGlu records:
for ctrl_off, label in [(14, 'Crosby'), (48, 'Ovechkin'), (184, 'Hedman')]:
    rec_line = data_start + ctrl_off
    if rec_line < len(lines):
        vals = lines[rec_line].strip().split(',')
        if len(vals) > xswt_idx:
            print(f"\n  eGlu rec {ctrl_off} ({label} ctrl_off): dXSB={vals[team_idx]}, XSWT={vals[xswt_idx]}, sVRt={vals[svrt_idx]}")
            if vals[xswt_idx] in ('3109', '3116', '4664', '13516'):
                print(f"    *** MATCH! This is {label}'s roster entry")

# Also check what the Player ID field tells us about the edit-log
# Maybe the edit-log uses Player ID directly, not record offset...
# Let's map: 
# Crosby PID=3109 → ctrl_off=14 → marker=48
# Ovechkin PID=3116 → ctrl_off=48 → marker=128
# Hedman PID=4664 → ctrl_off=184 → marker=48
# We need: Matthews PID=13516 → what ctrl_off and marker?

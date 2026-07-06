
"""Find what player ID 6670 is, and analyze edit-log structure."""
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

# Find player 6670
target = '6670'
for i in range(data_start, len(lines)):
    line = lines[i].strip()
    if not line:
        break
    vals = line.split(',')
    if len(vals) <= pid_idx:
        continue
    if vals[pid_idx] == target:
        print(f"Player ID {target}: {vals[first_idx]} {vals[last_idx]}, Team={vals[team_idx]}")
        break

# Now look at eGlu table and find all entries with Team=8 (Columbus)
# to understand record 769 in context
eGlu_start = None
for i, line in enumerate(lines):
    if line.strip() == 'eGlu':
        eGlu_start = i
        break

eGlu_fields = lines[eGlu_start+1].strip().split(',')
eglu_team_idx = eGlu_fields.index('dXSB')
eglu_xswt_idx = eGlu_fields.index('XSWT')
eglu_svrt_idx = eGlu_fields.index('sVRt')

eGlu_data = eGlu_start + 3
n_cols = 0
for i in range(eGlu_data, len(lines)):
    line = lines[i].strip()
    if not line or (len(line) == 4 and line.isascii() and line.isalpha()):
        break
    n_cols += 1
    vals = line.split(',')
    if len(vals) > eglu_team_idx and vals[eglu_team_idx] == '8':
        rec = n_cols - 1
        pid = vals[eglu_xswt_idx] if eglu_xswt_idx < len(vals) else '?'
        svrt = vals[eglu_svrt_idx] if eglu_svrt_idx < len(vals) else '?'
        marker = '*' if rec == 769 else ''
        print(f"eGlu record {rec}: Team=8, PID={pid}, Jersey={svrt} {marker}")

# Also verify the relationship between dXSB in eGlu and ubPc
# For eGlu records, find which ubPc player matches
print(f"\n--- Cross-referencing eGlu Team=8 records with ubPc ---")
for i in range(eGlu_data, len(lines)):
    line = lines[i].strip()
    if not line or (len(line) == 4 and line.isascii() and line.isalpha()):
        break
    vals = line.split(',')
    if len(vals) > eglu_team_idx and vals[eglu_team_idx] == '8':
        pid = vals[eglu_xswt_idx]
        # Search ubPc for this player ID
        for j in range(data_start, len(lines)):
            uvals = lines[j].strip().split(',')
            if not lines[j].strip():
                break
            if len(uvals) > pid_idx and uvals[pid_idx] == pid:
                print(f"  eGlu PID {pid} → {uvals[first_idx]} {uvals[last_idx]} (ubPc team={uvals[team_idx]})")
                break

print(f"\nTotal eGlu Columbus entries: {n_cols}")

# Let's figure out ctrl_off for Matthews
# In TRADEEDIT5, we have known players with ctrl_off values
# Let me look at what byte offset in the TDB corresponds to the record
# where Matthews' data is stored

# The edit-log bytes for Crosby: 0x1B97E1, marker=0x10
# In the CSV, Crosby is ubPc record 687, wBIz=3109
# In eGlu: Crosby XSWT=3109? Let me check

# Actually, XSWT in eGlu is the Player ID. Let me find what eGlu record has XSWT=3109
for i in range(eGlu_data, len(lines)):
    line = lines[i].strip()
    if not line:
        break
    vals = line.split(',')
    if len(vals) > eglu_xswt_idx and vals[eglu_xswt_idx] == '3109':
        rec = i - eGlu_data
        print(f"\nCrosby (3109) in eGlu: record {rec}, team={vals[eglu_team_idx]}, jersey={vals[eglu_svrt_idx]}")
        break
else:
    print("\nCrosby (3109) NOT found in eGlu!")

for i in range(eGlu_data, len(lines)):
    line = lines[i].strip()
    if not line:
        break
    vals = line.split(',')
    if len(vals) > eglu_xswt_idx and vals[eglu_xswt_idx] == '3116':
        rec = i - eGlu_data
        print(f"Ovechkin (3116) in eGlu: record {rec}, team={vals[eglu_team_idx]}, jersey={vals[eglu_svrt_idx]}")
        break
else:
    print("Ovechkin (3116) NOT found in eGlu!")

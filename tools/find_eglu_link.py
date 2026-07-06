"""Find Draisaitl's eGlu record via Player ID (XSWT)."""
import os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
csv_path = os.path.join(SRC, "default_orig.csv")
with open(csv_path, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Find eGlu
eglu_start = next(i for i, l in enumerate(lines) if l.strip() == 'eGlu')
eglu_fields = lines[eglu_start+1].strip().split(',')
xswt_idx = eglu_fields.index('XSWT')
dsxb_idx = eglu_fields.index('dXSB')
svrt_idx = eglu_fields.index('sVRt')
eglu_data = eglu_start + 3

# Search eGlu for Draisaitl (PID=10543), McDavid (10647), Matthews (13516)
targets = {'10543': 'Draisaitl', '10647': 'McDavid', '13516': 'Matthews'}
records_by_pid = {}
for i in range(eglu_data, len(lines)):
    line = lines[i].strip()
    if not line or (len(line) == 4 and line.isascii() and line.isalpha()):
        break
    vals = line.split(',')
    if len(vals) > xswt_idx and vals[xswt_idx]:
        records_by_pid[vals[xswt_idx]] = i - eglu_data

for pid, name in targets.items():
    if pid in records_by_pid:
        rec = records_by_pid[pid]
        # Get full record from CSV
        rec_line = eglu_data + rec
        vals = lines[rec_line].strip().split(',')
        print(f"{name} (PID={pid}): eGlu rec {rec}, team={vals[dsxb_idx]}, jersey={vals[svrt_idx]}")
    else:
        print(f"{name} (PID={pid}): NOT in eGlu")

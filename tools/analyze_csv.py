
"""Analyze default_orig.csv for player movement insights."""
import csv, sys, os

path = r'C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511\default_orig.csv'

with open(path, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

print(f"Loaded {len(lines)} lines")

# Find all table boundaries
tables = []
for i, line in enumerate(lines):
    s = line.strip()
    if len(s) == 4 and s.isascii() and s.isalpha():
        if i+1 < len(lines) and ',' in lines[i+1]:
            tables.append((i, s, lines[i+1].strip()))

print(f"Found {len(tables)} tables:")
for idx, (start, name, header) in enumerate(tables):
    nf = len(header.split(','))
    print(f"  {idx:2d} @ L{start+1:6d} {name:6s} ({nf} fields)")

# ── Player Bios (ubPc) ──
ubPc_idx = None
for idx, (start, name, header) in enumerate(tables):
    if name == 'ubPc':
        ubPc_idx = idx
        break

if ubPc_idx is None:
    print("ERROR: ubPc not found")
    sys.exit(1)

ubPc_start, ubPc_name, ubPc_header = tables[ubPc_idx]
ubPc_fields = ubPc_header.split(',')
first_idx = ubPc_fields.index('HdeP')  # First Name
last_idx = ubPc_fields.index('QbMR')   # Last Name
team_idx = ubPc_fields.index('dXSB')   # Team ID
pid_idx = ubPc_fields.index('wBIz')    # Player ID
pos_idx = ubPc_fields.index('vjla')    # Position
active_idx = ubPc_fields.index('kKYN') # Active
year_idx = ubPc_fields.index('JKLp')   # Birth month
month_idx = ubPc_fields.index('Kswi')  # Birth day
day_idx = ubPc_fields.index('ggdf') if 'ggdf' in ubPc_fields else None

print(f"\n--- Player Bios (ubPc) fields ---")
print(f"  First Name: HdeP[{first_idx}]")
print(f"  Last Name:  QbMR[{last_idx}]")
print(f"  Team ID:    dXSB[{team_idx}]")
print(f"  Player ID:  wBIz[{pid_idx}]")
print(f"  Position:   vjla[{pos_idx}]")
print(f"  Active:     kKYN[{active_idx}]")

# Search for specific players
target_players = ['Matthews', 'Crosby', 'Ovechkin', 'Hedman', 'McDavid']

data_start = ubPc_start + 3  # skip table name, header, separator
n_records = 0
for i in range(data_start, len(lines)):
    line = lines[i].strip()
    if not line:
        break
    n_records += 1
    vals = line.split(',')
    if len(vals) <= max(first_idx, last_idx):
        continue
    last = vals[last_idx] if last_idx < len(vals) else ''
    first = vals[first_idx] if first_idx < len(vals) else ''
    for tp in target_players:
        if tp.lower() in last.lower() or tp.lower() in first.lower():
            rec = n_records - 1
            print(f"\n  Record {rec}: {first} {last}")
            print(f"    Team ID (dXSB)  = {vals[team_idx]}")
            print(f"    Player ID (wBIz) = {vals[pid_idx]}")
            print(f"    Position (vjla)  = {vals[pos_idx]}")
            print(f"    Active (kKYN)    = {vals[active_idx]}")
            if month_idx < len(vals): print(f"    Birth month (JKLp) = {vals[month_idx]}")
            if day_idx and day_idx < len(vals): print(f"    Birth day (Kswi) = {vals[day_idx]}")
            if year_idx < len(vals): print(f"    Birth year? (qFnd) = {vals[year_idx]}")
            # Print all fields
            for fi, fn in enumerate(ubPc_fields):
                if fi < len(vals) and vals[fi] not in ('', '0'):
                    print(f"    {fn} = {vals[fi]}")
            break

print(f"\nTotal player records in ubPc: {n_records}")

# ── Rosters And Lines (eGlu) ──
eGlu_idx = None
for idx, (start, name, header) in enumerate(tables):
    if name == 'eGlu':
        eGlu_idx = idx
        break

if eGlu_idx:
    eGlu_start, eGlu_name, eGlu_header = tables[eGlu_idx]
    eGlu_fields = eGlu_header.split(',')
    eGlu_team_idx = eGlu_fields.index('dXSB')
    eGlu_xswt_idx = eGlu_fields.index('XSWT')  # TWSX
    eGlu_svrt_idx = eGlu_fields.index('sVRt')    # Jersey number
    eGlu_jyk_idx = eGlu_fields.index('JykA') if 'JykA' in eGlu_fields else None
    
    print(f"\n--- Rosters And Lines (eGlu) fields ---")
    print(f"  Team ID:   dXSB[{eGlu_team_idx}]")
    print(f"  XSWT:      [{eGlu_xswt_idx}]")
    print(f"  Jersey#:   sVRt[{eGlu_svrt_idx}]")
    
    # Look for record 769 (the 0x1AE750 record)
    eGlu_data_start = eGlu_start + 3
    eGlu_line_769 = eGlu_data_start + 769
    if eGlu_line_769 < len(lines):
        vals_769 = lines[eGlu_line_769].strip().split(',')
        print(f"\n  Record 769 (0x1AE750 in TDB):")
        print(f"    Team (dXSB) = {vals_769[eGlu_team_idx]}")
        print(f"    XSWT         = {vals_769[eGlu_xswt_idx]}")
        for fi, fn in enumerate(eGlu_fields):
            if fi < len(vals_769) and vals_769[fi] not in ('', '0'):
                print(f"    {fn} = {vals_769[fi]}")

# ── NHL Schedule (QQBR) ──
QQBR_idx = None
for idx, (start, name, header) in enumerate(tables):
    if name == 'QQBR':
        QQBR_idx = idx
        break

if QQBR_idx:
    QQBR_start, QQBR_name, QQBR_header = tables[QQBR_idx]
    QQBR_fields = QQBR_header.split(',')
    print(f"\n--- NHL Schedule (QQBR) fields ---")
    print(f"  {QQBR_fields}")
    
    # Count records
    QQBR_data_start = QQBR_start + 3
    qqbr_count = 0
    for i in range(QQBR_data_start, len(lines)):
        if lines[i].strip() == '' or (len(lines[i].strip()) in (2,3) and lines[i].strip().isalpha()):
            break
        qqbr_count += 1
    print(f"  Records: {qqbr_count}")

# ── Key unknown regions ──
# Look at what's between ulGe (eGlu) and caBZ
print("\n--- Tables between eGlu and the end ---")
eGlu_idx_for_end = None
for idx, (start, name, header) in enumerate(tables):
    if name == 'eGlu':
        eGlu_idx_for_end = idx
        break
if eGlu_idx_for_end is not None:
    for idx in range(eGlu_idx_for_end, min(eGlu_idx_for_end + 10, len(tables))):
        start, name, header = tables[idx]
        print(f"  [{idx}] {name} @ L{start+1}")

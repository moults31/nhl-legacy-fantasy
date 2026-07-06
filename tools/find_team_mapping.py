"""Find correct eGlu team index mapping by looking at actual ANA/LAK players."""
import struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
csv_path = os.path.join(SRC, "default_orig.csv")

with open(csv_path, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Find ubPc
ubPc_start = next(i for i, l in enumerate(lines) if l.strip() == 'ubPc')
ubPc_fields = lines[ubPc_start+1].strip().split(',')
pid_idx = ubPc_fields.index('wBIz')
first_idx = ubPc_fields.index('HdeP')
last_idx = ubPc_fields.index('QbMR')
team_idx = ubPc_fields.index('dXSB')

# Find eGlu
eglu_start = next(i for i, l in enumerate(lines) if l.strip() == 'eGlu')
eglu_fields = lines[eglu_start+1].strip().split(',')
eglu_team_idx = eglu_fields.index('dXSB')
eglu_xswt_idx = eglu_fields.index('XSWT')
eglu_data = eglu_start + 3

# For each team we care about, find a well-known player on that team and check their eGlu team index
# Known players and their expected teams (1-indexed):
known = [
    ('Ryan', 'Getzlaf', 'ANA', 1),     # should be on ANA  
    ('Corey', 'Perry', 'ANA', 1),      # should be on ANA
    ('Anze', 'Kopitar', 'LAK', 14),    # should be on LAK
    ('Drew', 'Doughty', 'LAK', 14),    # should be on LAK
    ('Connor', 'McDavid', 'EDM', 12),  # on EDM
    ('Sidney', 'Crosby', 'PIT', 24),   # on PIT
]

# Build player lookup from ubPc
ubPc_data_start = ubPc_start + 3
ubPc_players = {}
for i in range(ubPc_data_start, len(lines)):
    line = lines[i].strip()
    if not line:
        break
    vals = line.split(',')
    if len(vals) > pid_idx and vals[pid_idx]:
        ubPc_players[vals[pid_idx]] = {
            'first': vals[first_idx] if first_idx < len(vals) else '',
            'last': vals[last_idx] if last_idx < len(vals) else '',
            'team': vals[team_idx] if team_idx < len(vals) else '',
        }

# Build eGlu lookup: player ID -> eGlu team
eglu_by_pid = {}
eglu_count = 0
for i in range(eglu_data, len(lines)):
    line = lines[i].strip()
    if not line or (len(line) == 4 and line.isascii() and line.isalpha()):
        break
    eglu_count += 1
    vals = line.split(',')
    if len(vals) > eglu_xswt_idx and vals[eglu_xswt_idx]:
        eglu_by_pid[vals[eglu_xswt_idx]] = {
            'rec': i - eglu_data,
            'team': vals[eglu_team_idx] if eglu_team_idx < len(vals) else '',
        }

print(f"ubPc players: {len(ubPc_players)}")
print(f"eGlu records: {eglu_count}")

# For each known player, find what eGlu team they're on
print("\nKnown player -> eGlu team mapping:")
for first, last, team_name, expected_1idx in known:
    # Find PID for this player
    found_pid = None
    for pid, info in ubPc_players.items():
        if info['first'] == first and info['last'] == last:
            found_pid = pid
            break
    
    if found_pid:
        ubPc_team = ubPc_players[found_pid]['team']
        if found_pid in eglu_by_pid:
            eglu_team = eglu_by_pid[found_pid]['team']
            eglu_rec = eglu_by_pid[found_pid]['rec']
            print(f"  {first} {last}: PID={found_pid}, ubPc.team={ubPc_team}, eGlu.team={eglu_team} (rec {eglu_rec})  expected={expected_1idx}")
        else:
            print(f"  {first} {last}: PID={found_pid}, ubPc.team={ubPc_team}, NOT in eGlu")
    else:
        print(f"  {first} {last}: NOT FOUND in ubPc")

# Now: find all eGlu records with the correct team index for ANA and LAK
print("\n\neGlu records by team index:")
for team_val in ['1', '14', '8', '0']:
    count = 0
    last_rec = None
    for i in range(eglu_data, len(lines)):
        line = lines[i].strip()
        if not line or (len(line) == 4 and line.isascii() and line.isalpha()):
            break
        vals = line.split(',')
        if len(vals) > eglu_team_idx and vals[eglu_team_idx] == team_val:
            rec = i - eglu_data
            last_rec = rec
            count += 1
    print(f"  team={team_val}: {count} records, last @ rec {last_rec}")

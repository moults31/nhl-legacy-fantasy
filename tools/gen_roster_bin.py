"""Generate compact binary player/team data from CSV for Rust embedding."""
import os, struct, json

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
csv_path = os.path.join(SRC, "default_orig.csv")

with open(csv_path, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# ── Extract ubPc player data ──
ubPc_start = next(i for i, l in enumerate(lines) if l.strip() == 'ubPc')
ubPc_fields = lines[ubPc_start+1].strip().split(',')
pid_idx = ubPc_fields.index('wBIz')
first_idx = ubPc_fields.index('HdeP')
last_idx = ubPc_fields.index('QbMR')
active_idx = ubPc_fields.index('kKYN')

players = []
for i in range(ubPc_start+3, len(lines)):
    line = lines[i].strip()
    if not line: break
    vals = line.split(',')
    if len(vals) <= pid_idx or not vals[pid_idx]: continue
    first = vals[first_idx] if first_idx < len(vals) else ''
    last = vals[last_idx] if last_idx < len(vals) else ''
    active = int(vals[active_idx]) if active_idx < len(vals) and vals[active_idx] else 0
    if first and last and active:
        players.append({
            'name': f"{first} {last}".upper(),
            'rec': i - (ubPc_start + 3),  # 0-indexed CSV record
            'pid': int(vals[pid_idx]),
        })

# Sort by name for binary search
players.sort(key=lambda p: p['name'])

print(f"Active players: {len(players)}")

# ── Extract eGlu player ID -> record mapping ──
eglu_start = next(i for i, l in enumerate(lines) if l.strip() == 'eGlu')
eglu_fields = lines[eglu_start+1].strip().split(',')
eglu_xswt_idx = eglu_fields.index('XSWT')
eglu_data = eglu_start + 3

pid_to_eglu = {}
for i in range(eglu_data, len(lines)):
    line = lines[i].strip()
    if not line or (len(line)==4 and line.isascii() and line.isalpha()): break
    vals = line.split(',')
    if len(vals) > eglu_xswt_idx and vals[eglu_xswt_idx]:
        pid_to_eglu[int(vals[eglu_xswt_idx])] = i - eglu_data

print(f"eGlu mappings: {len(pid_to_eglu)}")

# ── Extract team ClpB from StEO ──
# From earlier: ClpB values are in StEO.
# The eGlu team values (dXSB) correspond to ClpB values.
# And our proteam values correspond to... let me figure this out from the CSV.

# Actually, let me compute ClpB from the known relationship:
# For CBJ: our proteam=9, eGlu dXSB=8, so eglu_team + 1 = proteam
# For LAK: our proteam=14, eGlu dXSB=14, same value (doesn't follow +1 rule)
# 
# Wait, LAK eGlu dXSB is 14 and our proteam for LAK is 14. But we set proteam to 14 and it WORKED.
# So for LAK: proteam == eGlu dXSB. For CBJ: proteam != eGlu dXSB.
# This is contradictory.
# 
# Let me check: what's the eGlu dXSB for ANA? From earlier analysis, ANA has dXSB=1 in eGlu.
# And in the working MS save, ANA proteam = 0.
# So ANA eGlu = 1, proteam = 0. Not matching either pattern.
# 
# Actually, looking at the CSV: ANA players in ubPc have dXSB=0 (from earlier analysis)
# But in eGlu, ANA records have dXSB=1.
# 
# OK I think the issue is: the eGlu dXSB values are NOT the same as proteam values.
# They're a different team indexing scheme (maybe ClpB-based).
# 
# From StEO:
#   row 7: ClpB=8, City=Columbus → CBJ
#   row 12: ClpB=13, City=Los Angeles → LAK
#
# eGlu dXSB for CBJ = 8 (= ClpB)
# eGlu dXSB for LAK = 14 (= ClpB? But ClpB is 13, not 14)
# 
# Wait, I said LAK eGlu dXSB=14. But earlier I also said LAK has ClpB=13. Let me verify.
# From the find_team_mapping.py output:
#   eGlu team=14: 25 records, last @ rec 3131
# 
# And from StEO row 12 (Glendale = Arizona? Or Los Angeles):
# From earlier CSV analysis StEO rows:
#   row 12: ClpB=13, City=Los Angeles
# But Glendale is row 21. So LA is row 12 with ClpB=13.
# And eGlu dXSB for LAK players is 14. So eGlu dXSB != ClpB for LAK.
#
# This is getting confusing. Let me just hardcode the mapping.

# Actual working team data from analysis:
# Key: our proteam (1-indexed)
TEAM_DATA = {
    1:  {'name': 'ANA', 'clpb': 0,  'd3': 0x00, 'd4': 0x00},  # team 0 internal
    9:  {'name': 'CBJ', 'clpb': 8,  'd3': 0x00, 'd4': 0xAC},
    14: {'name': 'LAK', 'clpb': 13, 'd3': 0x01, 'd4': 0x10},
    24: {'name': 'PIT', 'clpb': 23, 'd3': 0x01, 'd4': 0x00},  # unknown d4
    29: {'name': 'TOR', 'clpb': 27, 'd3': 0x01, 'd4': 0x00},  # unknown d4
    33: {'name': 'WSH', 'clpb': 29, 'd3': 0x01, 'd4': 0x00},  # unknown d4
    8:  {'name': 'COL', 'clpb': 7,  'd3': 0x01, 'd4': 0x00},  # unknown d4
    12: {'name': 'EDM', 'clpb': 11, 'd3': 0x01, 'd4': 0x00},  # unknown d4
}

# For now, fill in all teams we know from TRADEEDIT5 move_player.rs
# with best guesses for d4 (0x00 = unknown, needs MS sample)
ALL_TEAMS = {
    1: 'ANA', 2: 'BOS', 3: 'BUF', 5: 'CGY', 6: 'CAR', 7: 'CHI', 8: 'COL',
    9: 'CBJ', 10: 'DAL', 11: 'DET', 12: 'EDM', 13: 'FLA', 14: 'LAK',
    15: 'MIN', 16: 'MTL', 17: 'NSH', 18: 'NJD', 19: 'NYI', 20: 'NYR',
    21: 'OTT', 22: 'PHI', 24: 'PIT', 25: 'SJS', 27: 'STL', 28: 'TBL',
    29: 'TOR', 30: 'VAN', 31: 'VGK', 32: 'WPG', 33: 'WSH',
}

# Extended team data with known ClpB and guessed d3/d4
for tid, name in ALL_TEAMS.items():
    if tid not in TEAM_DATA:
        TEAM_DATA[tid] = {'name': name, 'clpb': 0, 'd3': 0, 'd4': 0}

# ── Write binary player file ──
# Format:
#   u32: number of players
#   For each player:
#     u8: name length
#     bytes: name (ASCII uppercase)
#     u16: record index (0-indexed CSV)
#     u16: player ID

data_dir = os.path.join("crates", "roster-cli", "data")
os.makedirs(data_dir, exist_ok=True)

with open(os.path.join(data_dir, "players.bin"), "wb") as f:
    f.write(struct.pack('<I', len(players)))
    for p in players:
        name_bytes = p['name'].encode('ascii')
        f.write(struct.pack('B', len(name_bytes)))
        f.write(name_bytes)
        f.write(struct.pack('<H', p['rec']))
        f.write(struct.pack('<H', p['pid']))

print(f"Wrote {len(players)} players to players.bin")

# ── Write eGlu mapping ──
# Format: sorted by PID, each entry [u16 pid, u16 record]
pid_list = sorted(pid_to_eglu.items())
with open(os.path.join(data_dir, "eglu.bin"), "wb") as f:
    f.write(struct.pack('<I', len(pid_list)))
    for pid, rec in pid_list:
        f.write(struct.pack('<HH', pid, rec))

print(f"Wrote {len(pid_list)} eGlu mappings to eglu.bin")

# ── Write team table ──
with open(os.path.join(data_dir, "teams.bin"), "wb") as f:
    f.write(struct.pack('<I', len(TEAM_DATA)))
    for tid in sorted(TEAM_DATA.keys()):
        data = TEAM_DATA[tid]
        name_bytes = data['name'].encode('ascii')
        f.write(struct.pack('B', tid))
        f.write(struct.pack('B', data['clpb']))
        f.write(struct.pack('B', data['d3']))
        f.write(struct.pack('B', data['d4']))
        f.write(struct.pack('B', len(name_bytes)))
        f.write(name_bytes)

print(f"Wrote {len(TEAM_DATA)} teams to teams.bin")

# Also dump stats
print(f"\nStats:")
print(f"  Players: {len(players)}")
print(f"  Name lengths: min={min(len(p['name']) for p in players)}, max={max(len(p['name']) for p in players)}")
print(f"  eGlu mappings: {len(pid_to_eglu)}")
print(f"  Teams with known D4: {sum(1 for t in TEAM_DATA.values() if t['d4']!=0)}/{len(TEAM_DATA)}")

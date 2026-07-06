"""Extract player and team data from default_orig.csv into Rust source."""
import os, csv, json

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
csv_path = os.path.join(SRC, "default_orig.csv")

with open(csv_path, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Find ubPc table
ubPc_start = next(i for i, l in enumerate(lines) if l.strip() == 'ubPc')
ubPc_fields = lines[ubPc_start+1].strip().split(',')
pid_idx = ubPc_fields.index('wBIz')
first_idx = ubPc_fields.index('HdeP')
last_idx = ubPc_fields.index('QbMR')
team_idx = ubPc_fields.index('dXSB')
active_idx = ubPc_fields.index('kKYN')

# Extract all active players with valid names
players = []
for i in range(ubPc_start+3, len(lines)):
    line = lines[i].strip()
    if not line:
        break
    vals = line.split(',')
    if len(vals) <= pid_idx: continue
    if not vals[pid_idx]: continue
    first = vals[first_idx] if first_idx < len(vals) else ''
    last = vals[last_idx] if last_idx < len(vals) else ''
    team = vals[team_idx] if team_idx < len(vals) else '0'
    active = vals[active_idx] if active_idx < len(vals) else '0'
    if first and last:
        players.append({
            'rec': i - (ubPc_start + 3),
            'pid': int(vals[pid_idx]),
            'first': first,
            'last': last,
            'team': int(team),
            'active': int(active),
        })

print(f"Extracted {len(players)} players from ubPc")

# Find eGlu table
eglu_start = next(i for i, l in enumerate(lines) if l.strip() == 'eGlu')
eglu_fields = lines[eglu_start+1].strip().split(',')
eglu_xswt_idx = eglu_fields.index('XSWT')
eglu_team_idx = eglu_fields.index('dXSB')
eglu_data = eglu_start + 3

# Map player ID -> eGlu record
pid_to_eglu = {}
for i in range(eglu_data, len(lines)):
    line = lines[i].strip()
    if not line or (len(line) == 4 and line.isascii() and line.isalpha()):
        break
    vals = line.split(',')
    if len(vals) > eglu_xswt_idx and vals[eglu_xswt_idx]:
        pid = vals[eglu_xswt_idx]
        eglu_rec = i - eglu_data
        pid_to_eglu[pid] = eglu_rec

print(f"eGlu: {len(pid_to_eglu)} player-to-record mappings")

# Find StEO table for ClpB values
steo_start = next(i for i, l in enumerate(lines) if l.strip() == 'StEO')
steo_fields = lines[steo_start+1].strip().split(',')
clpb_idx = steo_fields.index('ClpB')
city_idx = steo_fields.index('bhQD')
steo_data = steo_start + 3

# Read StEO rows for ClpB map (row index -> ClpB)
clpb_by_row = {}
for i in range(steo_data, min(steo_data + 100, len(lines))):
    line = lines[i].strip()
    if not line or (len(line) == 4 and line.isascii() and line.isalpha()):
        break
    vals = line.split(',')
    if len(vals) > clpb_idx and vals[clpb_idx]:
        row = i - steo_data
        clpb = int(vals[clpb_idx])
        city = vals[city_idx] if city_idx < len(vals) else ''
        clpb_by_row[row] = {'clpb': clpb, 'city': city}

# Now build the TEAM_TABLE: our 1-indexed team_id -> StEO row, ClpB, D3, D4
# Our team mapping (from move_player.rs):
TEAM_NAMES = {
    1: 'ANA', 2: 'BOS', 3: 'BUF', 5: 'CGY', 6: 'CAR', 7: 'CHI', 8: 'COL',
    9: 'CBJ', 10: 'DAL', 11: 'DET', 12: 'EDM', 13: 'FLA', 14: 'LAK',
    15: 'MIN', 16: 'MTL', 17: 'NSH', 18: 'NJD', 19: 'NYI', 20: 'NYR',
    21: 'OTT', 22: 'PHI', 24: 'PIT', 25: 'SJS', 27: 'STL', 28: 'TBL',
    29: 'TOR', 30: 'VAN', 31: 'VGK', 32: 'WPG', 33: 'WSH',
}

# Map eGlu team value (dXSB) to our team ID
# From earlier analysis:
# CBJ: dXSB=8, our team=9 → eglu_team + 1 = our team
# LAK: dXSB=14, our team=14 → match. But CBJ doesn't match.
# So eGlu team = ClpB value!
# CBJ ClpB=8, eGlu dXSB=8. Match.
# LAK: would need to find ClpB for LAK

# Actually, let me just find the ClpB for each team by scanning StEO
# and also figure out which eGlu dXSB values correspond to which teams

# First, find ClpB for each team from StEO
team_clpb = {}
for row, info in clpb_by_row.items():
    clpb = info['clpb']
    city = info['city'].upper()
    # Match city to team name
    for tid, tname in TEAM_NAMES.items():
        if tname in city[:10] or city[:10] in tname:
            team_clpb[tid] = clpb
            break

print("\nTeam -> ClpB:")
for tid in sorted(TEAM_NAMES.keys()):
    clpb = team_clpb.get(tid, '?')
    print(f"  {TEAM_NAMES[tid]:>4} (t={tid:2d}): ClpB={clpb}")

# Also map ClpB -> team_id
clpb_to_team = {v: k for k, v in team_clpb.items()}

# Known D4 values
D4_TABLE = {
    9: 0xAC,   # CBJ
    14: 0x10,  # LAK
}

# D3 = ClpB & 1
def compute_d3d4(tid):
    clpb = team_clpb.get(tid)
    if clpb is None:
        return (0, 0)
    d3 = clpb & 1
    d4 = D4_TABLE.get(tid, 0)
    return (d3, d4)

print("\nFull team table:")
print(f"{'Name':>4} {'TID':>3} {'ClpB':>4} {'D3':>4} {'D4':>6} {'CC':>4}")
for tid in sorted(TEAM_NAMES.keys()):
    name = TEAM_NAMES[tid]
    clpb = team_clpb.get(tid, 0)
    d3, d4 = compute_d3d4(tid)
    cc = tid - 1  # CC = team_id - 1
    print(f"{name:>4} {tid:>3} {clpb:>4} {d3:>4} 0x{d4:02x}   {cc:>4}")

# Generate Rust source
rust_lines = []
rust_lines.append("// Auto-generated roster data from default_orig.csv.")
rust_lines.append("// Maps player name -> record index, PID -> eGlu record, and team metadata.")
rust_lines.append("")
rust_lines.append("use std::collections::HashMap;")
rust_lines.append("")

# Player lookup: (first_name, last_name) -> record index
rust_lines.append("/// Map player (first_name, last_name) to cPbu record index (0-indexed CSV).")
rust_lines.append("pub fn player_records() -> HashMap<(&'static str, &'static str), usize> {")
rust_lines.append("    let mut m = HashMap::new();")
count = 0
for p in players:
    if p['active'] == 0:  # only include active players
        continue
    # Escape single quotes in names
    first = p['first'].replace("'", "''")
    last = p['last'].replace("'", "''")
    rust_lines.append(f"    m.insert((\"{first}\", \"{last}\"), {p['rec']});")
    count += 1
    if count >= 2000:
        rust_lines.append(f"    // ... ({len(players)} total, truncated to 2000)")
        break
rust_lines.append("    m")
rust_lines.append("}")
rust_lines.append("")

# eGlu mapping: player PID -> eGlu record
rust_lines.append("/// Map player PID to eGlu record index (0-based).")
rust_lines.append("pub fn eglu_records() -> HashMap<usize, usize> {")
rust_lines.append("    let mut m = HashMap::new();")
for pid, rec in sorted(pid_to_eglu.items(), key=lambda x: int(x[0]))[:500]:
    rust_lines.append(f"    m.insert({pid}, {rec});")
rust_lines.append("    m")
rust_lines.append("}")
rust_lines.append("")

# Team table
rust_lines.append("/// Team metadata.")
rust_lines.append("pub struct TeamInfo {")
rust_lines.append("    pub name: &'static str,")
rust_lines.append("    pub team_id: usize,  // 1-indexed, matches proteam encoding")
rust_lines.append("    pub clpb: usize,")
rust_lines.append("    pub d3: u8,          // ClpB & 1")
rust_lines.append("    pub d4: u8,          // team-specific edit-log byte")
rust_lines.append("}")
rust_lines.append("")
rust_lines.append("/// All known teams keyed by team_id (1-indexed).")
rust_lines.append("pub fn team_table() -> HashMap<usize, TeamInfo> {")
rust_lines.append("    let mut m = HashMap::new();")
for tid in sorted(TEAM_NAMES.keys()):
    name = TEAM_NAMES[tid]
    clpb = team_clpb.get(tid, 0)
    d3, d4 = compute_d3d4(tid)
    rust_lines.append(f"    m.insert({tid}, TeamInfo {{ name: \"{name}\", team_id: {tid}, clpb: {clpb}, d3: 0x{d3:02x}, d4: 0x{d4:02x} }});")
rust_lines.append("    m")
rust_lines.append("}")
rust_lines.append("")
rust_lines.append("/// Lookup team by name or abbreviation (e.g. \"CBJ\", \"COLUMBUS\").")
rust_lines.append("pub fn find_team(name: &str) -> Option<TeamInfo> {")
rust_lines.append("    let upper = name.to_uppercase();")
rust_lines.append("    for (_id, info) in team_table().iter() {")
rust_lines.append("        if info.name == upper.as_str() || upper.starts_with(info.name) || info.name.starts_with(&upper) {")
rust_lines.append("            return Some(TeamInfo { name: info.name, team_id: info.team_id, clpb: info.clpb, d3: info.d3, d4: info.d4 });")
rust_lines.append("        }")
rust_lines.append("    }")
rust_lines.append("    // Handle common full names")
rust_lines.append("    match upper.as_str() {")
rust_lines.append("        \"ANAHEIM\" => team_table().get(&1).cloned(),")
rust_lines.append("        \"BOSTON\" | \"BRUINS\" => team_table().get(&2).cloned(),")
rust_lines.append("        \"CALGARY\" | \"FLAMES\" => team_table().get(&5).cloned(),")
rust_lines.append("        \"COLORADO\" | \"AVALANCHE\" => team_table().get(&8).cloned(),")
rust_lines.append("        \"COLUMBUS\" | \"BLUE JACKETS\" => team_table().get(&9).cloned(),")
rust_lines.append("        \"EDMONTON\" | \"OILERS\" => team_table().get(&12).cloned(),")
rust_lines.append("        \"LOS ANGELES\" | \"KINGS\" | \"LA\" => team_table().get(&14).cloned(),")
rust_lines.append("        \"PITTSBURGH\" | \"PENGUINS\" => team_table().get(&24).cloned(),")
rust_lines.append("        \"TORONTO\" | \"MAPLE LEAFS\" => team_table().get(&29).cloned(),")
rust_lines.append("        \"TAMPA\" | \"TAMPA BAY\" | \"LIGHTNING\" => team_table().get(&28).cloned(),")
rust_lines.append("        \"WASHINGTON\" | \"CAPITALS\" => team_table().get(&33).cloned(),")
rust_lines.append("        _ => None,")
rust_lines.append("    }")
rust_lines.append("}")

# Write output
out_path = os.path.join("crates", "roster-cli", "src", "roster_db.rs")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w') as f:
    f.write('\n'.join(rust_lines) + '\n')

print(f"\nGenerated {out_path}")
print(f"  Players: {count}")
print(f"  eGlu mappings: {len(pid_to_eglu)}")
print(f"  Teams: {len(TEAM_NAMES)}")

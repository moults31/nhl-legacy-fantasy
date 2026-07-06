"""Generate compact Rust module with player lookup data from CSV."""
import os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
csv_path = os.path.join(SRC, "default_orig.csv")

with open(csv_path, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# ── ubPc ──
ubPc_start = next(i for i, l in enumerate(lines) if l.strip() == 'ubPc')
ubPc_fields = lines[ubPc_start+1].strip().split(',')
pid_idx = ubPc_fields.index('wBIz')
first_idx = ubPc_fields.index('HdeP')
last_idx = ubPc_fields.index('QbMR')
active_idx = ubPc_fields.index('kKYN')

def safe_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0

players = []
for i in range(ubPc_start+3, len(lines)):
    line = lines[i].strip()
    if not line: break
    vals = line.split(',')
    if len(vals) <= pid_idx or not vals[pid_idx]: continue
    pid = safe_int(vals[pid_idx])
    if pid == 0: continue
    first = vals[first_idx] if first_idx < len(vals) else ''
    last = vals[last_idx] if last_idx < len(vals) else ''
    active = safe_int(vals[active_idx]) if active_idx < len(vals) else 0
    if first and last and active:
        # Sanitize non-ASCII characters
        name = f"{first} {last}".upper()
        name = name.encode('ascii', errors='replace').decode('ascii')
        players.append((name, i - (ubPc_start + 3), pid))

players.sort(key=lambda p: p[0])
print(f"Active players: {len(players)}")

# ── eGlu ──
eglu_start = next(i for i, l in enumerate(lines) if l.strip() == 'eGlu')
eglu_fields = lines[eglu_start+1].strip().split(',')
eglu_xswt_idx = eglu_fields.index('XSWT')
eglu_data = eglu_start + 3

eglu_pairs = []
for i in range(eglu_data, len(lines)):
    line = lines[i].strip()
    if not line or (len(line)==4 and line.isascii() and line.isalpha()): break
    vals = line.split(',')
    if len(vals) > eglu_xswt_idx and vals[eglu_xswt_idx]:
        pid = safe_int(vals[eglu_xswt_idx])
        if pid:
            eglu_pairs.append((pid, i - eglu_data))

eglu_pairs.sort()
print(f"eGlu mappings: {len(eglu_pairs)}")

# ── Generate Rust ──
out_path = os.path.join("crates", "roster-cli", "src", "roster_db.rs")
parts = []

parts.append("// Auto-generated from default_orig.csv. Do not edit by hand.")
parts.append("")
parts.append("/// Player entry: (name, CSV record index, player ID). Sorted by name for binary search.")
parts.append(f"pub static PLAYERS: &[(&str, usize, usize)] = &[")
for name, rec, pid in players:
    parts.append(f'    ("{name}", {rec}, {pid}),')
parts.append("];")
parts.append("")
parts.append("/// eGlu mapping: (player ID, eGlu record index). Sorted by PID for binary search.")
parts.append(f"pub static EGLU: &[(usize, usize)] = &[")
for pid, rec in eglu_pairs:
    parts.append(f"    ({pid}, {rec}),")
parts.append("];")
parts.append("")

# Team table
parts.append("/// Team metadata.")
parts.append("pub struct TeamInfo { pub name: &'static str, pub id: u8, pub d3: u8, pub d4: u8 }")
parts.append("")
parts.append("/// Lookup team info by team_id (1-indexed proteam value).")
parts.append("pub fn team_info(tid: u8) -> Option<TeamInfo> {")
parts.append("    match tid {")
team_map = [
    (1, "ANA", 0x00, 0x00),
    (2, "BOS", 0x00, 0x00),
    (3, "BUF", 0x00, 0x00),
    (5, "CGY", 0x00, 0x00),
    (6, "CAR", 0x00, 0x00),
    (7, "CHI", 0x00, 0x00),
    (8, "COL", 0x00, 0x00),
    (9, "CBJ", 0x00, 0xAC),
    (10, "DAL", 0x00, 0x00),
    (11, "DET", 0x00, 0x00),
    (12, "EDM", 0x00, 0x00),
    (13, "FLA", 0x00, 0x00),
    (14, "LAK", 0x01, 0x10),
    (15, "MIN", 0x00, 0x00),
    (16, "MTL", 0x00, 0x00),
    (17, "NSH", 0x00, 0x00),
    (18, "NJD", 0x00, 0x00),
    (19, "NYI", 0x00, 0x00),
    (20, "NYR", 0x00, 0x00),
    (21, "OTT", 0x00, 0x00),
    (22, "PHI", 0x00, 0x00),
    (24, "PIT", 0x00, 0x00),
    (25, "SJS", 0x00, 0x00),
    (27, "STL", 0x00, 0x00),
    (28, "TBL", 0x00, 0x00),
    (29, "TOR", 0x00, 0x00),
    (30, "VAN", 0x00, 0x00),
    (31, "VGK", 0x00, 0x00),
    (32, "WPG", 0x00, 0x00),
    (33, "WSH", 0x00, 0x00),
]
for tid, name, d3, d4 in team_map:
    parts.append(f"        {tid} => Some(TeamInfo {{ name: \"{name}\", id: {tid}, d3: 0x{d3:02x}, d4: 0x{d4:02x} }}),")
parts.append("        _ => None,")
parts.append("    }")
parts.append("}")
parts.append("")
parts.append("/// Lookup team by name or abbreviation.")
parts.append("pub fn find_team(name: &str) -> Option<TeamInfo> {")
parts.append("    let upper = name.to_uppercase();")
parts.append("    for tid in [1u8,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33] {")
parts.append("        if let Some(info) = team_info(tid) {")
parts.append("            if info.name == upper.as_str() { return Some(info); }")
parts.append("        }")
parts.append("    }")
parts.append("    match upper.as_str() {")
parts.append("        \"ANAHEIM\" => team_info(1),")
parts.append("        \"BOSTON\" => team_info(2),")
parts.append("        \"BUFFALO\" => team_info(3),")
parts.append("        \"CALGARY\" => team_info(5),")
parts.append("        \"CAROLINA\" => team_info(6),")
parts.append("        \"CHICAGO\" => team_info(7),")
parts.append("        \"COLORADO\" => team_info(8),")
parts.append("        \"COLUMBUS\" => team_info(9),")
parts.append("        \"DALLAS\" => team_info(10),")
parts.append("        \"DETROIT\" => team_info(11),")
parts.append("        \"EDMONTON\" => team_info(12),")
parts.append("        \"FLORIDA\" => team_info(13),")
parts.append("        \"LA\" | \"LOS ANGELES\" | \"LOSANGELES\" => team_info(14),")
parts.append("        \"MINNESOTA\" => team_info(15),")
parts.append("        \"MONTREAL\" => team_info(16),")
parts.append("        \"NASHVILLE\" => team_info(17),")
parts.append("        \"NEW JERSEY\" | \"NEWJERSEY\" | \"NJ\" => team_info(18),")
parts.append("        \"NY ISLANDERS\" | \"NYISLANDERS\" | \"NYI\" => team_info(19),")
parts.append("        \"NY RANGERS\" | \"NYRANGERS\" | \"NYR\" => team_info(20),")
parts.append("        \"OTTAWA\" => team_info(21),")
parts.append("        \"PHILADELPHIA\" => team_info(22),")
parts.append("        \"PITTSBURGH\" => team_info(24),")
parts.append("        \"SAN JOSE\" | \"SANJOSE\" | \"SJ\" => team_info(25),")
parts.append("        \"ST LOUIS\" | \"STLOUIS\" | \"ST. LOUIS\" | \"ST.LOUIS\" => team_info(27),")
parts.append("        \"TAMPA BAY\" | \"TAMPABAY\" | \"TB\" => team_info(28),")
parts.append("        \"TORONTO\" => team_info(29),")
parts.append("        \"VANCOUVER\" => team_info(30),")
parts.append("        \"VEGAS\" => team_info(31),")
parts.append("        \"WINNIPEG\" => team_info(32),")
parts.append("        \"WASHINGTON\" => team_info(33),")
parts.append("        _ => None,")
parts.append("    }")
parts.append("}")
parts.append("")
parts.append("/// Binary search for a player by full name. Returns (record, pid) if found.")
parts.append("pub fn find_player(name: &str) -> Option<(usize, usize)> {")
parts.append("    let name = name.to_uppercase();")
parts.append("    let idx = PLAYERS.binary_search_by_key(&name.as_str(), |(n, _, _)| n).ok()?;")
parts.append("    Some((PLAYERS[idx].1, PLAYERS[idx].2))")
parts.append("}")
parts.append("")
parts.append("/// Binary search for an eGlu record by player ID.")
parts.append("pub fn find_eglu(pid: usize) -> Option<usize> {")
parts.append("    let idx = EGLU.binary_search_by_key(&pid, |(p, _)| *p).ok()?;")
parts.append("    Some(EGLU[idx].1)")
parts.append("}")

with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(parts) + '\n')

size_kb = len('\n'.join(parts)) / 1024
print(f"Generated {out_path}: {size_kb:.0f} KB")
print(f"  Players: {len(players)}, eGlu: {len(eglu_pairs)}, Teams: {len(team_map)}")

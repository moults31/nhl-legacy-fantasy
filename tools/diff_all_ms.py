"""Diff all 5 MS saves vs default_orig.db to discover the edit-log pattern."""
import struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"

with open(os.path.join(SRC, "default_orig.db"), "rb") as f:
    orig = f.read()

MS_SAVES = [
    "default_orig_matthews_cbj.db",  # Matthews -> CBJ (known working)
    "default_orig_mcd_ana.db",       # McDavid -> ANA
    "default_orig_mcd_lak.db",       # McDavid -> LAK
    "default_orig_drai_ana.db",      # Draisaitl -> ANA
    "default_orig_drai_lak.db",      # Draisaitl -> LAK
    "default_ms_matt_ana.db",        # Matthews -> ANA (old, may be zeroed different)
]

# Read CSV for player lookup
csv_path = os.path.join(SRC, "default_orig.csv")
with open(csv_path, encoding='utf-8', errors='replace') as f:
    csv_lines = f.readlines()

# Find ubPc
ubPc_start = next(i for i, l in enumerate(csv_lines) if l.strip() == 'ubPc')
ubPc_fields = csv_lines[ubPc_start+1].strip().split(',')
pid_idx = ubPc_fields.index('wBIz')
first_idx = ubPc_fields.index('HdeP')
last_idx = ubPc_fields.index('QbMR')

players = {}
for i in range(ubPc_start+3, len(csv_lines)):
    line = csv_lines[i].strip()
    if not line:
        break
    vals = line.split(',')
    if len(vals) > pid_idx and vals[pid_idx]:
        players[vals[pid_idx]] = {
            'csv_rec': i - (ubPc_start + 3),
            'first': vals[first_idx] if first_idx < len(vals) else '',
            'last': vals[last_idx] if last_idx < len(vals) else '',
        }

# Find eGlu
eglu_start = next(i for i, l in enumerate(csv_lines) if l.strip() == 'eGlu')
eglu_fields = csv_lines[eglu_start+1].strip().split(',')
eglu_team_idx = eglu_fields.index('dXSB')
eglu_xswt_idx = eglu_fields.index('XSWT')
eglu_data = eglu_start + 3

BASE = 0x0A3168
ULGE_RECS = 0x1AB73C

for save_name in MS_SAVES:
    save_path = os.path.join(SRC, save_name)
    if not os.path.exists(save_path):
        print(f"\n=== {save_name}: MISSING ===")
        continue
    
    with open(save_path, "rb") as f:
        ms = f.read()
    
    if len(ms) != len(orig):
        print(f"\n=== {save_name}: SIZE MISMATCH ({len(ms)} vs {len(orig)}) ===")
        continue
    
    # Find what player record changed
    diffs = [(i, orig[i], ms[i]) for i in range(len(orig)) if orig[i] != ms[i]]
    
    # Identify the player by finding player record changes
    player_recs = set()
    for off, _, _ in diffs:
        if off >= BASE:
            rec = (off - BASE) // 132
            player_recs.add(rec)
    
    # Filter to records that have both team_alt and proteam changes
    changed_recs = []
    for rec in sorted(player_recs):
        rs = BASE + rec * 132
        no_proteam = orig[rs + 115]
        no_team_alt = orig[rs + 6]
        ms_proteam = ms[rs + 115]
        ms_team_alt = ms[rs + 6]
        if no_proteam != ms_proteam or no_team_alt != ms_team_alt:
            # Find player info from CSV
            pid = None
            for p, info in players.items():
                if info['csv_rec'] + 1 == rec:
                    pid = p
                    break
            if pid:
                info = players[pid]
                old_team = (no_proteam >> 3) & 0x1F
                new_team = (ms_proteam >> 3) & 0x1F
                changed_recs.append((rec, pid, info['first'], info['last'], 
                                    old_team, new_team, ms_team_alt))
    
    print(f"\n=== {save_name} ===")
    if changed_recs:
        for rec, pid, first, last, old_t, new_t, ta in changed_recs:
            print(f"\n  Player: {first} {last} (PID={pid}, rec={rec})")
            print(f"    proteam: {old_t} -> {new_t}")
            print(f"    team_alt: -> {ta}")
    else:
        print("  No player team changes found")
    
    # Edit-log region (0x1B97C8 - 0x1B97E0)
    print(f"\n  Edit-log region (0x1B97C8-0x1B97E0):")
    for off in range(0x1B97C8, 0x1B97E0, 16):
        if off + 16 > len(orig):
            break
        o_bytes = orig[off:off+16]
        m_bytes = ms[off:off+16]
        if o_bytes != m_bytes:
            o_hex = ' '.join(f'{b:02x}' for b in o_bytes)
            m_hex = ' '.join(f'{b:02x}' for b in m_bytes)
            marker = ' *** CHANGED ***'
            print(f"    0x{off:08x}: orig [{o_hex}]")
            print(f"    0x{off:08x}: ms   [{m_hex}]{marker}")
    
    # Find which eGlu record was zeroed
    print(f"\n  eGlu records zeroed (bytes 4-6):")
    for rec_off in range(ULGE_RECS, ULGE_RECS + 4000 * 16, 16):
        if rec_off + 7 > len(orig):
            break
        rec_idx = (rec_off - ULGE_RECS) // 16
        if bytes(orig[rec_off+4:rec_off+7]) != bytes(ms[rec_off+4:rec_off+7]):
            no_val = orig[rec_off+4:rec_off+7].hex(' ')
            ms_val = ms[rec_off+4:rec_off+7].hex(' ')
            # Check if MS zeroed this
            if ms[rec_off+4] == 0 and ms[rec_off+5] == 0 and ms[rec_off+6] == 0:
                # Find what team this record belongs to
                # Look up in CSV
                eglu_line = eglu_data + rec_idx
                if eglu_line < len(csv_lines):
                    # Find the team for this record from CSV
                    pass
                print(f"    rec {rec_idx} @ 0x{rec_off:x}: orig=[{no_val}] -> ms=[{ms_val}] ZEROED")
    
    # CRC counter
    print(f"\n  CRC counter @ 0x1AB24B: orig=0x{orig[0x1AB24B]:02x}  ms=0x{ms[0x1AB24B]:02x}")
    
    # Specific edit-log bytes
    print(f"  Edit-log bytes:")
    for label, off in [
        ("0x1B97CC (team-1)", 0x1B97CC),
        ("0x1B97D0-D2 (saved)", None),
        ("0x1B97D4 (prefix)", 0x1B97D4),
        ("0x1B97D5 (0x80)", 0x1B97D5),
    ]:
        if off:
            print(f"    {label}: orig=0x{orig[off]:02x} ms=0x{ms[off]:02x}")
        else:
            print(f"    {label}: orig=[{orig[0x1B97D0]:02x} {orig[0x1B97D1]:02x} {orig[0x1B97D2]:02x}] ms=[{ms[0x1B97D0]:02x} {ms[0x1B97D1]:02x} {ms[0x1B97D2]:02x}]")

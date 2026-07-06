"""Extract edit-log pattern from ALL working MS saves."""
import struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"

with open(os.path.join(SRC, "default_orig.db"), "rb") as f:
    orig = f.read()

SAVES = [
    ("default_orig_matthews_cbj.db",  "Matthews",  "CBJ", 9),
    ("default_orig_matthews_ana.db",  "Matthews",  "ANA", 1),
    ("default_orig_mcd_cbj.db",       "McDavid",   "CBJ", 9),
    ("default_orig_mcd_lak.db",       "McDavid",   "LAK", 14),
    ("default_orig_mcd_ana.db",       "McDavid",   "ANA", 1),
    ("default_orig_drai_lak.db",      "Draisaitl", "LAK", 14),
    ("default_orig_drai_ana.db",      "Draisaitl", "ANA", 1),
]

print(f"{'Save':<38} {'Player':>10} {'Tgt':>4} {'P->T':>4} {'TA':>3} {'CRC':>3} {'CC':>4} {'saved[3]':>20} {'pref':>4} {'80':>3} {'eGlu':>6}")
print("-" * 120)

ULGE_RECS = 0x1AB73C
BASE = 0x0A3168

for save_name, player_name, target_name, target_team in SAVES:
    path = os.path.join(SRC, save_name)
    if not os.path.exists(path):
        print(f"{save_name:<38} MISSING")
        continue
    
    with open(path, "rb") as f:
        ms = f.read()
    
    # Find changed player record
    changed_rec = None
    for rec in range(500, 6500):
        rs = BASE + rec * 132
        if rs + 115 >= len(orig): break
        if orig[rs + 115] != ms[rs + 115] or orig[rs + 6] != ms[rs + 6]:
            changed_rec = rec
            break
    
    if changed_rec is None:
        print(f"{save_name:<38} NO CHANGE")
        continue
    
    rs = BASE + changed_rec * 132
    new_pt = (ms[rs + 115] >> 3) & 0x1F
    new_ta = ms[rs + 6]
    
    cc = ms[0x1B97CC]
    saved_bytes = ms[0x1B97D0:0x1B97D3]
    prefix = ms[0x1B97D4]
    const80 = ms[0x1B97D5]
    crc_counter = ms[0x1AB24B]
    
    # Find displaced eGlu record
    displaced_rec = None
    for rec_off in range(ULGE_RECS, min(ULGE_RECS + 4000 * 16, len(orig) - 7), 16):
        rec_idx = (rec_off - ULGE_RECS) // 16
        if bytes(orig[rec_off+4:rec_off+7]) == saved_bytes:
            if ms[rec_off+4] == 0 and ms[rec_off+5] == 0 and ms[rec_off+6] == 0:
                displaced_rec = rec_idx
                break
    
    saved_hex = saved_bytes.hex(' ')
    dr = str(displaced_rec) if displaced_rec is not None else '?'
    
    print(f"{save_name:<38} {player_name:>10} {target_name:>4} {new_pt:>4} {new_ta:>3} "
          f"0x{crc_counter:02x} {cc:#04x} {saved_hex:>20} {prefix:#04x} {const80:#04x} {dr:>6}")

# ── PREFIX FORMULA ──
print("\n\nPrefix derivation:")
# Read CSV for PIDs
csv_path = os.path.join(SRC, "default_orig.csv")
with open(csv_path, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()
ubPc_start = next(i for i, l in enumerate(lines) if l.strip() == 'ubPc')
ubPc_fields = lines[ubPc_start+1].strip().split(',')
pid_idx = ubPc_fields.index('wBIz')
first_idx = ubPc_fields.index('HdeP')
last_idx = ubPc_fields.index('QbMR')

pid_by_rec = {}
for i in range(ubPc_start+3, len(lines)):
    line = lines[i].strip()
    if not line: break
    vals = line.split(',')
    if len(vals) > pid_idx and vals[pid_idx]:
        csv_rec = i - (ubPc_start + 3)
        pid_by_rec[csv_rec + 1] = {'pid': int(vals[pid_idx]), 'name': vals[first_idx] + ' ' + vals[last_idx]}

valid = []
for save_name, player_name, target_name, target_team in SAVES:
    path = os.path.join(SRC, save_name)
    if not os.path.exists(path): continue
    with open(path, "rb") as f:
        ms = f.read()
    changed_rec = None
    for rec in range(500, 6500):
        rs = BASE + rec * 132
        if rs + 115 >= len(orig): break
        if orig[rs + 115] != ms[rs + 115] or orig[rs + 6] != ms[rs + 6]:
            changed_rec = rec
            break
    if changed_rec is None: continue
    new_pt = (ms[rs + 115] >> 3) & 0x1F
    if new_pt == 0: continue  # skip failed moves (team 0)
    
    prefix = ms[0x1B97D4]
    pid = pid_by_rec.get(changed_rec, {}).get('pid', 0)
    valid.append((player_name, target_name, target_team, changed_rec, pid, prefix, ms[0x1B97CC]))

print(f"\n{'Player':>10} {'Tgt':>4} {'tID':>3} {'rec':>5} {'PID':>6} {'pref':>4} {'CC':>4} {'t-1':>4} {'rec%256':>7} {'PID%256':>7}")
for player_name, target_name, tid, rec, pid, prefix, cc in valid:
    print(f"{player_name:>10} {target_name:>4} {tid:>3} {rec:>5} {pid:>6} {prefix:#04x} {cc:#04x} {tid-1:#04x} {rec%256:#04x}    {pid%256:#04x}")

# Deduce prefix
print("\nDeduced prefix formulas:")
for player_name, target_name, tid, rec, pid, prefix, cc in valid:
    candidates = []
    candidates.append(("t*19", tid * 19))
    candidates.append(("rec%256", rec % 256))
    candidates.append(("pid%256", pid % 256))
    candidates.append(("t+160", tid + 160))
    matches = [c for c in candidates if c[1] == prefix]
    print(f"  {player_name}->{target_name}: prefix=0x{prefix:02x}  matches: {[c[0] for c in matches] if matches else 'NONE'}")

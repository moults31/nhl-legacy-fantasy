"""Build McDavid->ANA and Draisaitl->LAK test saves (fixed)."""
import struct, os, subprocess, datetime

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

with open(os.path.join(SRC, "default_orig.db"), "rb") as f:
    orig = bytearray(f.read())

BASE = 0x0A3168

# Read CSV for player/team lookup
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
eglu_data = eglu_start + 3

def last_eglu_rec_for_team(team_id_0idx):
    last = None
    for i in range(eglu_data, len(csv_lines)):
        line = csv_lines[i].strip()
        if not line or (len(line) == 4 and line.isascii() and line.isalpha()):
            break
        vals = line.split(',')
        if len(vals) > eglu_team_idx and vals[eglu_team_idx] == str(team_id_0idx):
            last = i - eglu_data
    return last

# Find Draisaitl by name
draisaitl_pid = None
for pid, info in players.items():
    if info['first'] == 'Leon' and info['last'] == 'Draisaitl':
        draisaitl_pid = pid
        break

moves = [
    {'pid': '10647',       'name': 'McDavid',   'team': 1,  'team_name': 'ANA'},
    {'pid': draisaitl_pid, 'name': 'Draisaitl', 'team': 14, 'team_name': 'LAK'},
]

for m in moves:
    pid = m['pid']
    info = players[pid]
    csv_rec = info['csv_rec']
    rust_rec = csv_rec + 1
    target_1idx = m['team']
    target_0idx = target_1idx - 1
    
    print(f"\n--- {info['first']} {info['last']} (PID={pid}) to {m['team_name']} (team {target_1idx}) ---")
    print(f"  CSV rec={csv_rec}, Rust rec={rust_rec}")
    
    db = bytearray(orig)
    RS = BASE + rust_rec * 132
    
    # proteam + team_alt
    db[RS + 115] = (target_1idx & 0x1F) << 3
    db[RS + 6] = target_1idx
    
    # Displaced eGlu record
    displaced_rec = last_eglu_rec_for_team(target_0idx)
    if displaced_rec is None:
        print(f"  ERROR: No eGlu records for team {target_0idx}")
        continue
    
    recs_base = 0x1AB73C
    displaced_off = recs_base + displaced_rec * 16
    saved = bytes(db[displaced_off+4:displaced_off+7])
    print(f"  Displacing eGlu rec {displaced_rec} (TDB 0x{displaced_off:x}), saved=[{saved.hex(' ')}]")
    
    # Edit-log writes
    db[0x1B97CC] = target_0idx
    db[0x1B97D0] = saved[0]
    db[0x1B97D1] = saved[1]
    db[0x1B97D2] = saved[2]
    db[0x1B97D4] = 0xAC
    db[0x1B97D5] = 0x80
    
    # Zero displaced record bytes 4-6
    db[displaced_off+4] = 0x00
    db[displaced_off+5] = 0x00
    db[displaced_off+6] = 0x00
    
    # CRC counter
    db[0x1AB24B] = 0x0A
    
    label = f"V_{m['team_name']}"
    
    # Save, reseal, pack, install
    pre_db = os.path.join(TMP, f"{label.lower()}_pre.db")
    with open(pre_db, "wb") as f:
        f.write(bytes(db))
    
    result = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "reseal", pre_db, "--output", f"{TMP}/{label.lower()}.db", "--ms-only"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  RESEAL FAILED: {result.stderr}")
        continue
    
    result = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "pack-fdeflate", f"{TMP}/{label.lower()}.db", f"{BIN}/TRADEEDIT5",
        "--output", f"{TMP}/{label}.bin"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  PACK FAILED: {result.stderr}")
        continue
    
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    result = subprocess.run([
        "python", "tools/install_recomp_roster.py", f"{TMP}/{label}.bin",
        "--timestamp", ts, "--name", label,
        "--template-header", HEADER
    ], capture_output=True, text=True)
    print(f"  {result.stdout.strip()}")

print("\n=== Installed ===")
print("V_ANA: McDavid -> ANA (Anaheim) - displaces eGlu rec 1941")
print("V_LAK: Draisaitl -> LAK (Los Angeles) - displaces eGlu rec 3131")
print()
print("Test these in-game. If they silently fail:")
print("  Use Modding Studio on default_orig.db to make these same moves,")
print("  and save the output .db files. That will let me reverse the real pattern.")

"""Check team ID scheme for Matthews."""
path = r'C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511\default_orig.csv'

with open(path, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Show StEO rows for NHL teams (first 30 entries)
print('StEO NHL teams (first 30):')
for i in range(6, 36):
    vals = lines[i].strip().split(',')
    tid = i - 6
    city = vals[1] if len(vals) > 1 else '?'
    clpb = vals[0] if vals[0] else '?'
    print(f'  row {tid}: ClpB={clpb}, City={city}')

# Find Matthews in ubPc
ubPc_start = None
for i, line in enumerate(lines):
    if line.strip() == 'ubPc':
        ubPc_start = i
        break

ubPc_fields = lines[ubPc_start+1].strip().split(',')
pid_idx = ubPc_fields.index('wBIz')
first_idx = ubPc_fields.index('HdeP')
last_idx = ubPc_fields.index('QbMR')
dXSB_idx = ubPc_fields.index('dXSB')

data_start = ubPc_start + 3
for i in range(data_start, len(lines)):
    vals = lines[i].strip().split(',')
    if not vals or not vals[0]:
        break
    pid = vals[pid_idx] if pid_idx < len(vals) else ''
    if pid == '13516':
        fn = vals[first_idx] if first_idx < len(vals) else ''
        ln = vals[last_idx] if last_idx < len(vals) else ''
        tid = vals[dXSB_idx] if dXSB_idx < len(vals) else ''
        print(f'\nMatthews: ubPc.dXSB={tid}, PID={pid}, Name={fn} {ln}')
        # Look up city from StEO
        if tid and tid.isdigit():
            idx = int(tid)
            if 6 + idx < len(lines):
                st_line = lines[6 + idx]
                st_vals = st_line.strip().split(',')
                print(f'  StEO row {idx}: City={st_vals[1]}')
        break

# Also check TRADEEDIT5 binary for Matthews proteam
import struct, zlib
tre5_path = r'C:\Users\galileo\code\nhl-legacy-fantasy\_local\game-saves\xbox\TRADEEDIT5'
with open(tre5_path, 'rb') as f:
    packed = f.read()
db = zlib.decompress(packed[48:])

BASE = 0x0A3168
REC = 5592  # 0-indexed
RS = BASE + REC * 132
proteam = db[RS + 115]
team_alt = db[RS + 6]
proteam_team = (proteam >> 3) & 0x1F

print(f'\nTRADEEDIT5 binary:')
print(f'  proteam  ({RS+115:#x}): 0x{proteam:02x} -> team {(proteam >> 3) & 0x1F} (1-indexed={proteam_team})')
print(f'  team_alt ({RS+6:#x}): 0x{team_alt:02x} -> team {team_alt} (1-indexed)')

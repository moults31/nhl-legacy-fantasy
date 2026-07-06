
"""Analyze Modding Studio's Matthews->ANA save to discover edit-log pattern."""
import struct, os

ms_path = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511\default_ms_matt_ana.db"
noedit_path = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511\default_ms_noedit.db"

with open(ms_path, 'rb') as f:
    ms = f.read()
    
print(f"MS Matthews->ANA save size: {len(ms)} ({len(ms):#x})")

# Look at edit-log region (0x1B97D0-0x1B9815)
print("\n=== MS Matthews->ANA edit-log region ===")
for offset in range(0x1B97D0, 0x1B9815 + 1, 16):
    chunk = ms[offset:offset+16]
    hex_str = ' '.join(f'{b:02x}' for b in chunk)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f'0x{offset:08x}: {hex_str}  {ascii_str}')

# Also look at the pre-move slots (0x1B97D1 and 0x1B97E1)
print(f"\nHedman slot (0x1B97D1-0x1B97E0): {ms[0x1B97D1:0x1B97E1].hex(' ')}")
print(f"Crosby slot (0x1B97E1-0x1B97F1): {ms[0x1B97E1:0x1B97F1].hex(' ')}")

# Look for Matthews marker - check write at 0x1B9802
print(f"\nMove entry at 0x1B97FC-0x1B9806: {ms[0x1B97FC:0x1B9806].hex(' ')}")
print(f"  team-1  (0x1B97FC): 0x{ms[0x1B97FC]:02x} (= team {ms[0x1B97FC] + 1})")
print(f"  marker  (0x1B9802): 0x{ms[0x1B9802]:02x}")
print(f"  prefix  (0x1B9801): 0x{ms[0x1B9801]:02x}")
print(f"  t*19    (0x1B9804): 0x{ms[0x1B9804]:02x}")
print(f"  0x80    (0x1B9805): 0x{ms[0x1B9805]:02x}")

# CRC counter
print(f"\nCRC counter @ 0x1AB24B: 0x{ms[0x1AB24B]:02x}")

# Check Matthews' proteam and team_alt
# Record 5592, base 0x0A3168
matthews_rec = 5592
base = 0x0A3168
rs = base + matthews_rec * 132
print(f"\nMatthews (rec {matthews_rec} @ 0x{rs:x}):")
print(f"  proteam  ({rs+115:#x}): 0x{ms[rs+115]:02x}")
print(f"  team_alt ({rs+6:#x}): 0x{ms[rs+6]:02x}")

# Compare with no-edit to see all changes
if os.path.exists(noedit_path):
    with open(noedit_path, 'rb') as f:
        noedit = f.read()
    
    if len(ms) == len(noedit):
        diffs = [(i, noedit[i], ms[i]) for i in range(len(ms)) if noedit[i] != ms[i]]
        print(f"\n=== Total diffs vs no-edit: {len(diffs)} ===")
        
        # Group diffs by region
        edit_log_diffs = [(i, n, m) for i, n, m in diffs if 0x1B97D0 <= i <= 0x1B9820]
        print(f"\nEdit-log diffs ({len(edit_log_diffs)}):")
        for i, n, m in edit_log_diffs:
            print(f"  0x{i:08x}: noedit=0x{n:02x} -> ms=0x{m:02x}")
        
        # All other diff clusters
        print(f"\nAll diff clusters:")
        in_diff = False
        diff_start = 0
        cluster = []
        for i, n, m in diffs:
            if not in_diff:
                diff_start = i
                cluster = [(i, n, m)]
                in_diff = True
            elif i == cluster[-1][0] + 1:
                cluster.append((i, n, m))
            else:
                if len(cluster) >= 1:
                    print(f"\n  Cluster at 0x{diff_start:08x} ({len(cluster)} bytes):")
                    for bi, bn, bm in cluster[:16]:
                        print(f"    0x{bi:08x}: {bn:#04x} -> {bm:#04x}")
                    if len(cluster) > 16:
                        print(f"    ... ({len(cluster) - 16} more)")
                cluster = [(i, n, m)]
                diff_start = i
            in_diff = True
        if cluster and len(cluster) >= 1:
            print(f"\n  Cluster at 0x{diff_start:08x} ({len(cluster)} bytes):")
            for bi, bn, bm in cluster[:16]:
                print(f"    0x{bi:08x}: {bn:#04x} -> {bm:#04x}")
            if len(cluster) > 16:
                print(f"    ... ({len(cluster) - 16} more)")
    else:
        print(f"Sizes differ: ms={len(ms)}, noedit={len(noedit)}")
else:
    print(f"noedit file not found at {noedit_path}")

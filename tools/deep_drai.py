"""Deep search for Draisaitl's displaced bytes pattern."""
import struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
with open(os.path.join(SRC, 'default_orig.db'), 'rb') as f: orig = f.read()
with open(os.path.join(SRC, 'default_orig_drai_lak.db'), 'rb') as f: ms = f.read()

# All non-zero to zero changes
print("Non-zero->zero clusters in Draisaitl->LAK:")
zeroed = [off for off in range(len(orig)) if orig[off] != 0 and ms[off] == 0]
print(f"  Total: {len(zeroed)} bytes zeroed")

clusters = []
if zeroed:
    start = zeroed[0]
    prev = zeroed[0]
    for z in zeroed[1:]:
        if z != prev + 1:
            clusters.append((start, prev - start + 1))
            start = z
        prev = z
    clusters.append((start, prev - start + 1))
    
    for start, length in clusters:
        if length < 3:
            continue  # skip single bytes
        o_bytes = ' '.join(f'{orig[i]:02x}' for i in range(start, min(start+16, start+length)))
        print(f"  0x{start:08x} ({length}B): [{o_bytes}]")

# Search for the saved bytes anywhere
target = bytes([0x01, 0x0e, 0x20])
print(f"\nSearch for {target.hex(' ')} anywhere in orig:")
matches = []
idx = 0
while True:
    idx = orig.find(target, idx)
    if idx < 0: break
    matches.append(idx)
    idx += 1
print(f"  {len(matches)} occurrences")
for m in matches[:10]:
    print(f"  0x{m:08x}")

# Also check all MS saves quickly: which ones write to 0x1B97CC-0x1B97D5
# and whether the pattern at D3 changes
print("\nEdit-log D0-D5 across all working saves:")
for fname, label in [
    ("default_orig_matthews_cbj.db", "Matt->CBJ"),
    ("default_orig_mcd_cbj.db",      "McD->CBJ"),
    ("default_orig_mcd_lak.db",      "McD->LAK"),
    ("default_orig_drai_lak.db",     "Drai->LAK"),
]:
    path = os.path.join(SRC, fname)
    with open(path, 'rb') as f: m = f.read()
    d0_5 = m[0x1B97D0:0x1B97D6].hex(' ')
    cc = m[0x1B97CC]
    print(f"  {label}: CC=0x{cc:02x}  D0-D5=[{d0_5}]")

"""Diff default_orig.db vs default_orig_matthews_cbj.db to discover edit-log pattern."""
import struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"

with open(os.path.join(SRC, "default_orig.db"), "rb") as f:
    orig = f.read()
with open(os.path.join(SRC, "default_orig_matthews_cbj.db"), "rb") as f:
    ms = f.read()

print(f"Orig size: {len(orig)} ({len(orig):#x})")
print(f"MS   size: {len(ms)} ({len(ms):#x})")

if len(orig) != len(ms):
    print("SIZE MISMATCH")
    exit()

# Count diffs
diffs = [(i, orig[i], ms[i]) for i in range(len(orig)) if orig[i] != ms[i]]
print(f"\nTotal diffs: {len(diffs)}")

# Group into clusters
clusters = []
i = 0
while i < len(diffs):
    start = diffs[i][0]
    items = []
    while i < len(diffs) and (not items or diffs[i][0] == items[-1][0] + 1):
        items.append(diffs[i])
        i += 1
    clusters.append((start, items))

print(f"\nClusters: {len(clusters)}")
for start, items in clusters:
    length = len(items)
    print(f"\n  Cluster at 0x{start:08x} ({length} bytes):")
    # Show first 32 bytes of orig vs ms
    show = min(length, 32)
    o_hex = ' '.join(f'{o:02x}' for _, o, _ in items[:show])
    m_hex = ' '.join(f'{m:02x}' for _, _, m in items[:show])
    print(f"    orig: {o_hex}")
    print(f"    ms:   {m_hex}")
    if length > 32:
        print(f"    ... ({length - 32} more bytes)")

# Specifically analyze the edit-log region
print(f"\n=== Edit-log region (0x1B97D0-0x1B9820) ===")
for offset in range(0x1B97D0, 0x1B9820, 16):
    o_bytes = orig[offset:offset+16]
    m_bytes = ms[offset:offset+16]
    o_hex = ' '.join(f'{b:02x}' for b in o_bytes)
    m_hex = ' '.join(f'{b:02x}' for b in m_bytes)
    match = '  ' if o_bytes == m_bytes else '**'
    print(f"  0x{offset:08x}: orig [{o_hex}]")
    print(f"  0x{offset:08x}: ms   [{m_hex}] {match}")
    print()

# Also dump the region where the edit-log entry might be
# Known: Hedman slot at 0x1B97D1, Crosby slot at 0x1B97E1
# New player slots might be at higher offsets
print(f"=== Edit-log slots analysis ===")
# Dump as 16-byte slots from 0x1B97D0 onwards
for slot in range(0):
    base = 0x1B97D0 + slot * 16
    if base >= 0x1B9820:
        break
    o = orig[base:base+16]
    m = ms[base:base+16]
    o_hex = o.hex(' ')
    m_hex = m.hex(' ')
    marker = 'CHANGED' if o != m else 'same'
    print(f"  Slot {slot} @ 0x{base:08x}: orig={o_hex}")
    print(f"  Slot {slot} @ 0x{base:08x}: ms  ={m_hex}  ({marker})")

# Check the known edit-log write positions
for label, off in [("team-1", 0x1B97FC), ("0x41 prefix", 0x1B9801), 
                    ("marker", 0x1B9802), ("team*19", 0x1B9804), 
                    ("0x80", 0x1B9805), ("CRC counter", 0x1AB24B)]:
    print(f"  {label:15s} @ 0x{off:08x}: orig=0x{orig[off]:02x}  ms=0x{ms[off]:02x}")

# Also check if there are changes at the 0x1ACE71 region (Ovechkin's edit-log)
print(f"\n  Ovechkin cfg @ 0x1ACE71: orig=0x{orig[0x1ACE71]:02x}  ms=0x{ms[0x1ACE71]:02x}")

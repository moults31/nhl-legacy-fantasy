"""Find Draisaitl's displaced eGlu record and deduce the full pattern."""
import struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
with open(os.path.join(SRC, 'default_orig.db'), 'rb') as f: orig = f.read()
with open(os.path.join(SRC, 'default_orig_drai_lak.db'), 'rb') as f: ms = f.read()

ULGE = 0x1AB73C
target = bytes([0x01, 0x0e, 0x20])
t2 = bytes([0x01, 0x12, 0x10])  # McDavid

print("Search eGlu for saved bytes:")
for label, tbytes in [("Draisaitl [01 0e 20]", target), ("McDavid [01 12 10]", t2)]:
    found = []
    for off in range(ULGE, min(ULGE + 3600 * 16, len(orig)), 16):
        for bp in range(0, 14):
            if off + bp + 3 > len(orig): continue
            if orig[off+bp:off+bp+3] == tbytes:
                rec = (off - ULGE) // 16
                zeroed = ms[off+bp] == 0 and ms[off+bp+1] == 0 and ms[off+bp+2] == 0
                found.append((rec, bp, zeroed))
    print(f"  {label}: {len(found)} matches")
    for rec, bp, zeroed in found:
        print(f"    rec {rec}, byte +{bp} {'[ZEROED]' if zeroed else ''}")

# eGlu rec 2788 details
print("\neGlu rec 2788 (McDavid's displaced record):")
off = ULGE + 2788 * 16
for b in range(16):
    if orig[off+b] != 0:
        print(f"  +{b}: orig=0x{orig[off+b]:02x}  ms=0x{ms[off+b]:02x}")

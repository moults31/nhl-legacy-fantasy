"""Find ALL displaced records by searching each MS file."""
import struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
with open(os.path.join(SRC, 'default_orig.db'), 'rb') as f:
    orig = f.read()

# Check each working MS save
for save_name, label, saved_hex in [
    ("default_orig_matthews_cbj.db", "Matthews->CBJ", "01 9b 90"),
    ("default_orig_mcd_cbj.db",      "McDavid->CBJ",  "01 12 10"),
    ("default_orig_mcd_lak.db",      "McDavid->LAK",  "01 12 10"),
    ("default_orig_drai_lak.db",     "Draisaitl->LAK","01 0e 20"),
]:
    path = os.path.join(SRC, save_name)
    if not os.path.exists(path):
        print(f"{label}: MISSING")
        continue
    with open(path, 'rb') as f:
        ms = f.read()
    
    saved = bytes.fromhex(saved_hex.replace(' ', ''))
    
    # Search entire binary for saved bytes that got zeroed
    print(f"\n{label}: saved={saved_hex}")
    matches = []
    for off in range(0, len(orig) - len(saved)):
        if orig[off:off+len(saved)] == saved:
            if ms[off] == 0 and ms[off+1] == 0 and ms[off+2] == 0:
                matches.append(off)
    
    print(f"  {len(matches)} zeroed locations found:")
    for m in matches[:10]:
        # Determine which table this is in
        print(f"    0x{m:08x}")
    
    # Also check the edit-log for this save
    print(f"  0x1B97CC: orig=0x{orig[0x1B97CC]:02x} ms=0x{ms[0x1B97CC]:02x}")
    print(f"  0x1B97D0-D5: orig=[{orig[0x1B97D0]:02x} {orig[0x1B97D1]:02x} {orig[0x1B97D2]:02x} {orig[0x1B97D3]:02x} {orig[0x1B97D4]:02x} {orig[0x1B97D5]:02x}]")
    print(f"               ms  =[{ms[0x1B97D0]:02x} {ms[0x1B97D1]:02x} {ms[0x1B97D2]:02x} {ms[0x1B97D3]:02x} {ms[0x1B97D4]:02x} {ms[0x1B97D5]:02x}]")

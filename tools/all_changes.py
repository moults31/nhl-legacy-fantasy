"""Find ALL changes in Draisaitl->LAK and McDavid->LAK."""
import struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
with open(os.path.join(SRC, 'default_orig.db'), 'rb') as f: orig = f.read()

for save_name, label in [
    ("default_orig_drai_lak.db", "Draisaitl->LAK"),
    ("default_orig_mcd_lak.db", "McDavid->LAK"),
]:
    path = os.path.join(SRC, save_name)
    with open(path, 'rb') as f: ms = f.read()
    
    diff_count = sum(1 for i in range(len(orig)) if orig[i] != ms[i])
    print(f"\n{label}: {diff_count} total byte changes")
    
    diffs = [(i, orig[i], ms[i]) for i in range(len(orig)) if orig[i] != ms[i]]
    clusters = []
    if diffs:
        start = diffs[0][0]
        prev = diffs[0][0]
        items = [diffs[0]]
        for d in diffs[1:]:
            if d[0] == prev + 1:
                items.append(d)
            else:
                clusters.append((start, items))
                items = [d]
                start = d[0]
            prev = d[0]
        clusters.append((start, items))
    
    for start, items in clusters:
        o_hex = ' '.join(f'{o:02x}' for _, o, _ in items[:16])
        m_hex = ' '.join(f'{m:02x}' for _, _, m in items[:16])
        suffix = ' ...' if len(items) > 16 else ''
        print(f"  0x{start:08x} ({len(items)}B): orig=[{o_hex}]{suffix}")
        print(f"  {'':10s} ms  =[{m_hex}]{suffix}")

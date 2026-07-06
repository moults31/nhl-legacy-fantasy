import zlib, os

SRC = r'C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511'

# Test Ovechkin->COL
with open('tools/tmp/rust_ovi_col.bin', 'rb') as f:
    rust = zlib.decompress(f.read()[48:])
with open(os.path.join(SRC, 'default_ms_ovi_col.db'), 'rb') as f:
    ms = f.read()
diffs = [i for i in range(len(rust)) if rust[i] != ms[i]]
print(f'Ovechkin->COL: {"PERFECT" if len(diffs)==0 else f"{len(diffs)} diffs"}')

# Test no-CRC version
with open('tools/tmp/rust_crsb_col_nocrc.bin', 'rb') as f:
    nocrc = zlib.decompress(f.read()[48:])
with open(os.path.join(SRC, 'default_ms_crsb_col.db'), 'rb') as f:
    ms_crsb = f.read()
nocrc_diffs = [(i, nocrc[i], ms_crsb[i]) for i in range(len(nocrc)) if nocrc[i] != ms_crsb[i]]
crc_regions = [(0x1A4838, 0x1A483C), (0x1AB258, 0x1AB25C), (0x1D5F2C, 0x1D5F30)]
non_crc = [(i, n, m) for i, n, m in nocrc_diffs if not any(s <= i < e for s, e in crc_regions)]
crc_only = [(i, n, m) for i, n, m in nocrc_diffs if any(s <= i < e for s, e in crc_regions)]
print(f'No-CRC vs MS: {len(nocrc_diffs)} total diffs ({len(crc_only)} CRC, {len(non_crc)} other)')
if non_crc:
    for off, r, m in non_crc[:5]:
        print(f'  0x{off:06X}: nocrc=0x{r:02X} ms=0x{m:02X}')

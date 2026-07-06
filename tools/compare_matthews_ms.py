
"""Compare MS Matthews save vs TRADEEDIT5 to find edit-log pattern for new players."""
import struct

tre5_path = r'C:\Users\galileo\code\nhl-legacy-fantasy\_local\game-saves\xbox\TRADEEDIT5.db'
ms_path = r'C:\Users\galileo\code\nhl-legacy-fantasy\tools\tmp\matthews_ms.db'

with open(tre5_path, 'rb') as f:
    tre5 = f.read()

with open(ms_path, 'rb') as f:
    ms = f.read()

print(f'TRADEEDIT5 size: {len(tre5)} ({len(tre5):#x})')
print(f'mathews_ms size: {len(ms)} ({len(ms):#x})')

if len(tre5) != len(ms):
    print(f'WARNING: sizes differ!')
    # Use smaller
    min_len = min(len(tre5), len(ms))
    tre5 = tre5[:min_len]
    ms = ms[:min_len]

# Count total differences
diffs = 0
for i in range(len(tre5)):
    if tre5[i] != ms[i]:
        diffs += 1
print(f'\nTotal byte differences: {diffs}')

# Compare edit-log region 0x1B97D0-0x1B9810
print()
print('=== Edit-log region comparison (0x1B97D0-0x1B9810) ===')
print(f'{"Offset":<10} {"TRADEEDIT5":<50} {"matthews_ms":<50} {"Match?":<6}')
for offset in range(0x1B97D0, 0x1B9810, 16):
    t_bytes = tre5[offset:offset+16]
    m_bytes = ms[offset:offset+16]
    t_hex = ' '.join(f'{b:02x}' for b in t_bytes)
    m_hex = ' '.join(f'{b:02x}' for b in m_bytes)
    match = 'YES' if t_bytes == m_bytes else 'DIFF'
    print(f'0x{offset:08x}: {t_hex:<50} {m_hex:<50} {match}')

# Also compare the 0x1AE750 region (eGlu record 769)
print()
print('=== eGlu record 769 region (0x1AE74C-0x1AE75C) ===')
for offset in range(0x1AE74C, 0x1AE75C + 1, 16):
    t_bytes = tre5[offset:offset+16]
    m_bytes = ms[offset:offset+16]
    t_hex = ' '.join(f'{b:02x}' for b in t_bytes)
    m_hex = ' '.join(f'{b:02x}' for b in m_bytes)
    match = 'YES' if t_bytes == m_bytes else 'DIFF'
    print(f'0x{offset:08x}: {t_hex:<50} {m_hex:<50} {match}')

# CRC counter at 0x1AB24B
print(f'\nCRC counter @ 0x1AB24B: TRADEEDIT5=0x{tre5[0x1AB24B]:02x}  ms=0x{ms[0x1AB24B]:02x}')

# Check the 3 CRC regions
for label, off in [('RBQQ prior_crc', 0x1A4838), ('ulGe header_crc', 0x1AB258), ('caBZ prior_crc', 0x1D5F2C)]:
    t_val = struct.unpack('>I', tre5[off:off+4])[0]
    m_val = struct.unpack('>I', ms[off:off+4])[0]
    print(f'{label} @ 0x{off:08x}: TRADEEDIT5=0x{t_val:08x}  ms=0x{m_val:08x}  match={t_val==m_val}')

# Check proteam and team_alt for Matthews (record 5592)
matthews_rec = 5592
base = 0x0A3168
rs = base + matthews_rec * 132
t_proteam = tre5[rs + 115]
t_team_alt = tre5[rs + 6]
m_proteam = ms[rs + 115]
m_team_alt = ms[rs + 6]
print(f'\nMatthews (rec {matthews_rec} @ 0x{rs:x}):')
print(f'  TRADEEDIT5: proteam=0x{t_proteam:02x}, team_alt=0x{t_team_alt:02x}')
print(f'  ms:         proteam=0x{m_proteam:02x}, team_alt=0x{m_team_alt:02x}')

# Check all non-matching byte regions (clusters of diffs)
print(f'\n=== Diff clusters (>= 3 consecutive diffs) ===')
in_diff = False
diff_start = 0
for i in range(len(tre5)):
    is_diff = tre5[i] != ms[i]
    if is_diff and not in_diff:
        diff_start = i
        in_diff = True
    elif not is_diff and in_diff:
        length = i - diff_start
        if length >= 3:
            # Show first 32 bytes of diff
            show_len = min(length, 32)
            t_hex = ' '.join(f'{b:02x}' for b in tre5[diff_start:diff_start+show_len])
            m_hex = ' '.join(f'{b:02x}' for b in ms[diff_start:diff_start+show_len])
            suffix = ' ...' if length > 32 else ''
            print(f'\n  0x{diff_start:08x} ({length} bytes):')
            print(f'    TRE5: {t_hex}{suffix}')
            print(f'    MS:   {m_hex}{suffix}')
        in_diff = False

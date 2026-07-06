"""Inspect raw TDB header to understand 0x1DFB20."""
import struct, os

SRC = r'C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511'
with open(os.path.join(SRC, 'default_orig.db'), 'rb') as f:
    data = f.read()

print('=== TDB header investigation ===')
print(f'File size: {len(data)} (0x{len(data):x})')

# Dump first 48 bytes
print('\nFirst 48 bytes:')
for i in range(0, 48, 16):
    chunk = data[i:i+16]
    hex_str = ' '.join(f'{b:02x}' for b in chunk)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f'  {i:#06x}: {hex_str}  {ascii_str}')

# Try parsing TDB header at offset 0
fmt_le = struct.Struct('<I')
fmt_be = struct.Struct('>I')
print(f'\n  [0:4]   LE={fmt_le.unpack(data[0:4])[0]:#010x} BE={fmt_be.unpack(data[0:4])[0]:#010x}')
print(f'  [4:8]   LE={fmt_le.unpack(data[4:8])[0]:#010x} (table_count?)')
print(f'  [8:12]  LE={fmt_le.unpack(data[8:12])[0]:#010x} (data_start?)')

# Search for known table names
for name in [b'cPbu', b'inlv', b'RBQQ', b'ulGe', b'caBZ', b'ubPc', b'FxFG', b'GFxF']:
    idx = data.find(name)
    if idx >= 0:
        prior = fmt_be.unpack(data[idx-4:idx])[0]
        hdr_crc = fmt_be.unpack(data[idx+36:idx+40])[0] if idx+40 <= len(data) else 0
        print(f'\n  Found {name!r} at offset 0x{idx:x}')
        print(f'    prior_crc @ -4: 0x{prior:08x}')
        print(f'    header_crc @ +36: 0x{hdr_crc:08x}')

# Check if 0x1DFB20 is at a known offset
print(f'\n=== Checking 0x1DFB20 ===')
# Is it at +4 after some table name?
for name in [b'cPbu', b'inlv', b'RBQQ', b'ulGe', b'caBZ']:
    idx = data.find(name)
    if idx >= 0:
        info_start = idx - 4  # table info starts 4 bytes before name
        rec_size = struct.unpack_from('<I', data, info_start + 16)[0]
        rec_count = struct.unpack_from('<I', data, info_start + 20)[0]
        data_size = rec_size * rec_count
        print(f'  {name!r}: info=0x{info_start:x}, rec_size={rec_size}, rec_count={rec_count}, data={data_size} bytes')
        data_end = info_start + 40 + data_size
        print(f'    Data ends at 0x{data_end:x}')
        if data_end == 0x1DFB20:
            print(f'    *** NEXT TABLE starts at 0x1DFB20! This is a prior_crc ***')

# Find what's at 0x1DFB20-4 (the name at this table)
name_at = data[0x1DFB20:0x1DFB24]
print(f'\n  Table name at 0x1DFB20: {name_at!r}')
# Check what the prior CRC is
prior = fmt_be.unpack(data[0x1DFB20:0x1DFB24])[0] if 0x1DFB20+4 <= len(data) else 0
hdr = fmt_be.unpack(data[0x1DFB20+36:0x1DFB20+40])[0] if 0x1DFB20+40 <= len(data) else 0
print(f'  prior_crc value: 0x{prior:08x}')
print(f'  header_crc value: 0x{hdr:08x}')

# Dump around 0x1DFB20
print(f'\n=== Region around 0x1DFB20 ===')
for off in range(0x1DFB10, min(0x1DFB50, len(data)), 16):
    chunk = data[off:off+16]
    hex_str = ' '.join(f'{b:02x}' for b in chunk)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    marker = ' <-- 0x1DFB20' if off <= 0x1DFB20 < off+16 else ''
    print(f'  0x{off:08x}: {hex_str}  {ascii_str}{marker}')

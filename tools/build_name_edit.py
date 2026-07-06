#!/usr/bin/env python3
"""Build a save with a player NAME edit to check if the game even loads our DB at all."""
import zlib as zl, struct, subprocess

BIN = "_local/game-saves/xbox"

with open(f"{BIN}/hedman_col.db", "rb") as f:
    ms_db = bytearray(f.read())

# Find "Crosby" in the DB and change it to "CrsbyX"
needle = b"Crosby"
pos = ms_db.find(needle)
if pos >= 0:
    print(f"'Crosby' found at offset 0x{pos:X}")
    ms_db[pos+5] = ord('X')  # Crosby -> CrsbyX
    print(f"Changed to: {ms_db[pos:pos+7]}")
else:
    print("'Crosby' not found, trying other encodings")
    # Try as UTF-16 or other encodings
    for i in range(0, len(ms_db)-40, 2):
        chunk = ms_db[i:i+14]
        if chunk == b'C\x00r\x00o\x00s\x00b\x00y\x00\x00\x00':
            print(f"Found UTF-16 Crosby at 0x{i:X}")
            ms_db[i+10] = ord('X')
            break

with open(f"{BIN}/name_edit.db", "wb") as f:
    f.write(ms_db)

# Pack
subprocess.run([
    "cargo", "run", "-p", "roster-cli", "--release", "--",
    "pack",
    "--output", f"{BIN}/NAME_EDIT.bin",
    f"{BIN}/name_edit.db", f"{BIN}/TRADEEDIT5",
], check=False)

# Also: hex-edit T0_CLEAN.bin at the proteam byte (bypass re-encoder entirely)
with open(f"{BIN}/T0_CLEAN.bin", "rb") as f:
    t0 = bytearray(f.read())
t0_db = bytearray(zl.decompress(t0[48:]))
t0_db[0x0B949B] = 0x40  # Crosby -> COL

# Re-compress with flate2 (not template) 
import io
comp_buf = bytearray()
compressor = zl.compressobj(level=6, wbits=15)  # max compression
comp_buf.extend(compressor.compress(bytes(t0_db)))
comp_buf.extend(compressor.flush())
# Pad to 2456072
padded = bytearray(comp_buf)
while len(padded) < 2456072:
    padded.append(0)
padded = padded[:2456072]

hex_edit = bytearray(t0)
hex_edit[48:] = padded
with open(f"{BIN}/HEX_EDIT.bin", "wb") as f:
    f.write(hex_edit)
print(f"HEX_EDIT.bin: {len(hex_edit)} bytes, decomp DB Crosby=0x{zl.decompress(hex_edit[48:])[0x0B949B]:02X}")

# Verify NAME_EDIT zlib
with open(f"{BIN}/NAME_EDIT.bin", "rb") as f:
    ne = f.read()
ne_db = zl.decompress(ne[48:])
pos2 = ne_db.find(b"Crsby")
if pos2 < 0:
    pos2 = ne_db.find(b"Crosby")
print(f"NAME_EDIT DB: 'Crosby' at 0x{pos2:X} = {ne_db[pos2:pos2+7]}")

# Install both
for label, fn, ts in [
    ("NAME_EDIT", "NAME_EDIT.bin", "20260308000601"),
    ("HEX_EDIT", "HEX_EDIT.bin", "20260308000602"),
]:
    subprocess.run([
        "python", "tools/install_recomp_roster.py",
        f"{BIN}/{fn}",
        "--timestamp", ts,
        "--name", label,
        "--template-header", r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\BUILDYOURAI 20260706025159.header",
    ], check=False)
    print(f"Installed {label} as {ts}")

"""List all installed saves with their names."""
import os

HEADERS = os.path.expandvars(r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001")
SAVES = os.path.expandvars(r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\00000001")

header_map = {}
for f in os.listdir(HEADERS):
    path = os.path.join(HEADERS, f)
    if not os.path.isfile(path):
        continue
    with open(path, 'rb') as h:
        data = h.read()
    if len(data) >= 0x49 + 16:
        name = data[0x49:0x49+16].decode('ascii', errors='replace').rstrip('\0').strip()
    else:
        name = '?'
    header_map[f] = name

print("Installed saves:")
for d in sorted(os.listdir(SAVES)):
    path = os.path.join(SAVES, d)
    if not os.path.isdir(path):
        continue
    header_file = d + '.header'
    display_name = header_map.get(header_file, '?')
    print(f"  {d:<50} {display_name}")

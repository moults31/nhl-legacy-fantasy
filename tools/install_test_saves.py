"""Install test roster saves: ZBAC_VFEQ and ZBAC_VFEQ_SWAP."""
import shutil
import struct
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECKPOINT = REPO / "_local/game-saves/checkpoint"
STAGING = REPO / "_local/game-saves/xbox/m5-staging"

# Save tree root (Proton compatdata, used by launch-nhl-legacy.sh)
# On Windows via Xenia: saves go to content/454109EC/
# Try both possible locations
POSSIBLE_BASES = [
    Path.home() / ".steam/steam/steamapps/compatdata/3623314720/pfx/drive_c/users/steamuser/Documents/nhllegacy/B13EBABEBABEBABE/454109EC",
    REPO / "_local/NHL Legacy Recomp/content/454109EC",
]

def find_base():
    for b in POSSIBLE_BASES:
        # Look for existing save folders
        for candidate in [b, b / "00000001"]:
            if candidate.is_dir():
                print(f"Found save tree at: {b}")
                return b
    # Fall back to first option
    print(f"No existing save tree found, will create under: {POSSIBLE_BASES[0]}")
    return POSSIBLE_BASES[0]

INSTALLS = [
    {
        "name": "ZBAC_VFEQ",
        "blob": CHECKPOINT / "zbac_vfeq.bin",
        "timestamp": "20260704230301",
        "trailer": "5301",
    },
    {
        "name": "ZBAC_VFEQ_SWAP",
        "blob": CHECKPOINT / "zbac_vfeq_swap.bin",
        "timestamp": "20260704230302",
        "trailer": "5302",
    },
]

def write_utf16_name(header, name, start=0x09, end=0x1F):
    header[0x08] = 0x00
    for i in range(start, end):
        header[i] = 0x00
    off = start
    for ch in name:
        if off + 1 >= end:
            raise ValueError(f"display name too long: {name!r}")
        code = ord(ch)
        header[off] = code & 0xFF
        header[off + 1] = (code >> 8) & 0xFF
        off += 2
    header[off] = 0x00
    header[off + 1] = 0x00

def install(base, item):
    folder_name = f"ROSTER {item['timestamp']}"
    blob_dir = base / "00000001" / folder_name
    blob_path = blob_dir / folder_name
    header_dir = base / "Headers" / "00000001"
    header_path = header_dir / f"{folder_name}.header"

    blob_dir.mkdir(parents=True, exist_ok=True)
    header_dir.mkdir(parents=True, exist_ok=True)

    # Copy blob
    shutil.copy2(item["blob"], blob_path)

    # Create header from template or from scratch
    template_header_path = REPO / "_local/game-saves/xbox/testroster.header"
    if template_header_path.is_file():
        header = bytearray(template_header_path.read_bytes())
    else:
        # Minimal header (the script expects a template)
        header = bytearray(512)
        header[0] = 0x00  # filler, the name starts at 0x09

    write_utf16_name(header, item["name"])
    ascii_block = f"{folder_name}\0{item['trailer']}".encode("ascii")
    if len(ascii_block) > 32:
        raise ValueError("header ascii block too long")
    header[0x108 : 0x108 + len(ascii_block)] = ascii_block
    header_path.write_bytes(bytes(header))

    print(f"Installed {item['name']} -> {blob_dir}")

    # Also copy to staging for easier reference
    staging_blob = STAGING / f"{item['name']}.bin"
    shutil.copy2(item["blob"], staging_blob)
    staging_header = STAGING / f"{item['name']}.header"
    header_path_bytes = header_path.read_bytes() if header_path.is_file() else bytes(header)
    staging_header.write_bytes(header_path_bytes)
    print(f"  Also staged at: {staging_blob}")

def main():
    base = find_base()
    for item in INSTALLS:
        if not item["blob"].is_file():
            print(f"MISSING BLOB: {item['blob']}")
            continue
        install(base, item)
    print("\nDone! In-game roster names to load:")
    for item in INSTALLS:
        print(f"  {item['name']}")

if __name__ == "__main__":
    main()

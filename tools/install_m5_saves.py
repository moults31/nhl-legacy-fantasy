#!/usr/bin/env python3
"""Install M5 verification roster saves beside TESTROSTER in the Proton tree."""

from __future__ import annotations

import argparse
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SaveInstall:
    display_name: str
    timestamp: str  # 14 digits, e.g. 20260704215001
    blob: Path
    trailer_id: str  # 4-char field copied into header after timestamp


DEFAULT_INSTALLS = [
    SaveInstall(
        display_name="M5CHK01",
        timestamp="20260704215002",
        blob=Path("M5CHK01.bin"),
        trailer_id="5102",
    ),
    SaveInstall(
        display_name="M5ANA02",
        timestamp="20260704215003",
        blob=Path("M5ANA02.bin"),
        trailer_id="5103",
    ),
    SaveInstall(
        display_name="M5MCT01",
        timestamp="20260704215004",
        blob=Path("M5MCT01.bin"),
        trailer_id="5104",
    ),
]


def write_utf16_name(header: bytearray, name: str, start: int = 0x09, end: int = 0x1F) -> None:
    header[0x08] = 0x00
    for i in range(start, end):
        header[i] = 0x00
    off = start
    for ch in name:
        if off + 1 >= end:
            raise ValueError(f"display name too long for header slot: {name!r}")
        code = ord(ch)
        header[off] = code & 0xFF
        header[off + 1] = (code >> 8) & 0xFF
        off += 2
    header[off] = 0x00
    header[off + 1] = 0x00


def patch_header(template: bytes, install: SaveInstall) -> bytes:
    header = bytearray(template)
    write_utf16_name(header, install.display_name)
    folder = f"ROSTER {install.timestamp}"
    ascii_block = f"{folder}\0{install.trailer_id}".encode("ascii")
    if len(ascii_block) > 32:
        raise ValueError("header ascii block too long")
    header[0x108 : 0x108 + len(ascii_block)] = ascii_block
    return bytes(header)


def install_save(base: Path, template_header: bytes, install: SaveInstall) -> Path:
    folder_name = f"ROSTER {install.timestamp}"
    blob_dir = base / "00000001" / folder_name
    blob_path = blob_dir / folder_name
    header_path = base / "Headers" / "00000001" / f"{folder_name}.header"

    blob_dir.mkdir(parents=True, exist_ok=True)
    (base / "Headers" / "00000001").mkdir(parents=True, exist_ok=True)

    shutil.copy2(install.blob, blob_path)
    header_path.write_bytes(patch_header(template_header, install))
    return blob_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        action="append",
        metavar="NAME",
        help="Install only these display names (repeatable)",
    )
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    staging = repo / "_local/game-saves/xbox/m5-staging"
    template_header = (repo / "_local/game-saves/xbox/testroster.header").read_bytes()
    base = Path.home() / (
        ".steam/steam/steamapps/compatdata/3623314720/pfx/drive_c/users/"
        "steamuser/Documents/nhllegacy/B13EBABEBABEBABE/454109EC"
    )

    installs = DEFAULT_INSTALLS
    if args.only:
        wanted = set(args.only)
        installs = [item for item in installs if item.display_name in wanted]

    for item in installs:
        blob = staging / item.blob
        if not blob.is_file():
            raise SystemExit(f"missing blob: {blob}")
        install = SaveInstall(
            display_name=item.display_name,
            timestamp=item.timestamp,
            blob=blob,
            trailer_id=item.trailer_id,
        )
        dest = install_save(base, template_header, install)
        print(f"installed {item.display_name} -> {dest}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Install a packed roster blob into the NHL Legacy Recomp (Windows) save tree."""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path


def write_utf16_name(header: bytearray, name: str, start: int = 0x09, end: int = 0x1F) -> None:
    """Write in-game list name as UTF-16LE starting at 0x09 (byte 0x08 must be 0x00)."""
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


def patch_header(template: bytes, folder_name: str, display_name: str) -> bytes:
    header = bytearray(template)
    write_utf16_name(header, display_name)
    ascii_block = f"{folder_name}\0".encode("ascii")
    if len(ascii_block) > 32:
        raise ValueError("header ascii block too long")
    header[0x108 : 0x108 + 32] = ascii_block + bytes(32 - len(ascii_block))
    return bytes(header)


def default_base() -> Path:
    return (
        Path.home()
        / "Documents/nhllegacy/B13EBABEBABEBABE/454109EC"
    )


def install_blob(
    base: Path,
    blob: Path,
    timestamp: str,
    display_name: str,
    template_header: Path,
) -> Path:
    folder_name = f"ROSTER {timestamp}"
    blob_dir = base / "00000001" / folder_name
    blob_path = blob_dir / folder_name
    header_path = base / "Headers" / "00000001" / f"{folder_name}.header"

    blob_dir.mkdir(parents=True, exist_ok=True)
    (base / "Headers" / "00000001").mkdir(parents=True, exist_ok=True)

    shutil.copy2(blob, blob_path)
    header_path.write_bytes(
        patch_header(template_header.read_bytes(), folder_name, display_name)
    )
    return blob_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blob", type=Path, help="Packed RosterFile inner save blob")
    parser.add_argument(
        "--timestamp",
        required=True,
        help="14-digit folder timestamp, e.g. 20260704230001",
    )
    parser.add_argument(
        "--name",
        default="TRADEEDIT",
        help="In-game display name (UTF-16, max ~12 chars)",
    )
    parser.add_argument(
        "--template-header",
        type=Path,
        help="Existing .header sidecar to clone metadata from",
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=default_base(),
        help="454109EC save root",
    )
    args = parser.parse_args()

    if not args.blob.is_file():
        raise SystemExit(f"missing blob: {args.blob}")

    template_header = args.template_header
    if template_header is None:
        # Prefer a header with valid UTF-16 @0x09 (game-created saves). ROSTER 20260307
        # template has a stray 0x48 at 0x09 and garbles the in-game list name.
        for candidate in (
            args.base / "Headers/00000001/BUILDYOURAI 20260705004003.header",
            args.base / "Headers/00000001/HOCKEYCARD 20260701232214.header",
            args.base / "Headers/00000001/ROSTER 20260307213511.header",
        ):
            if candidate.is_file():
                template_header = candidate
                break
    if not template_header.is_file():
        raise SystemExit(f"missing template header: {template_header}")

    data = args.blob.read_bytes()
    if not data.startswith(b"RosterFile"):
        raise SystemExit("blob must start with RosterFile magic")
    if data[48:50] != b"\x78\x9c":
        raise SystemExit(f"expected zlib 78 9c at offset 48, got {data[48:50].hex()}")

    dest = install_blob(args.base, args.blob, args.timestamp, args.name, template_header)
    print(f"installed {args.name} -> {dest}")
    print(f"header -> {args.base / 'Headers/00000001' / f'ROSTER {args.timestamp}.header'}")
    print("In-game: Customize / Load -> Roster -> Refresh (RB) -> pick slot -> Load")


if __name__ == "__main__":
    main()

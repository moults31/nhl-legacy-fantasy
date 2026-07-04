#!/usr/bin/env python3
"""Find RIP-relative LEA targets in a PE .text section (x86-64)."""

from __future__ import annotations

import struct
import sys
from dataclasses import dataclass


@dataclass
class Section:
    name: str
    va: int
    raw: int
    size: int


def parse_pe(data: bytes) -> tuple[int, list[Section]]:
    if data[:2] != b"MZ":
        raise ValueError("not MZ")
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_off : pe_off + 4] != b"PE\0\0":
        raise ValueError("not PE")
    num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    sec_table = pe_off + 24 + opt_size
    sections: list[Section] = []
    for i in range(num_sections):
        off = sec_table + i * 40
        name = data[off : off + 8].split(b"\0", 1)[0].decode()
        vsize, va, rsize, raw = struct.unpack_from("<IIII", data, off + 8)
        sections.append(Section(name, va, raw, rsize))
    image_base = struct.unpack_from("<Q", data, pe_off + 24 + 24)[0]
    return image_base, sections


def file_off_to_va(sections: list[Section], image_base: int, file_off: int) -> int | None:
    for sec in sections:
        if sec.raw <= file_off < sec.raw + sec.size:
            return image_base + sec.va + (file_off - sec.raw)
    return None


def scan_lea_xrefs(text: bytes, text_va: int, target_va: int) -> list[int]:
    hits: list[int] = []
    for i in range(len(text) - 7):
        # lea r64, [rip+disp32]: 48/4c 8d modrm ...
        if text[i] not in (0x48, 0x4C):
            continue
        if text[i + 1] != 0x8D:
            continue
        modrm = text[i + 2]
        if modrm & 0xC7 != 0x05:  # RIP-relative
            continue
        disp = struct.unpack_from("<i", text, i + 3)[0]
        insn_va = text_va + i
        next_ip = insn_va + 7
        resolved = next_ip + disp
        if resolved == target_va:
            hits.append(insn_va)
    return hits


def main() -> None:
    path = sys.argv[1]
    needle = sys.argv[2].encode()
    data = open(path, "rb").read()
    off = data.find(needle)
    if off < 0:
        raise SystemExit(f"needle not found: {needle!r}")
    image_base, sections = parse_pe(data)
    target_va = file_off_to_va(sections, image_base, off)
    if target_va is None:
        raise SystemExit("needle not in a mapped section")
    text = next(s for s in sections if s.name == ".text")
    text_bytes = data[text.raw : text.raw + text.size]
    text_va = image_base + text.va
    hits = scan_lea_xrefs(text_bytes, text_va, target_va)
    print(f"needle file_off=0x{off:X} va=0x{target_va:X}")
    print(f"xrefs={len(hits)}")
    for va in hits[:20]:
        rel = va - text_va
        print(f"  .text+0x{rel:X} (va 0x{va:X})")
        snippet = text_bytes[rel : rel + 48]
        print("   ", snippet.hex())


if __name__ == "__main__":
    main()

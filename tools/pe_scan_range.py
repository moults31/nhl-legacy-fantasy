#!/usr/bin/env python3
"""Scan PE .text for RIP-relative LEA/MOV targets in a VA range."""

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
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
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


def file_off_to_va(sections: list[Section], image_base: int, file_off: int) -> int:
    for sec in sections:
        if sec.raw <= file_off < sec.raw + sec.size:
            return image_base + sec.va + (file_off - sec.raw)
    raise ValueError(f"off 0x{file_off:x} unmapped")


def scan_rip_rel(text: bytes, text_va: int, lo: int, hi: int) -> list[tuple[int, int, bytes]]:
    hits: list[tuple[int, int, bytes]] = []
    i = 0
    while i < len(text) - 6:
        b0, b1 = text[i], text[i + 1]
        # REX.W + 8d/8b with modrm rip-relative (mod=00 rm=101)
        if b0 in (0x48, 0x4C, 0x49, 0x4D) and b1 in (0x8D, 0x8B):
            modrm = text[i + 2]
            if modrm & 0xC7 == 0x05:
                disp = struct.unpack_from("<i", text, i + 3)[0]
                insn_len = 7
                insn_va = text_va + i
                target = insn_va + insn_len + disp
                if lo <= target <= hi:
                    hits.append((insn_va, target, text[i : i + insn_len]))
                i += 7
                continue
        i += 1
    return hits


def main() -> None:
    path = sys.argv[1]
    lo_off = int(sys.argv[2], 16)
    hi_off = int(sys.argv[3], 16)
    data = open(path, "rb").read()
    image_base, sections = parse_pe(data)
    lo_va = file_off_to_va(sections, image_base, lo_off)
    hi_va = file_off_to_va(sections, image_base, hi_off)
    text = next(s for s in sections if s.name == ".text")
    text_bytes = data[text.raw : text.raw + text.size]
    text_va = image_base + text.va
    hits = scan_rip_rel(text_bytes, text_va, lo_va, hi_va)
    print(f"image_base=0x{image_base:X}")
    print(f"range file 0x{lo_off:X}..0x{hi_off:X} -> va 0x{lo_va:X}..0x{hi_va:X}")
    print(f"hits={len(hits)}")
    for insn_va, target, raw in hits[:40]:
        rel = insn_va - text_va
        print(f"  .text+0x{rel:X} -> 0x{target:X}  {raw.hex()}")


if __name__ == "__main__":
    main()

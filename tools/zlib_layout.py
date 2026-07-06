#!/usr/bin/env python3
"""Examine exact zlib layout: deflate size, Adler position, zero padding."""
import zlib as zl
import struct

def examine(name, path):
    with open(path, "rb") as f:
        data = f.read()
    zlib_stream = data[48:]
    
    # Find where the deflate actually ends
    # Decompress to check
    try:
        db = zl.decompress(zlib_stream)
        db_ok = True
    except Exception as e:
        db_ok = False
        db = b""
    
    # The actual deflate part: strip header and try to find bfinal
    # In deflate, we can scan for bfinal=1 block end
    # But easier: find where non-zero bytes end in the zlib (ignoring Adler)
    
    # Find the last non-zero byte before the final 4 (Adler) bytes
    last_nonzero = -1
    for i in range(len(zlib_stream) - 4):
        if zlib_stream[i] != 0:
            last_nonzero = i
    
    # The Adler should be at the end, 4 bytes before zlib end
    # But our padding may have shifted things
    stream_adler = struct.unpack(">I", zlib_stream[-4:])[0]
    computed_adler = zl.adler32(db) if db_ok else 0
    
    print(f"\n=== {name} ===")
    print(f"  Total zlib size: {len(zlib_stream)}")
    print(f"  Decompress OK: {db_ok}, DB size: {len(db)}")
    print(f"  Last non-zero byte at zlib offset: {last_nonzero}")
    print(f"  Stream Adler (last 4 bytes): 0x{stream_adler:08X}")
    print(f"  Computed Adler: 0x{computed_adler:08X}")
    print(f"  Adler matches: {stream_adler == computed_adler}")
    
    # Check: are the bytes just before the central zero region zero?
    # Look at bytes around the transition
    if last_nonzero > 0:
        ctx_start = max(0, last_nonzero - 16)
        ctx_end = min(len(zlib_stream), last_nonzero + 32)
        print(f"  Near end of deflate (offset {last_nonzero}):")
        print(f"    [{-4:>4}..{0:>4}]: {zlib_stream[ctx_start:ctx_end].hex()}")

examine("TRADEEDIT5", "_local/game-saves/xbox/TRADEEDIT5")
examine("T0_CLEAN", "_local/game-saves/xbox/T0_CLEAN.bin")
examine("T1_CRSB", "_local/game-saves/xbox/T1_CRSB.bin")

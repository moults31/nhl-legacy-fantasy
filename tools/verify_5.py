#!/usr/bin/env python3
"""Verify all 5 test saves decompress to correct DBs, and check .header validity."""
import zlib as zl, struct, os

BIN = "_local/game-saves/xbox"

tests = {
    "TRY_FL2":   "try_flate2.db",
    "TRY_FLIP":  "try_bitflip.db",
    "TRY_STD":   "try_std.db",
    "ORIG_CRSB": "orig_crsb.db",
    "ORIG_UNCH": "orig_unch.db",
}

for name, expected_db_path in tests.items():
    bin_path = f"{BIN}/{name}.bin"
    db_path = f"{BIN}/{expected_db_path}"
    
    with open(bin_path, "rb") as f:
        bin_zlib = f.read()[48:]
    with open(db_path, "rb") as f:
        expected = f.read()
    
    try:
        actual = zl.decompress(bin_zlib)
    except Exception as e:
        print(f"{name}: DECOMPRESS FAILED: {e}")
        continue
    
    match = actual == expected
    crosby = actual[0x0B949B]
    hedman = actual[0x0CAD1B]
    
    diffs = sum(1 for i in range(len(actual)) if actual[i] != expected[i]) if len(actual) == len(expected) else "LEN"
    
    print(f"{name}: match={match} diffs={diffs} Crosby=0x{crosby:02X} Hedman=0x{hedman:02X} ({'COL' if crosby==0x40 else 'orig'},{'COL' if hedman==0x40 else 'orig'})")

# Check .header file sizes
import glob
header_dir = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001"
for ts in ["20260308000301","20260308000302","20260308000303","20260308000401","20260308000402"]:
    hpath = os.path.join(header_dir, f"ROSTER {ts}.header")
    if os.path.exists(hpath):
        size = os.path.getsize(hpath)
        print(f"ROSTER {ts}.header: {size} bytes {'(EXPECTED ~328)' if size != 328 else '(CORRECT SIZE)'}")

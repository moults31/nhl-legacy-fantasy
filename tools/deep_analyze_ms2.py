#!/usr/bin/env python3
"""Second pass: deep analysis with correct team_alt interpretation and original save comparison."""
import struct, zlib as zl, os, re

BIN = "_local/game-saves/xbox"
SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BACKUP = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511\ROSTER 20260307213511"

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5_db = bytes(zl.decompress(f.read()[48:]))
with open(BACKUP, "rb") as f:
    orig_db = bytes(zl.decompress(f.read()[48:]))

RLB = 132
PROTEAM_OFF = 115
TEAM_ALT_OFF = 6

PLAYERS = {688: "Crosby", 695: "Ovechkin", 1232: "Hedman"}
crosby_base = 0x0B949B - PROTEAM_OFF
base = crosby_base - 688 * RLB

def proteam_team(pbyte):
    """Packed proteam byte (upper 5 bits) -> team ID (1-indexed)."""
    return (pbyte >> 3) & 0x1F

def team_alt_team(b):
    """Team_alt byte at record+6 -> team ID (full byte, 1-indexed)."""
    return b  # stored directly

def build_raw(db, edits):
    result = bytearray(db)
    for rec, pbyte in edits:
        result[base + rec * RLB + PROTEAM_OFF] = pbyte
        # Also update team_alt!
        tid = proteam_team(pbyte)
        result[base + rec * RLB + TEAM_ALT_OFF] = tid
    return bytes(result)

# ---- First: compare ORIGINAL vs TRADEEDIT5 ----
t5_raw = build_raw(t5_db, [])
orig_diffs = [(i, orig_db[i], t5_db[i]) for i in range(len(orig_db)) if orig_db[i] != t5_db[i]]
print("=" * 80)
print(f"ORIGINAL backup vs TRADEEDIT5: {len(orig_diffs)} byte diffs")
print("=" * 80)

# Show what TRADEEDIT5 changed from original
for off, ov, tv in orig_diffs:
    for rec, pname in PLAYERS.items():
        rs = base + rec * RLB
        byte_in_rec = off - rs
        if 0 <= byte_in_rec < RLB:
            if byte_in_rec == PROTEAM_OFF:
                ot = proteam_team(ov)
                tt = proteam_team(tv)
                print(f"  0x{off:06X} {pname}[+{byte_in_rec}] proteam: team {ot} -> {tt}")
            elif byte_in_rec == TEAM_ALT_OFF:
                print(f"  0x{off:06X} {pname}[+{byte_in_rec}] team_alt: {ov} -> {tv}")
            else:
                print(f"  0x{off:06X} {pname}[+{byte_in_rec}]: 0x{ov:02X} -> 0x{tv:02X}")
            break
    else:
        print(f"  0x{off:06X} (non-player): 0x{ov:02X} -> 0x{tv:02X}")

# ---- Second: MS noedit vs TRADEEDIT5 ----
ms_noedit_path = os.path.join(SRC, "default_ms_noedit.db")
with open(ms_noedit_path, "rb") as f:
    ms_noedit = f.read()

ms_noedit_diffs = [(i, ms_noedit[i], t5_db[i]) for i in range(len(ms_noedit)) if ms_noedit[i] != t5_db[i]]
print(f"\n{'='*80}")
print(f"MS noedit vs TRADEEDIT5: {len(ms_noedit_diffs)} byte diffs")
print(f"{'='*80}")

for off, mv, tv in orig_diffs:
    for rec, pname in PLAYERS.items():
        rs = base + rec * RLB
        byte_in_rec = off - rs
        if 0 <= byte_in_rec < RLB:
            if byte_in_rec == PROTEAM_OFF:
                ot = proteam_team(ov)
                tt = proteam_team(tv)
                print(f"  0x{off:06X} {pname}[+{byte_in_rec}] proteam: team {ot}->{tt} (T5)")

# ---- KEY TEST: build raw edit WITH team_alt, compare to MS ----
print(f"\n{'='*80}")
print("KEY: does raw edit WITH team_alt match MS?")
print(f"{'='*80}")

for key, edits in [
    ("noedit", []),
    ("crsb_col", [(688, 0x40)]),
    ("crsb_cgy", [(688, 0x28)]),
    ("ovi_col", [(695, 0x40)]),
    ("ovi_cgy", [(695, 0x28)]),
]:
    pattern = key.replace("_", ".*")
    fpath = None
    for fn in os.listdir(SRC):
        if re.search(key, fn) and not fn.endswith(".bak"):
            fpath = os.path.join(SRC, fn)
            break
    if not fpath:
        print(f"  {key}: FILE NOT FOUND")
        continue
    
    with open(fpath, "rb") as f:
        ms = f.read()
    
    raw = build_raw(t5_db, edits)
    diffs = [(i, ms[i], raw[i]) for i in range(len(ms)) if ms[i] != raw[i]]
    
    if len(diffs) == 0:
        print(f"  {key}: PERFECT MATCH! Raw edit + team_alt == MS output")
    else:
        print(f"  {key}: {len(diffs)} remaining diffs")
        for off, mv, rv in diffs:
            # Categorize
            for rec, pname in PLAYERS.items():
                rs = base + rec * RLB
                if rs <= off < rs + RLB:
                    print(f"    0x{off:06X} {pname}[+{off-rs}]: raw=0x{rv:02X} ms=0x{mv:02X}")
                    break
            else:
                print(f"    0x{off:06X} (non-player): raw=0x{rv:02X} ms=0x{mv:02X}")

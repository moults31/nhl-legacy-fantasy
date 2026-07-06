#!/usr/bin/env python3
"""Deep analysis of all MS-edited DBs to reverse-engineer Modding Studio's changes."""
import struct, zlib as zl, os, re

BIN = "_local/game-saves/xbox"
SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5_db = bytes(zl.decompress(f.read()[48:]))

# Player record info (from ea-tdb dump_wbbd_byte_layout)
# proteam at bit_offset=920 (byte 115 from record start)
# record_length = 132 bytes
RLB = 132
PROTEAM_OFF = 115
TEAM_ALT_OFF = 6

PLAYERS = {
    688:  "Crosby",
    695:  "Ovechkin",
    1232: "Hedman",
}

# Compute table base
crosby_base = 0x0B949B - PROTEAM_OFF  # 0x0B949B - 115 = 0x0B9428
base = crosby_base - 688 * RLB

print(f"cPbu base = 0x{base:06X}")
print(f"Record length = {RLB}")

# Edit specifications
edit_specs = {
    "noedit":        [],
    "crsb_col":      [(688, 0x40)],
    "crsb_cgy":      [(688, 0x28)],
    "ovi_col":       [(695, 0x40)],
    "ovi_cgy":       [(695, 0x28)],
    "crsbcol_ovicgy":[(688, 0x40), (695, 0x28)],
    "crsbcgy_ovicol":[(688, 0x28), (695, 0x40)],
}

def build_raw(db, edits):
    result = bytearray(db)
    for rec, pbyte in edits:
        result[base + rec * RLB + PROTEAM_OFF] = pbyte
    return bytes(result)

def team_from_proteam(pbyte):
    """proteam byte (5 bits upper, WfTt lower 3) -> team id (1-indexed)."""
    return (pbyte >> 3) & 0x1F

# Match files
file_map = {}
for fname in os.listdir(SRC):
    if not fname.endswith(".db") or ".bak" in fname:
        continue
    n = fname.replace("default_", "").replace(".db", "")
    for key in edit_specs:
        pat = key.replace("_", ".*")
        if re.search(key, n):
            file_map[key] = os.path.join(SRC, fname)
            break

# Now analyze each
all_diffs = {}  # key -> list of (offset, ms_val, raw_val)

for key in edit_specs:
    if key not in file_map:
        print(f"MISSING: {key}")
        continue
    
    with open(file_map[key], "rb") as f:
        ms = f.read()
    raw = build_raw(t5_db, edit_specs[key])
    assert len(ms) == len(raw)
    
    diffs = [(i, ms[i], raw[i]) for i in range(len(ms)) if ms[i] != raw[i]]
    all_diffs[key] = diffs

# --- ANALYSIS ---
print("\n" + "="*80)
print("1. PER-PLAYER TEAM_ALT BYTE (record_offset + 6)")
print("="*80)

for key in edit_specs:
    if key not in all_diffs:
        continue
    diffs = all_diffs[key]
    print(f"\n{key}:")
    edited_recs = [r for r, _ in edit_specs[key]]
    for off, mv, rv in diffs:
        for rec, pname in PLAYERS.items():
            rs = base + rec * RLB
            if off == rs + TEAM_ALT_OFF:
                t_old = team_from_proteam(rv)
                t_new = team_from_proteam(mv)
                note = " (EXPLICITLY EDITED)" if rec in edited_recs else " (COLLATERAL)"
                print(f"  {pname}[+6] 0x{off:06X}: team {t_old} -> {t_new}{note}")

print("\n" + "="*80)
print("2. SHARED NORMALIZATION BYTES (same across ALL MS saves)")
print("="*80)

# Find offsets that appear in ALL diffs
if all_diffs:
    first_key = list(all_diffs.keys())[0]
    common = set(off for off, _, _ in all_diffs[first_key])
    for key in all_diffs:
        common &= set(off for off, _, _ in all_diffs[key])
    
    # Remove the player-specific bytes
    player_offsets = set()
    for rec in PLAYERS:
        rs = base + rec * RLB
        player_offsets.add(rs + TEAM_ALT_OFF)
    common -= player_offsets
    
    print(f"Bytes changed by MS in all {len(all_diffs)} saves (excluding player team_alt):")
    for off in sorted(common)[:30]:
        # Find values from one example
        ex_key = list(all_diffs.keys())[0]
        for o, mv, rv in all_diffs[ex_key]:
            if o == off:
                print(f"  0x{off:06X}: raw_T5=0x{rv:02X}  ms_all=0x{mv:02X}")

print("\n" + "="*80)
print("3. PER-SAVE UNIQUE DIFFS (vary by save, not normalization)")
print("="*80)

# Bytes that are NOT in all saves, and NOT player team_alt
for key in edit_specs:
    if key not in all_diffs:
        continue
    diffs = all_diffs[key]
    
    player_offsets = set()
    for rec in PLAYERS:
        rs = base + rec * RLB
        player_offsets.add(rs + TEAM_ALT_OFF)
    
    unique = []
    for off, mv, rv in diffs:
        if off in player_offsets:
            continue
        # Check if this offset appears in all saves
        appears_in_all = all(off in set(o for o,_,_ in all_diffs[k]) for k in all_diffs)
        if appears_in_all:
            continue
        unique.append((off, mv, rv))
    
    if unique:
        print(f"\n{key}:")
        for off, mv, rv in unique[:20]:
            # Try to locate which player record this is in
            loc = ""
            for rec, pname in PLAYERS.items():
                rs = base + rec * RLB
                if rs <= off < rs + RLB:
                    loc = f" [{pname}[{off-rs}]"
            print(f"  0x{off:06X}: raw=0x{rv:02X} ms=0x{mv:02X}{loc}")

print("\n" + "="*80)
print("4. CRC-LIKE 4-BYTE CLUSTERS")
print("="*80)

for key in edit_specs:
    if key not in all_diffs:
        continue
    diffs = all_diffs[key]
    # Group aligned 4-byte runs
    aligned_runs = {}
    for off, mv, rv in diffs:
        a = off & ~3
        if a not in aligned_runs:
            aligned_runs[a] = []
        aligned_runs[a].append((off - a, mv, rv))
    
    four_byte_runs = {a: v for a, v in aligned_runs.items() if len(v) == 4}
    if four_byte_runs:
        print(f"\n{key}:")
        for a in sorted(four_byte_runs.keys()):
            raw_val = struct.unpack("<I", bytes(b[2] for b in sorted(four_byte_runs[a])))[0]
            ms_val = struct.unpack("<I", bytes(b[1] for b in sorted(four_byte_runs[a])))[0]
            print(f"  0x{a:06X}: raw_T5=0x{raw_val:08X} ms=0x{ms_val:08X}")

print("\n" + "="*80)
print("5. HEDMAN COLLATERAL CHANGE")
print("="*80)
for key in sorted(all_diffs.keys()):
    diffs = all_diffs[key]
    hed_rs = base + 1232 * RLB
    changes = [(off, mv, rv) for off, mv, rv in diffs if hed_rs <= off < hed_rs + RLB]
    if changes:
        print(f"\n{key}: Hedman changes ({len(changes)}):")
        for off, mv, rv in changes:
            print(f"  0x{off:06X}[+{off-hed_rs}]: 0x{rv:02X} -> 0x{mv:02X}")

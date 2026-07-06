#!/usr/bin/env python3
"""Deep analysis: MS edits starting from default.db (TRADEEDIT5 + Hedman->COL)."""

import struct, zlib as zl, os, re

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"

# default.db = TRADEEDIT5 + Hedman->COL
with open(os.path.join(SRC, "default.db"), "rb") as f:
    baseline = f.read()
print(f"Baseline (default.db): {len(baseline)} bytes")

RLB = 132
PROTEAM_OFF = 115
TEAM_ALT_OFF = 6
PLAYERS = {688: "Crosby", 695: "Ovechkin", 1232: "Hedman"}
base = 0x0B9428 - 688 * RLB  # as computed earlier: 0x0A3168

# Confirm baseline player state
print("\nBaseline player state:")
for rec, pname in PLAYERS.items():
    rs = base + rec * RLB
    pt = (baseline[rs+PROTEAM_OFF] >> 3) & 0x1F
    ta = baseline[rs+TEAM_ALT_OFF]
    print(f"  {pname}: proteam={pt:2d}  team_alt={ta:2d}")

# Load all MS-edited files
edits = {}
for fn in os.listdir(SRC):
    if not fn.endswith(".db") or ".bak" in fn:
        continue
    n = fn.replace("default_", "").replace(".db", "")
    for key, pat in [
        ("ms_noedit", r"ms_noedit"),
        ("crsb_col", r"ms_crsb_col"),
        ("crsb_cgy", r"ms_crsb_cgy"),
        ("ovi_col", r"ms_ovi_col"),
        ("ovi_cgy", r"ms_ovi_cgy"),
        ("crsbcol_ovicgy", r"crsb_col_ovi_cgy"),
        ("crsbcgy_ovicol", r"crsb_cgy_ovi_col"),
    ]:
        if re.search(pat, n):
            with open(os.path.join(SRC, fn), "rb") as f:
                edits[key] = f.read()
            print(f"Loaded {key} from {fn}")
            break

# Now build "raw" versions: apply ONLY proteam changes to baseline
# team_alt changes will show as diffs
team_map = {
    "ms_noedit": [],
    "crsb_col": [(688, 0x40)],       # Crosby -> COL (team 8)
    "crsb_cgy": [(688, 0x28)],       # Crosby -> CGY (team 5)
    "ovi_col": [(695, 0x40)],        # Ovechkin -> COL
    "ovi_cgy": [(695, 0x28)],        # Ovechkin -> CGY
    "crsbcol_ovicgy": [(688, 0x40), (695, 0x28)],  # Crosby->COL, Ovi->CGY
    "crsbcgy_ovicol": [(688, 0x28), (695, 0x40)],  # Crosby->CGY, Ovi->COL
}

def build_raw(edits_list):
    result = bytearray(baseline)
    for rec, pbyte in edits_list:
        result[base + rec * RLB + PROTEAM_OFF] = pbyte
    return bytes(result)

# Categorize ALL diffs
print("\n" + "="*80)
print("COMPLETE DIFF CATEGORIZATION (MS vs baseline)")
print("="*80)

# Collect ALL bytes that differ in ANY save
all_diff_offsets = set()
per_save_diffs = {}  # key -> {(offset, ms_val, raw_val)}

for key in edits:
    ms = edits[key]
    raw = build_raw(team_map[key])
    diffs = {(i, ms[i], raw[i]) for i in range(len(ms)) if ms[i] != raw[i]}
    per_save_diffs[key] = diffs
    all_diff_offsets |= {off for off, _, _ in diffs}

print(f"\nTotal unique offset positions across all saves: {len(all_diff_offsets)}")

# Categorize each offset
player_offsets = {}
for rec, pname in PLAYERS.items():
    rs = base + rec * RLB
    for off in range(rs, rs + RLB):
        player_offsets[off] = (pname, off - rs)

# Group offsets by what they are
proteam_offsets = {base + rec * RLB + PROTEAM_OFF for rec in PLAYERS}
team_alt_offsets = {base + rec * RLB + TEAM_ALT_OFF for rec in PLAYERS}

# 1. TEAM_ALT changes (the key finding)
print("\n" + "-"*60)
print("1. TEAM_ALT BYTES (record_offset +6)")
print("-"*60)
for off in sorted(all_diff_offsets):
    if off in team_alt_offsets:
        for rec, pname in PLAYERS.items():
            if off == base + rec * RLB + TEAM_ALT_OFF:
                print(f"\n  {pname} at 0x{off:06X}:" % locals())
                print(f"    baseline: team_alt={baseline[off]:2d} (0x{baseline[off]:02X})")
                for key in sorted(edits):
                    ms = edits[key]
                    if key in per_save_diffs and off in {o for o,_,_ in per_save_diffs[key]}:
                        edits_spec = team_map[key]
                        edited_recs = [r for r,_ in edits_spec]
                        in_edits = "EXPLICITLY EDITED" if rec in edited_recs else "COLLATERAL"
                        print(f"    {key:20}: team_alt={ms[off]:2d}  ({in_edits})")
                    else:
                        print(f"    {key:20}: (same as baseline)")

# 2. PROTEAM changes  
print("\n" + "-"*60)
print("2. PROTEAM BYTES (record_offset +115)")
print("-"*60)
for off in sorted(all_diff_offsets):
    if off in proteam_offsets:
        for rec, pname in PLAYERS.items():
            if off == base + rec * RLB + PROTEAM_OFF:
                print(f"\n  {pname} at 0x{off:06X}:")
                print(f"    baseline: proteam=byte 0x{baseline[off]:02X}")
                for key in sorted(edits):
                    ms = edits[key]
                    if key in per_save_diffs and off in {o for o,_,_ in per_save_diffs[key]}:
                        tid = (ms[off] >> 3) & 0x1F
                        print(f"    {key:20}: proteam byte=0x{ms[off]:02X} team={tid}")
                    else:
                        print(f"    {key:20}: (same as baseline)")

# 3. Other player record bytes
print("\n" + "-"*60)
print("3. OTHER PLAYER RECORD BYTE DIFFS")
print("-"*60)
for off in sorted(all_diff_offsets):
    if off in proteam_offsets or off in team_alt_offsets:
        continue
    if off in player_offsets:
        pname, byte_in_rec = player_offsets[off]
        print(f"\n  {pname}[+{byte_in_rec}] at 0x{off:06X}: baseline=0x{baseline[off]:02X}")
        for key in sorted(edits):
            ms = edits[key]
            if key in per_save_diffs and off in {o for o,_,_ in per_save_diffs[key]}:
                print(f"    {key:20}: 0x{ms[off]:02X}")
            else:
                print(f"    {key:20}: (same as baseline)")

# 4. NON-PLAYER (normalization and CRC) diffs
print("\n" + "-"*60)
print("4. NON-PLAYER DIFFS (normalization/CRC)")
print("-"*60)

non_player = {}
for off in sorted(all_diff_offsets):
    if off in player_offsets:
        continue
    # How many saves have this diff?
    saves_with = set()
    save_vals = set()
    for key in edits:
        ms = edits[key]
        if ms[off] != baseline[off]:
            saves_with.add(key)
            save_vals.add(ms[off])
    
    # Is this same across ALL saves (normalization)?
    if len(saves_with) == 0:
        continue
    
    cat = "VARIES per save" if len(save_vals) > 1 else f"ALL={list(save_vals)[0]:02X}"
    print(f"  0x{off:06X}: baseline=0x{baseline[off]:02X}  in {len(saves_with)}/{len(edits)} saves  [{cat}]")

# 5. CRC verification
print("\n" + "-"*60)
print("5. CRC ANALYSIS (4-byte aligned blocks)")
print("-"*60)

crc_addrs = [0x1A4838, 0x1AB258, 0x1D5F2C]
for a in crc_addrs:
    print(f"\n  u32 at 0x{a:06X}:")
    print(f"    baseline = 0x{struct.unpack('<I', baseline[a:a+4])[0]:08X}")
    for key in sorted(edits):
        ms = edits[key]
        val = struct.unpack("<I", ms[a:a+4])[0]
        print(f"    {key:20}: 0x{val:08X}")

# 6. Per-diff that varies between saves - identify what it encodes
print("\n" + "-"*60)
print("6. PER-SAVE PATTERN ANALYSIS (variable non-player bytes)")
print("-"*60)

# Find the variable non-player bytes and correlate with team assignments
variable_offsets = []
for off in sorted(all_diff_offsets):
    if off in player_offsets:
        continue
    save_vals = set()
    for key in edits:
        ms = edits[key]
        if ms[off] != baseline[off]:
            save_vals.add(ms[off])
    if len(save_vals) > 1:
        variable_offsets.append(off)

if variable_offsets:
    # Group consecutive variable offsets
    groups = []
    cur = [variable_offsets[0]]
    for off in variable_offsets[1:]:
        if off == cur[-1] + 1:
            cur.append(off)
        else:
            groups.append(cur)
            cur = [off]
    groups.append(cur)
    
    print(f"\n  {len(variable_offsets)} variable bytes in {len(groups)} groups:\n")
    for g in groups:
        print(f"  Group at 0x{g[0]:06X}-0x{g[-1]:06X} ({len(g)} bytes):")
        for off in g:
            vals = ""
            for key in sorted(edits):
                ms = edits[key]
                vals += f" {key[:15]:15}=0x{ms[off]:02X}"
            print(f"    0x{off:06X}: baseline=0x{baseline[off]:02X} {vals}")
        # Try interpreting as team assignments 
        print()

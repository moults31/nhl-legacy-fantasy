#!/usr/bin/env python3
"""Minimal test: modify Bergeron proteam WITHOUT resealing TDB CRCs."""
import json, shutil, struct, subprocess, sys
from datetime import datetime, UTC
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "_local/game-saves/xbox/TRADEEDIT5"
WORK = REPO / "_local/game-saves/checkpoint"
WORK.mkdir(parents=True, exist_ok=True)

BASELINE_DB = WORK / "noreseal_baseline.db"
BASELINE_JSON = WORK / "noreseal_baseline.json"
EDITED_DB = WORK / "noreseal_edited.db"
PATCH_JSON = WORK / "noreseal_patch.json"
PACKED_BIN = WORK / "noreseal_packed.bin"
TIMESTAMP = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
NAME = "BERGNRSL"

def cargo(args):
    cmd = ["cargo", "run", "-p", "roster-cli", "--"] + args
    print(f"  $ {' '.join(args)}", flush=True)
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr)
        sys.exit(p.returncode)
    for line in p.stderr.strip().splitlines():
        print(f"    {line}")

# Step 1: Unpack
print("[1] Unpack TRADEEDIT5")
cargo(["unpack", str(SOURCE), "-o", str(BASELINE_DB)])

# Step 2: Export
print("[2] Export baseline JSON")
cargo(["export", str(BASELINE_DB), "-o", str(BASELINE_JSON)])

with open(BASELINE_JSON, encoding="utf-8") as f:
    baseline = json.load(f)

# Find Bergeron
bergeron = None
for p in baseline["players"]:
    if p["first_name"].lower() == "patrice" and p["last_name"].lower() == "bergeron":
        bergeron = p
        break
if not bergeron:
    sys.exit("Bergeron not found")

# Find Colorado
colorado = None
for t in baseline["teams"]:
    if t["city"].lower() == "colorado":
        colorado = t
        break
if not colorado:
    sys.exit("Colorado not found")

dest_id = colorado["record"] + 1  # 1-indexed proteam
print(f"  Bergeron record={bergeron['record']}, current proteam={bergeron['proteam']}")
print(f"  Colorado record={colorado['record']}, proteam ID={dest_id}")

# Step 3: Write patch
patch = {
    "schema": "nhl-legacy-roster/0.1",
    "teams": [],
    "players": [{
        "record": bergeron["record"],
        "first_name": bergeron["first_name"],
        "last_name": bergeron["last_name"],
        "proteam": dest_id,
    }]
}
with open(PATCH_JSON, "w", encoding="utf-8") as f:
    json.dump(patch, f, indent=2)

# Step 4: Import (NO RESEAL!)
print("[4] Import proteam patch (NO RESEAL)")
cargo(["import", str(BASELINE_DB), str(PATCH_JSON), "-o", str(EDITED_DB)])

# Verify the import
print("[5] Verify import")
cargo(["export", str(EDITED_DB), "-o", str(WORK / "noreseal_verify.json")])
with open(WORK / "noreseal_verify.json", encoding="utf-8") as f:
    verify = json.load(f)
for p in verify["players"]:
    if p["record"] == bergeron["record"]:
        if p["proteam"] == dest_id:
            print(f"  OK: Bergeron proteam={p['proteam']} (Colorado)")
        else:
            sys.exit(f"FAIL: Bergeron proteam={p['proteam']}, expected {dest_id}")
        break

# Step 5: Pack (use TRADEEDIT5 as template with its @0x2c)
print("[6] Pack")
with open(SOURCE, "rb") as f:
    hdr = f.read(48)
field_0x2c = struct.unpack_from(">I", hdr, 0x2C)[0]
print(f"  @0x2c = 0x{field_0x2c:08X}")
cargo([
    "pack", str(EDITED_DB), str(SOURCE),
    "--field-0x2c", f"0x{field_0x2c:08X}",
    "-o", str(PACKED_BIN),
])

# Step 6: Verify round-trip
print("[7] Verify round-trip")
cargo(["unpack", str(PACKED_BIN), "-o", str(WORK / "noreseal_roundtrip.db")])
rt = (WORK / "noreseal_roundtrip.db").read_bytes()
ed = EDITED_DB.read_bytes()
if rt == ed:
    print("  round-trip OK")
else:
    sys.exit(f"round-trip FAIL: {len(rt)} vs {len(ed)} bytes, {sum(1 for a,b in zip(rt,ed) if a!=b)} diffs")

# Step 7: Install
print("[8] Install")
installer = REPO / "tools/install_recomp_roster.py"
header_dir = Path.home() / "Documents/nhllegacy/B13EBABEBABEBABE/454109EC/Headers/00000001"
template = None
for n in ["BUILDYOURAI 20260705061804.header", "PROFILE 20260702052022.header"]:
    h = header_dir / n
    if h.is_file():
        template = h
        break

args = [sys.executable, str(installer), str(PACKED_BIN),
        "--timestamp", TIMESTAMP, "--name", NAME]
if template:
    args.extend(["--template-header", str(template)])
subprocess.run(args, cwd=REPO, check=True)

print(f"\nInstalled as: {NAME} (folder timestamp {TIMESTAMP})")
print(f"Load in-game: Customize -> Load -> Roster -> Refresh -> {NAME}")

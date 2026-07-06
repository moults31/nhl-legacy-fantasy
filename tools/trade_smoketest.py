#!/usr/bin/env python3
"""Run a single pass of the full roster trade pipeline as a smoketest.

Pick 3 NHL superstars, move them between teams via the Rust toolchain,
generate an HTML diff report, pack a loadable roster save, and install it
into the NHL Legacy save tree.

This is a developer smoke test — not a user-facing tool.  It exercises the
entire unpack → export → patch → import → reseal → pack → install pipeline
and generates a self-contained HTML report for visual inspection.
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path

# ── configuration ────────────────────────────────────────────────────────

REPO = Path(__file__).resolve().parents[1]

# Players to move: (first_name, last_name, destination_city)
TRADES = [
    ("Connor", "McDavid", "Toronto"),
    ("Auston", "Matthews", "Edmonton"),
    ("Nathan", "MacKinnon", "Boston"),
]

# Source roster save.  Pick the first available.  TRADEEDIT5 is preferred
# because it's known to load in-game; the generic fixture may cause profile
# mismatches on the PRESS START screen.
_SOURCE_CANDIDATES = [
    "_local/game-saves/xbox/TRADEEDIT5",
    "_local/game-saves/xbox/roster1.bin",
    "_local/game-saves/xbox/testroster.bin",
]
SOURCE_SAVE = next((c for c in _SOURCE_CANDIDATES if (REPO / c).is_file()), None)
if SOURCE_SAVE is None:
    sys.exit("no source roster save found. Checked: " + ", ".join(_SOURCE_CANDIDATES))

# Output directory for intermediate files and the HTML report.
WORK_DIR = "_local/game-saves/checkpoint"

# In-game display name for the new roster.
ROSTER_DISPLAY_NAME = "CHKTRADE"

# Timestamp (14-digit) for the save folder name.
TIMESTAMP = datetime.now(UTC).strftime("%Y%m%d%H%M%S")


# ── helpers ───────────────────────────────────────────────────────────────


def run(*args: str) -> None:
    """Run a command and exit on failure."""
    print(f"\n  $ {' '.join(args)}", file=sys.stderr, flush=True)
    proc = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        sys.exit(f"command failed with code {proc.returncode}: {' '.join(args)}")
    if proc.stderr.strip():
        for line in proc.stderr.strip().splitlines():
            print(f"    {line}", file=sys.stderr)


def cargo(subcmd_args: list[str]) -> None:
    """Run `cargo run -p roster-cli -- <args>`."""
    run("cargo", "run", "-p", "roster-cli", "--", *subcmd_args)


def resolve_team_id(teams: list[dict], city: str) -> int:
    """Find a team proteam value by city name (case-insensitive).

    Returns the proteam value (record_index + 1), not the raw record index.
    """
    city_lower = city.lower()
    for t in teams:
        if t["city"].lower() == city_lower:
            return t["record"] + 1
    candidates = [t["city"] for t in teams if city_lower in t["city"].lower()]
    sys.exit(f"team '{city}' not found in team list. Candidates: {candidates}")


def read_field_0x2c(save_path: Path) -> str:
    """Read the @0x2c field from a RosterFile header."""
    with open(save_path, "rb") as f:
        header = f.read(48)
    if len(header) < 48:
        sys.exit(f"{save_path}: too short for RosterFile header")
    value = struct.unpack_from(">I", header, 0x2C)[0]
    return f"0x{value:08X}"


def find_installer() -> str:
    """Return the path to the best available install script."""
    # Prefer Windows recomp installer since we're on Windows.
    script = REPO / "tools" / "install_recomp_roster.py"
    if script.is_file():
        return str(script)
    # Fall back to Proton installer.
    script = REPO / "tools" / "install_m5_saves.py"
    if script.is_file():
        return str(script)
    sys.exit("no install script found (install_recomp_roster.py or install_m5_saves.py)")


def find_template_header() -> Path | None:
    """Find a .header sidecar to use as template, preferring the recomp save tree."""
    base = Path.home() / "Documents/nhllegacy/B13EBABEBABEBABE/454109EC/Headers/00000001"
    if not base.is_dir():
        return None
    # Any .header file in the tree works for metadata cloning — try common names.
    for name in (
        "BUILDYOURAI 20260705004003.header",
        "BUILDYOURAI 20260705060521.header",
        "HOCKEYCARD 20260701232214.header",
        "ROSTER 20260307213511.header",
        "PROFILE 20260702052022.header",
    ):
        p = base / name
        if p.is_file():
            return p
    # Last resort: grab the first .header we find.
    for p in base.iterdir():
        if p.suffix == ".header":
            return p
    return None


# ── HTML diff report ──────────────────────────────────────────────────────

def build_html_diff(
    baseline: dict,
    edited: dict,
    trades: list[tuple[str, str, str, int]],
    out_path: Path,
) -> None:
    """Generate a self-contained HTML roster diff."""
    # Build lookups
    team_by_record: dict[int, dict] = {
        t["record"]: t for t in baseline["teams"]
    }
    player_by_record: dict[int, dict] = {
        p["record"]: p for p in baseline["players"]
    }
    edited_by_record: dict[int, dict] = {
        p["record"]: p for p in edited["players"]
    }

    changed_records = {p["record"] for p in edited["players"]
                       if player_by_record.get(p["record"], {}).get("proteam") != p["proteam"]}

    trade_names = {(t[0].lower(), t[1].lower()) for t in trades}  # (first, last)

    def team_name(proteam_id: int) -> str:
        t = team_by_record.get(proteam_id, {})
        return t.get("abbrev", "") or t.get("city", "") or f"#{proteam_id}"

    html_parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>",
        "<title>Roster Trade Diff</title>",
        "<style>",
        "body { font-family: system-ui, sans-serif; margin: 2em; background: #f8f9fa; color: #212529; }",
        "h1 { margin-bottom: 0.2em; }",
        "h2 { margin-top: 2em; }",
        ".summary { color: #6c757d; margin-bottom: 1.5em; }",
        "table { border-collapse: collapse; width: 100%; margin-bottom: 1.5em; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }",
        "th, td { padding: 6px 10px; text-align: left; border-bottom: 1px solid #dee2e6; font-size: 13px; }",
        "th { background: #343a40; color: #fff; position: sticky; top: 0; }",
        "tr:hover { background: #f1f3f5; }",
        ".changed { background: #fff3cd !important; }",
        ".changed:hover { background: #ffe69c !important; }",
        ".trade-hero { background: #d4edda !important; }",
        ".before { color: #dc3545; }",
        ".after { color: #28a745; font-weight: bold; }",
        "</style></head><body>",
        f"<h1>Roster Trade Smoke Test</h1>",
        f"<p class='summary'>"
        f"Source: {SOURCE_SAVE}<br>"
        f"Timestamp: {TIMESTAMP}<br>"
        f"Display name: {ROSTER_DISPLAY_NAME}<br>"
        f"Players moved: {len(TRADES)}<br>"
        f"Total players exported: {len(baseline['players'])} | Total teams: {len(baseline['teams'])}"
        f"</p>",
        "<h2>Trades Applied</h2>",
        "<table><tr><th>Player</th><th>From</th><th>To</th></tr>",
    ]

    for first, last, dest_city, dest_id in trades:
        # Find the player record in the edited set, then look up the old proteam from baseline.
        player_rec = None
        for p in edited["players"]:
            if p.get("first_name", "").lower() == first.lower() and p.get("last_name", "").lower() == last.lower():
                player_rec = p["record"]
                break
        old_id = player_by_record.get(player_rec, {}).get("proteam", 0) if player_rec is not None else 0
        html_parts.append(
            f"<tr class='trade-hero'>"
            f"<td>{first} {last}</td>"
            f"<td class='before'>{team_name(old_id)}</td>"
            f"<td class='after'>{team_name(dest_id)}</td>"
            f"</tr>"
        )
    html_parts.append("</table>")

    # Team table
    html_parts.append("<h2>NHL Teams</h2>")
    html_parts.append("<table><tr><th>Rec</th><th>City</th><th>Abbrev</th><th>Full Name</th></tr>")
    for t in baseline["teams"]:
        html_parts.append(
            f"<tr><td>{t['record']}</td><td>{t['city']}</td>"
            f"<td>{t.get('abbrev','') or ''}</td><td>{t.get('full_name','') or ''}</td></tr>"
        )
    html_parts.append("</table>")

    # Player table
    html_parts.append("<h2>All Players</h2>")
    html_parts.append(
        "<table><tr><th>Rec</th><th>First</th><th>Last</th>"
        "<th>Proteam</th><th>New Proteam</th></tr>"
    )
    for p in baseline["players"]:
        rec = p["record"]
        new_p = edited_by_record.get(rec, p)
        old_t = p["proteam"]
        new_t = new_p["proteam"]
        css = "changed" if rec in changed_records else ""
        name_key = (p["first_name"], p["last_name"])
        if name_key[0].lower() in {t[0].lower() for t in trade_names} and \
           name_key[1].lower() in {t[1].lower() for t in trade_names}:
            css += " trade-hero"

        html_parts.append(
            f"<tr class='{css}'>"
            f"<td>{rec}</td><td>{p['first_name']}</td><td>{p['last_name']}</td>"
            f"<td>{team_name(old_t)}</td>"
        )
        if rec in changed_records:
            html_parts.append(f"<td class='after'>{team_name(new_t)}</td>")
        else:
            html_parts.append("<td></td>")
        html_parts.append("</tr>")
    html_parts.append("</table></body></html>")

    out_path.write_text("\n".join(html_parts), encoding="utf-8")
    print(f"\n  wrote HTML diff: {out_path}")


# ── main pipeline ─────────────────────────────────────────────────────────

def main() -> None:
    source_path = REPO / SOURCE_SAVE
    if not source_path.is_file():
        sys.exit(f"source save not found: {source_path}")

    work = REPO / WORK_DIR
    work.mkdir(parents=True, exist_ok=True)

    baseline_db = work / "baseline.db"
    baseline_json = work / "baseline.json"
    patch_json = work / "patch.json"
    edited_db = work / "edited.db"
    edited_json = work / "edited.json"
    diff_html = work / "roster_diff.html"
    packed_bin = work / "checkpoint_roster.bin"

    print("=" * 60, file=sys.stderr)
    print("  ROSTER TRADE SMOKE TEST", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # ── step 1: unpack ────────────────────────────────────────────────
    print("\n[1/8] Unpack roster save", file=sys.stderr)
    cargo(["unpack", str(source_path), "-o", str(baseline_db)])

    # ── step 2: export baseline ───────────────────────────────────────
    print("\n[2/8] Export baseline roster JSON", file=sys.stderr)
    cargo(["export", str(baseline_db), "-o", str(baseline_json)])

    with open(baseline_json, encoding="utf-8") as f:
        baseline = json.load(f)

    teams = baseline["teams"]
    print(f"  exported {len(baseline['players'])} players, {len(teams)} teams")

    # ── step 3: resolve team IDs ──────────────────────────────────────
    print("\n[3/8] Resolve team IDs for trades", file=sys.stderr)
    trades_with_ids: list[tuple[str, str, str, int]] = []
    for first, last, dest_city in TRADES:
        dest_id = resolve_team_id(teams, dest_city)
        trades_with_ids.append((first, last, dest_city, dest_id))
        print(f"  {first} {last} -> #{dest_id} ({dest_city})")

    # ── step 4: write patch JSON ──────────────────────────────────────
    print("\n[4/8] Generate patch JSON", file=sys.stderr)
    patch = {
        "schema": "nhl-legacy-roster/0.1",
        "teams": [],
        "players": [],
    }

    for first, last, dest_city, dest_id in trades_with_ids:
        rec = None
        for p in baseline["players"]:
            if p["first_name"].lower() == first.lower() and p["last_name"].lower() == last.lower():
                rec = p["record"]
                break
        if rec is None:
            sys.exit(f"player not found in baseline: {first} {last}")
        patch["players"].append({
            "record": rec,
            "first_name": first,
            "last_name": last,
            "proteam": dest_id,
        })

    with open(patch_json, "w", encoding="utf-8") as f:
        json.dump(patch, f, indent=2)
    print(f"  wrote {patch_json}")

    # ── step 5: import patches ────────────────────────────────────────
    print("\n[5/8] Import proteam patches", file=sys.stderr)
    cargo(["import", str(baseline_db), str(patch_json), "-o", str(edited_db)])

    # ── step 6: reseal TDB CRCs ───────────────────────────────────────
    print("\n[6/8] Reseal TDB internal CRCs", file=sys.stderr)
    cargo(["reseal", str(edited_db), "-o", str(edited_db)])

    # ── step 7: export edited + HTML diff ─────────────────────────────
    print("\n[7/8] Export edited roster + generate HTML diff", file=sys.stderr)
    cargo(["export", str(edited_db), "-o", str(edited_json)])

    with open(edited_json, encoding="utf-8") as f:
        edited = json.load(f)

    for first, last, dest_city, dest_id in trades_with_ids:
        rec = None
        for p in edited["players"]:
            if p["first_name"].lower() == first.lower() and p["last_name"].lower() == last.lower():
                rec = p["record"]
                break
        actual = edited["players"][rec]["proteam"] if rec is not None else None
        status = "OK" if actual == dest_id else f"FAIL (got {actual}, expected {dest_id})"
        print(f"  {first} {last} proteam={actual} {status}")
        if actual != dest_id:
            sys.exit(f"import failed: {first} {last} proteam {actual} != {dest_id}")

    build_html_diff(baseline, edited, trades_with_ids, diff_html)

    # ── step 8: pack + install ────────────────────────────────────────
    print("\n[8/8] Pack roster container + install into save tree", file=sys.stderr)
    field_0x2c = read_field_0x2c(source_path)
    print(f"  @0x2c = {field_0x2c}")
    cargo([
        "pack", str(edited_db), str(source_path),
        "--field-0x2c", field_0x2c,
        "-o", str(packed_bin),
    ])

    # Verify the packed blob round-trips
    print("\n  verifying round-trip...")
    cargo(["unpack", str(packed_bin), "-o", str(work / "roundtrip.db")])
    roundtrip = (work / "roundtrip.db").read_bytes()
    original = edited_db.read_bytes()
    if roundtrip == original:
        print("  round-trip verified (unpacked == edited)")
    else:
        sys.exit(f"round-trip failure: {len(roundtrip)} vs {len(original)} bytes")

    # Install into save tree
    installer = find_installer()
    print(f"\n  using installer: {installer}")

    template_header = find_template_header()

    if "install_recomp_roster" in installer:
        args = [
            sys.executable, installer,
            str(packed_bin),
            "--timestamp", TIMESTAMP,
            "--name", ROSTER_DISPLAY_NAME,
        ]
        if template_header:
            args.extend(["--template-header", str(template_header)])
        run(*args)
    else:
        # install_m5_saves.py has hardcoded names; copy blob manually.
        print("  install_m5_saves cannot install custom names.", file=sys.stderr)
        print(f"  Copy {packed_bin.name} into the save tree manually.", file=sys.stderr)
        print(f"  See docs/LOCAL-ARTIFACTS.md for save tree paths.", file=sys.stderr)

    # ── done ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60, file=sys.stderr)
    print("  SMOKE TEST COMPLETE", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"\n  Roster name in-game:  {ROSTER_DISPLAY_NAME}", file=sys.stderr)
    print(f"  HTML diff:            {diff_html}", file=sys.stderr)
    print(f"  Packed roster:        {packed_bin}", file=sys.stderr)
    print(f"\n  To verify in-game:", file=sys.stderr)
    print(f"    1. Start NHL Legacy", file=sys.stderr)
    print(f"    2. Customize -> Load -> Roster -> RB (Refresh)", file=sys.stderr)
    print(f"    3. Load '{ROSTER_DISPLAY_NAME}'", file=sys.stderr)
    print(f"    4. Roster Management -> Player Movement", file=sys.stderr)
    print(f"    5. Confirm:", file=sys.stderr)
    for first, last, dest_city, dest_id in trades_with_ids:
        print(f"       {first} {last} is on {dest_city}", file=sys.stderr)


if __name__ == "__main__":
    main()

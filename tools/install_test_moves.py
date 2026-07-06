"""Build and install test roster saves using the Rust move-player pipeline."""
import subprocess, time, os

TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)
CLEAN_PACKED = f"{TMP}/clean_orig_packed.bin"
INSTALL_SCRIPT = "tools/install_recomp_roster.py"

MOVES = [
    ("Auston", "Matthews", "CBJ", "R_MATT_CBJ"),
    ("Connor", "McDavid", "CBJ", "R_MCD_CBJ"),
    ("Connor", "McDavid", "LAK", "R_MCD_LAK"),
    ("Leon", "Draisaitl", "CBJ", "R_DRAI_CBJ"),
    ("Leon", "Draisaitl", "LAK", "R_DRAI_LAK"),
]

for first, last, team, label in MOVES:
    print(f"\n=== {first} {last} -> {team} ({label}) ===")
    
    bin_path = f"{TMP}/{label}.bin"
    result = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "move-player", CLEAN_PACKED,
        "--player-first", first,
        "--player-last", last,
        "--team", team,
        "--output", bin_path,
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr}")
        continue
    
    ts = time.strftime("%Y%m%d%H%M%S")
    result = subprocess.run([
        "python", INSTALL_SCRIPT, bin_path,
        "--timestamp", ts, "--name", label,
        "--template-header", HEADER
    ], capture_output=True, text=True)
    print(f"  {result.stdout.strip()}")
    time.sleep(1)

print("\n=== DONE ===")
print("Our saves (R_ prefix): should work identically to known-good saves.")
print("To extend KNOWN_EGLU for new players: generate an MS sample and diff the eGlu table at 0x1AB73C (16-byte records).")

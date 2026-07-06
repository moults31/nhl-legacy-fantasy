"""Pack and install default_orig.db and default_orig_matthews_cbj.db, then diff them."""
import subprocess, os, datetime, struct

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

# Pack both
ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

for label, dbfile in [("R_ORIG", "default_orig.db"), ("R_MATT_CBJ", "default_orig_matthews_cbj.db")]:
    print(f"--- Packing {label} ({dbfile}) ---")
    db_path = os.path.join(SRC, dbfile)
    
    # Pack with flate2
    result = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "pack-fdeflate", db_path, f"{BIN}/TRADEEDIT5",
        "--output", f"{TMP}/{label}.bin"
    ], capture_output=True, text=True)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(f"PACK FAILED: {result.stderr}")
        exit(1)
    
    # Install
    result = subprocess.run([
        "python", "tools/install_recomp_roster.py", f"{TMP}/{label}.bin",
        "--timestamp", ts, "--name", label,
        "--template-header", HEADER
    ], capture_output=True, text=True)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(f"INSTALL FAILED: {result.stderr}")
        exit(1)

print("\n=== Installed ===")
print("R_ORIG:     default baseline, no edits")
print("R_MATT_CBJ: Matthews moved to CBJ (MS)")
print("Load both in-game to confirm they work. Then we diff R_MATT_CBJ vs R_ORIG.")

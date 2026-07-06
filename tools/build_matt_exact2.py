"""Build exact MS replica: Matthews->CBJ on clean default (fixed record=5593)."""
import struct, os, subprocess, datetime

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

with open(os.path.join(SRC, "default_orig.db"), "rb") as f:
    db = bytearray(f.read())
with open(os.path.join(SRC, "default_orig_matthews_cbj.db"), "rb") as f:
    ms_db = f.read()

# Matthews is at record 5593 (1-indexed Rust convention)
# Verified: team_alt=0x1c(=28), proteam=0xe0(=28<<3) at this record
REC = 5593
BASE = 0x0A3168
RS = BASE + REC * 132

# Apply ALL MS changes - just copy them exactly from the MS output
for off in range(len(db)):
    if db[off] != ms_db[off]:
        db[off] = ms_db[off]

# Verify byte-identical now
diffs = [(i, db[i], ms_db[i]) for i in range(len(db)) if db[i] != ms_db[i]]
print(f"Diffs after copying MS changes: {len(diffs)}")

# Save, pack, install
pre_db = os.path.join(TMP, "matt_cbj_exact2.db")
with open(pre_db, "wb") as f:
    f.write(bytes(db))

# No need to reseal - we copied MS's exact bytes including CRCs
print("Packing directly (MS bytes already have correct CRCs)...")
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-fdeflate", pre_db, f"{BIN}/TRADEEDIT5",
    "--output", f"{TMP}/M_EXACT2_CBJ.bin"
], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode != 0:
    print(f"PACK FAILED: {result.stderr}")
    exit(1)

ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
result = subprocess.run([
    "python", "tools/install_recomp_roster.py", f"{TMP}/M_EXACT2_CBJ.bin",
    "--timestamp", ts, "--name", "M_EXACT2_CBJ",
    "--template-header", HEADER
], capture_output=True, text=True)
print(result.stdout.strip())

if result.returncode == 0:
    print("\nInstalled as M_EXACT2_CBJ — Matlab at the byte level. Test in-game!")
    
    # Also install the MS original for comparison
    ms_db_path = os.path.join(SRC, "default_orig_matthews_cbj.db")
    result2 = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "pack-fdeflate", ms_db_path, f"{BIN}/TRADEEDIT5",
        "--output", f"{TMP}/R_MATT_MS_CBJ.bin"
    ], capture_output=True, text=True)
    ts2 = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    result2 = subprocess.run([
        "python", "tools/install_recomp_roster.py", f"{TMP}/R_MATT_MS_CBJ.bin",
        "--timestamp", ts2, "--name", "R_MATT_MS",
        "--template-header", HEADER
    ], capture_output=True, text=True)
    print("\nAlso installed R_MATT_MS — the original MS output, as a control.")
    print("If M_EXACT2_CBJ works but our earlier M_CBJ didn't, the issue is edit-log pattern.")

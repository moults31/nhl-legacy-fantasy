"""Pack MS DBs for testing, and test edit-log variants."""
import struct, os, subprocess, datetime

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

def pack_and_install(db_path, label):
    """Pack a .db file and install it as a loadable roster."""
    result = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "pack-fdeflate", db_path, f"{BIN}/TRADEEDIT5",
        "--output", f"{TMP}/{label}.bin"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  PACK FAILED: {result.stderr}")
        return False
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    result = subprocess.run([
        "python", "tools/install_recomp_roster.py", f"{TMP}/{label}.bin",
        "--timestamp", ts, "--name", label,
        "--template-header", HEADER
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  INSTALL FAILED: {result.stderr}")
        return False
    print(f"  Installed as {label}")
    return True

# 1. Pack the MS original for validation
print("=== Packing MS original Matthews->CBJ ===")
ms_orig = os.path.join(SRC, "default_orig_matthews_cbj.db")
pack_and_install(ms_orig, "R_MATT_MS")

# 2. Also pack R_ORIG for baseline comparison
print("\n=== Packing clean default (R_ORIG) ===")
orig_db = os.path.join(SRC, "default_orig.db")
pack_and_install(orig_db, "R_ORIG")

# 3. Build variant: ONLY proteam+team_alt, no edit-log, no CRCs
print("\n=== Building V_CLEAN: proteam+team_alt only ===")
with open(orig_db, "rb") as f:
    db = bytearray(f.read())

REC = 5593
BASE = 0x0A3168
RS = BASE + REC * 132
db[RS + 6] = 0x09     # team_alt = CBJ
db[RS + 115] = 0x48    # proteam = CBJ

v_clean = os.path.join(TMP, "v_clean.db")
with open(v_clean, "wb") as f:
    f.write(bytes(db))
pack_and_install(v_clean, "V_CLEAN")

# 4. Build variant: proteam+team_alt + edit-log bytes + CRCs
print("\n=== Building V_FULL: all MS changes except just copying them ===")
with open(orig_db, "rb") as f:
    db = bytearray(f.read())

# Player record
db[RS + 6] = 0x09
db[RS + 115] = 0x48

# Edit-log region
db[0x1B97CC] = 0x08
db[0x1B97D0] = 0x01
db[0x1B97D1] = 0x9B
db[0x1B97D2] = 0x90
db[0x1B97D4] = 0xAC
db[0x1B97D5] = 0x80

# eGlu record 769 zeroing
db[0x1AE750] = 0x00
db[0x1AE751] = 0x00
db[0x1AE752] = 0x00

# CRC counter
db[0x1AB24B] = 0x0A

v_full_pre = os.path.join(TMP, "v_full_pre.db")
with open(v_full_pre, "wb") as f:
    f.write(bytes(db))

# Reseal CRCs
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "reseal", v_full_pre, "--output", f"{TMP}/v_full.db", "--ms-only"
], capture_output=True, text=True)
if result.returncode != 0:
    print(f"  RESEAL FAILED: {result.stderr}")
else:
    pack_and_install(f"{TMP}/v_full.db", "V_FULL")

print("\n=== SUMMARY ===")
print("R_ORIG:     Clean default, no edits")
print("R_MATT_MS:  MS-produced Matthews->CBJ (should work)")
print("V_CLEAN:    Only proteam+team_alt, no edit-log (should silently fail)")
print("V_FULL:     All changes we identified, with computed CRCs")
print("\nTest R_MATT_MS first to confirm MS's save works.")
print("Then test V_FULL. If it works, our edit-log pattern is correct.")
print("If V_FULL silently fails, we're missing something (like the footer CRC).")

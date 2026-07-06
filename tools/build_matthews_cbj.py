"""Build Matthews->CBJ test save with proper edit-log for unknown players.

Matthews: record 5592 (0-indexed), currently on Toronto (team 29, 1-indexed).
Target: Columbus/CBJ (team 9, 1-indexed).
"""
import zlib, subprocess, os, datetime, struct

BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    packed = f.read()
    t5 = bytearray(zlib.decompress(packed[48:]))

MATTHEWS_REC = 5592
BASE = 0x0A3168
RS = BASE + MATTHEWS_REC * 132
SRC_TEAM = 29   # Toronto (1-indexed)
TGT_TEAM = 9    # CBJ/Columbus (1-indexed)
TGT_0IDX = TGT_TEAM - 1  # 8

# Verify source team in TRADEEDIT5
proteam_raw = t5[RS + 115]
team_alt_raw = t5[RS + 6]
print(f"TRADEEDIT5 Matthews: proteam=0x{proteam_raw:02x}, team_alt=0x{team_alt_raw:02x}")
print(f"Moving from Toronto ({SRC_TEAM}) to CBJ/Columbus ({TGT_TEAM})")

# Normalization (baseline MS re-save)
t5[0x0CACAE] = 0x08; t5[0x0CAD1B] = 0x40   # Hedman
t5[0x1B97D1] = 0x00; t5[0x1B97D2] = 0x00    # zero Hedman edit-log slot
t5[0x1B97EC] = 0x07; t5[0x1B97F1] = 0x70    # restore
t5[0x1B97F2] = 0x50; t5[0x1B97F4] = 0x98    # restore
t5[0x1AB24B] = 0x0C                           # CRC counter baseline

# Set proteam: 5 high bits of byte (record+115)
t5[RS + 115] = (TGT_TEAM & 0x1F) << 3

# Set team_alt: full byte at record+6
t5[RS + 6] = TGT_TEAM

# Edit-log: since Matthews has no pre-existing slot, skip ctrl_off zeroing.
# Write active move at 0x1B97FC-0x1B9805:
MARKER = (MATTHEWS_REC % 254) + 1  # Avoid 0

def team_editlog_byte(team_1idx):
    return 0x5D if team_1idx == 5 else team_1idx * 19

t5[0x1B97FC] = TGT_0IDX
t5[0x1B9801] = 0x41
t5[0x1B9802] = MARKER
t5[0x1B9804] = team_editlog_byte(TGT_TEAM)
t5[0x1B9805] = 0x80
t5[0x1AB24B] = 0x0D  # CRC counter: 0x0C + 1

print(f"Edit-log: team-1=0x{t5[0x1B97FC]:02x}, marker=0x{t5[0x1B9802]:02x}")
print(f"CRC counter: 0x{t5[0x1AB24B]:02x}")

# Save, reseal, pack, install
pre_db = os.path.join(TMP, "matt_cbj_pre.db")
with open(pre_db, "wb") as f:
    f.write(bytes(t5))

result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "reseal", pre_db, "--output", f"{TMP}/matt_cbj.db", "--ms-only"
], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode != 0:
    print(f"RESEAL FAILED: {result.stderr}")
    exit(1)

result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-fdeflate", f"{TMP}/matt_cbj.db", f"{BIN}/TRADEEDIT5",
    "--output", f"{TMP}/M_CBJ.bin"
], capture_output=True, text=True)
print(result.stdout.strip())

ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
result = subprocess.run([
    "python", "tools/install_recomp_roster.py", f"{TMP}/M_CBJ.bin",
    "--timestamp", ts, "--name", "M_CBJ",
    "--template-header", HEADER
], capture_output=True, text=True)
print(result.stdout.strip())

if result.returncode == 0:
    print("\nInstalled as M_CBJ -- test in-game! Matthews should be on CBJ/Columbus.")
    print("(If edit-log marker is wrong, this will silently fail.)")

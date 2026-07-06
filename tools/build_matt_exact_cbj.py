"""Build exact MS replica: Matthews->CBJ on clean default."""
import struct, os, subprocess, datetime

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

# Read original DB
with open(os.path.join(SRC, "default_orig.db"), "rb") as f:
    db = bytearray(f.read())

# Read MS output for comparison
with open(os.path.join(SRC, "default_orig_matthews_cbj.db"), "rb") as f:
    ms_db = f.read()

print(f"DB size: {len(db)}")

MATTHEWS_REC = 5592
BASE = 0x0A3168
RS = BASE + MATTHEWS_REC * 132

# ── Apply ALL MS changes ──
# team_alt at record+6
db[RS + 6] = 0x09    # CBJ (1-indexed)

# proteam at record+115
db[RS + 115] = 0x48  # CBJ packed

# eGlu record 769 (at 0x1AE750): zero 3 bytes
db[0x1AE750] = 0x00
db[0x1AE751] = 0x00
db[0x1AE752] = 0x00

# Edit-log region
db[0x1B97CC] = 0x08   # team-1 (CBJ 0-indexed)
db[0x1B97D0] = 0x01   # saved from eGlu rec 769 byte+4
db[0x1B97D1] = 0x9B   # saved from eGlu rec 769 byte+5
db[0x1B97D2] = 0x90   # saved from eGlu rec 769 byte+6
db[0x1B97D4] = 0xAC   # prefix/marker for new player
db[0x1B97D5] = 0x80   # constant

# CRC counter
db[0x1AB24B] = 0x0A

# ── Save and reseal ──
pre_db = os.path.join(TMP, "matt_cbj_exact_pre.db")
with open(pre_db, "wb") as f:
    f.write(bytes(db))

# Calculate what the resealer will change
print("\nBefore reseal, compare with MS at known CRC locations:")
for label, off in [
    ("RBQQ prior_crc", 0x1A4838),
    ("ulGe header_crc", 0x1AB258),
    ("caBZ prior_crc", 0x1D5F2C),
    ("??", 0x1DFB20),
]:
    ms_val = struct.unpack('>I', ms_db[off:off+4])[0]
    our_val = struct.unpack('>I', db[off:off+4])[0]
    print(f"  {label} @ 0x{off:08x}: ours=0x{our_val:08x}  ms=0x{ms_val:08x}  {'SAME' if our_val==ms_val else 'DIFF'}")

# Reseal MS-only
resealed = os.path.join(TMP, "matt_cbj_exact.db")
result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "reseal", pre_db, "--output", resealed, "--ms-only"
], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode != 0:
    print(f"RESEAL FAILED: {result.stderr}")
    exit(1)

# Check after reseal
print("\nAfter reseal:")
with open(resealed, "rb") as f:
    our_db = f.read()
for label, off in [
    ("RBQQ prior_crc", 0x1A4838),
    ("ulGe header_crc", 0x1AB258),
    ("caBZ prior_crc", 0x1D5F2C),
    ("??", 0x1DFB20),
]:
    ms_val = struct.unpack('>I', ms_db[off:off+4])[0]
    our_val = struct.unpack('>I', our_db[off:off+4])[0]
    print(f"  {label} @ 0x{off:08x}: ours=0x{our_val:08x}  ms=0x{ms_val:08x}  {'SAME' if our_val==ms_val else 'DIFF'}")

# Full byte comparison
diffs = [(i, our_db[i], ms_db[i]) for i in range(len(our_db)) if our_db[i] != ms_db[i]]
print(f"\nTotal diffs after reseal: {len(diffs)}")
for i, o, m in diffs[:20]:
    print(f"  0x{i:08x}: ours=0x{o:02x}  ms=0x{m:02x}")

# Pack if we have zero diffs (meaning exact replica)
if len(diffs) == 0:
    print("\nEXACT REPLICA! Packing...")
    result = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "pack-fdeflate", resealed, f"{BIN}/TRADEEDIT5",
        "--output", f"{TMP}/M_EXACT_CBJ.bin"
    ], capture_output=True, text=True)
    print(result.stdout.strip())
    
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    result = subprocess.run([
        "python", "tools/install_recomp_roster.py", f"{TMP}/M_EXACT_CBJ.bin",
        "--timestamp", ts, "--name", "M_EXACT_CBJ",
        "--template-header", HEADER
    ], capture_output=True, text=True)
    print(result.stdout.strip())
    print("\nInstalled as M_EXACT_CBJ — exact MS replica. Test in-game!")
else:
    print(f"\nNot exact. Need to investigate the {len(diffs)} remaining diffs.")

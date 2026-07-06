"""Build V_FIX: V_FULL with MS footer CRC, to isolate the issue."""
import struct, os, subprocess, datetime

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

with open(os.path.join(SRC, "default_orig_matthews_cbj.db"), "rb") as f:
    ms = f.read()

with open(os.path.join(TMP, "v_full.db"), "rb") as f:
    vfull = bytearray(f.read())

# Copy MS footer (last 4 bytes) and 0x1DFB20 bytes to V_FULL
eof = len(vfull) - 4
vfull[eof:eof+4] = ms[eof:eof+4]
vfull[0x1DFB20:0x1DFB24] = ms[0x1DFB20:0x1DFB24]

# Check remaining diffs
diffs = sum(1 for i in range(len(vfull)) if vfull[i] != ms[i])
print(f"Remaining diffs: {diffs}")

# Verify the changes are only at these locations
if diffs > 0:
    for i in range(len(vfull)):
        if vfull[i] != ms[i]:
            print(f"  0x{i:08x}: our=0x{vfull[i]:02x} ms=0x{ms[i]:02x}")

# Save and pack
vfix_path = os.path.join(TMP, "v_fix.db")
with open(vfix_path, "wb") as f:
    f.write(bytes(vfull))

result = subprocess.run([
    "cargo", "run", "--release", "-p", "roster-cli", "--",
    "pack-fdeflate", vfix_path, f"{BIN}/TRADEEDIT5",
    "--output", f"{TMP}/V_FIX.bin"
], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode != 0:
    print(f"PACK FAILED: {result.stderr}")
    exit(1)

ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
result = subprocess.run([
    "python", "tools/install_recomp_roster.py", f"{TMP}/V_FIX.bin",
    "--timestamp", ts, "--name", "V_FIX",
    "--template-header", HEADER
], capture_output=True, text=True)
print(result.stdout.strip())

print("\nInstalled as V_FIX — V_FULL + MS footer + caBZ data bytes.")
print("Test order:")
print("  1. R_MATT_MS — MS original (should work)")
print("  2. R_ORIG — clean default (Matthews on Toronto)")
print("  3. V_FULL — all our changes with computed CRCs")
print("  4. V_FIX — V_FULL with MS footer bytes")

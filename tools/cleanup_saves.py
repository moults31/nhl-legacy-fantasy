"""Clean up all test saves, then reinstall V_ANA and V_LAK with clear names."""
import os, shutil, subprocess, datetime

SAVES = os.path.expandvars(r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\00000001")
HEADERS = os.path.expandvars(r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001")
TMP = "tools/tmp"

# Delete all July 2026 test saves (keep March originals)
deleted = []
for d in sorted(os.listdir(SAVES)):
    if d.startswith("ROSTER 202607") or d.startswith("R_") or d.startswith("V_") or d.startswith("M_"):
        save_dir = os.path.join(SAVES, d)
        header_file = os.path.join(HEADERS, d + ".header")
        if os.path.isdir(save_dir):
            shutil.rmtree(save_dir)
            deleted.append(f"save: {d}")
        if os.path.isfile(header_file):
            os.remove(header_file)
            deleted.append(f"header: {d}.header")

print("Deleted:")
for item in deleted:
    print(f"  {item}")

# Now reinstall V_ANA.bin and V_LAK.bin with clear names
BIN = "_local/game-saves/xbox"
HEADER_TEMPLATE = os.path.expandvars(
    r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header"
)

def install(bin_name, display_name):
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    bin_path = os.path.join(TMP, f"{bin_name}.bin")
    if not os.path.exists(bin_path):
        print(f"  MISSING: {bin_path}")
        return False
    result = subprocess.run([
        "python", "tools/install_recomp_roster.py", bin_path,
        "--timestamp", ts, "--name", display_name,
        "--template-header", HEADER_TEMPLATE
    ], capture_output=True, text=True)
    print(f"  {display_name}: {result.stdout.strip()}")
    return result.returncode == 0

print("\nReinstalling:")
install("V_ANA", "MCDAVID_ANA")
install("V_LAK", "DRAI_LAK")

print("\nClean. Load these in-game:")
print("  MCDAVID_ANA  -- McDavid should be on Anaheim")
print("  DRAI_LAK     -- Draisaitl should be on Los Angeles")

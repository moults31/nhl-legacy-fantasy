"""Verify and build: D3 = ClpB parity, D4 = f(ClpB) using known MS samples."""
import struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"
with open(os.path.join(SRC, 'default_orig.db'), 'rb') as f: orig = f.read()

# Our team mapping
TEAMS = {1:'ANA',2:'BOS',3:'BUF',5:'CGY',6:'CAR',7:'CHI',8:'COL',9:'CBJ',
         10:'DAL',11:'DET',12:'EDM',13:'FLA',14:'LAK',15:'MIN',16:'MTL',
         17:'NSH',18:'NJD',19:'NYI',20:'NYR',21:'OTT',22:'PHI',24:'PIT',
         25:'SJS',27:'STL',28:'TBL',29:'TOR',30:'VAN',31:'VGK',32:'WPG',33:'WSH'}

# Known D3-D4 values from MS (for CBJ=9 and LAK=14)
# CBJ: CC=0x08, D3=0x00, D4=0xAC (=172)
# LAK: CC=0x0d, D3=0x01, D4=0x10 (=16)

# Verify D3 parity hypothesis + search for D4 formula
print("Team D3-D4 analysis:")
for tid in [9, 14]:
    clpb = None
    # Find ClpB from StEO table
    # StEO: row 7 = Columbus (ClpB=8), row 12 = LA (ClpB=13)
    st = {9: 8, 14: 13}  # hardcoded from earlier analysis
    clpb = st[tid]
    parity = clpb & 1
    print(f"  {TEAMS[tid]} (t={tid}): ClpB={clpb}, parity={parity}")

# For Draisaitl eGlu rec 1027, verify the pattern
print("\nDraisaitl eGlu rec 1027:")
off1027 = 0x1AB73C + 1027 * 16
print(f"  orig [+4..+6]: [{orig[off1027+4]:02x} {orig[off1027+5]:02x} {orig[off1027+6]:02x}]")

# Now build the saves!
print("\n" + "="*60)
print("Building working test saves")
print("="*60)
import subprocess, datetime

BIN = "_local/game-saves/xbox"
TMP = "tools/tmp"
HEADER = os.path.expandvars(r"%USERPROFILE%\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\Headers\00000001\ROSTER 20260308000501.header")
BASE = 0x0A3168
ULGE_RECS = 0x1AB73C

# Known player -> eGlu displacement records
EGLU_REC_FOR_PLAYER = {
    3498: 2788,   # McDavid
    3436: 1027,   # Draisaitl
    5593: 769,    # Matthews
}

# Known D3-D4 per target team
PREFIX_TABLE = {
    9:  (0x00, 0xAC),  # CBJ: D3=0x00, D4=0xAC
    14: (0x01, 0x10),  # LAK: D3=0x01, D4=0x10
}

MOVES = [
    ("McDavid", 3498, 9, "CBJ", "MCD_CBJ"),
    ("McDavid", 3498, 14, "LAK", "MCD_LAK"),
    ("Draisaitl", 3436, 9, "CBJ", "DRAI_CBJ"),
    ("Draisaitl", 3436, 14, "LAK", "DRAI_LAK"),
]

for player_name, rec, target_team, target_name, label in MOVES:
    print(f"\n--- {player_name} -> {target_name} ({label}) ---")
    
    db = bytearray(orig)
    RS = BASE + rec * 132
    
    # proteam + team_alt
    target_0idx = target_team - 1
    db[RS + 115] = (target_team & 0x1F) << 3
    db[RS + 6] = target_team
    print(f"  proteam: 0x{db[RS+115]:02x} (team {target_team})")
    print(f"  team_alt: 0x{db[RS+6]:02x}")
    
    # Edit-log
    eglu_rec = EGLU_REC_FOR_PLAYER[rec]
    eglu_off = ULGE_RECS + eglu_rec * 16
    orig_b4 = orig[eglu_off+4]
    orig_b5 = orig[eglu_off+5]
    orig_b6 = orig[eglu_off+6]
    
    print(f"  eGlu rec {eglu_rec}: orig [+4..+6]=[{orig_b4:02x} {orig_b5:02x} {orig_b6:02x}]")
    
    # Decrement counter at byte 4
    db[eglu_off+4] = orig_b4 - 1 if orig_b4 > 0 else 0
    # Zero bytes 5-6
    db[eglu_off+5] = 0
    db[eglu_off+6] = 0
    
    d3, d4 = PREFIX_TABLE[target_team]
    
    db[0x1B97CC] = target_0idx
    db[0x1B97D0] = 0x01       # constant
    db[0x1B97D1] = orig_b5    # saved byte 5
    db[0x1B97D2] = orig_b6    # saved byte 6
    db[0x1B97D3] = d3         # parity bit
    db[0x1B97D4] = d4         # team-specific value
    db[0x1B97D5] = 0x80       # constant
    
    db[0x1AB24B] = 0x0A
    
    print(f"  Edit-log: CC=0x{target_0idx:02x}, D0-D5=[{db[0x1B97D0]:02x} {db[0x1B97D1]:02x} {db[0x1B97D2]:02x} {db[0x1B97D3]:02x} {db[0x1B97D4]:02x} {db[0x1B97D5]:02x}]")
    
    # Save, reseal, pack, install
    pre_db = os.path.join(TMP, f"{label.lower()}_pre.db")
    with open(pre_db, "wb") as f:
        f.write(bytes(db))
    
    result = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "reseal", pre_db, "--output", f"{TMP}/{label.lower()}.db", "--ms-only"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  RESEAL FAILED: {result.stderr}")
        continue
    
    result = subprocess.run([
        "cargo", "run", "--release", "-p", "roster-cli", "--",
        "pack-fdeflate", f"{TMP}/{label.lower()}.db", f"{BIN}/TRADEEDIT5",
        "--output", f"{TMP}/{label}.bin"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  PACK FAILED: {result.stderr}")
        continue
    
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    result = subprocess.run([
        "python", "tools/install_recomp_roster.py", f"{TMP}/{label}.bin",
        "--timestamp", ts, "--name", label,
        "--template-header", HEADER
    ], capture_output=True, text=True)
    print(f"  INSTALLED: {result.stdout.strip()}")

# Verify byte-identical with MS samples
print("\n\nVerification: Should be byte-identical to MS output for known patterns:")
for ms_file, label, our_file in [
    ("default_orig_mcd_lak.db", "McDavid->LAK", "mcd_lak.db"),
    ("default_orig_drai_lak.db", "Draisaitl->LAK", "drai_lak.db"),
    ("default_orig_mcd_cbj.db", "McDavid->CBJ", "mcd_cbj.db"),
]:
    ms_path = os.path.join(SRC, ms_file)
    our_path = os.path.join(TMP, our_file)
    if os.path.exists(ms_path) and os.path.exists(our_path):
        with open(ms_path, 'rb') as f: m = f.read()
        with open(our_path, 'rb') as f: o = f.read()
        diffs = sum(1 for i in range(len(o)) if o[i] != m[i])
        print(f"  {label}: {diffs} diffs {'PERFECT!' if diffs == 0 else ''}")

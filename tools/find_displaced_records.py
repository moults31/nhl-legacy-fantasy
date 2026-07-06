"""Find which eGlu records to displace and how to compute edit-log bytes."""
import struct, os

SRC = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511"

# Read CSV to find eGlu records by team
path = os.path.join(SRC, "default_orig.csv")
with open(path, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

eglu_start = None
for i, line in enumerate(lines):
    if line.strip() == 'eGlu':
        eglu_start = i
        break

eglu_fields = lines[eglu_start+1].strip().split(',')
team_idx = eglu_fields.index('dXSB')
xswt_idx = eglu_fields.index('XSWT')
svrt_idx = eglu_fields.index('sVRt')
data_start = eglu_start + 3

# Find records by team
for target_team, team_name in [(1, 'ANA'), (14, 'LAK')]:
    recs = []
    for i in range(data_start, len(lines)):
        line = lines[i].strip()
        if not line or (len(line) == 4 and line.isascii() and line.isalpha()):
            break
        vals = line.split(',')
        if len(vals) > team_idx and vals[team_idx] == str(target_team):
            rec = i - data_start
            pid = vals[xswt_idx] if xswt_idx < len(vals) else '?'
            jersey = vals[svrt_idx] if svrt_idx < len(vals) else '?'
            recs.append((rec, pid, jersey))
    
    print(f'{team_name} (team {target_team}): {len(recs)} records')
    for r in recs[-5:]:
        print(f'  rec {r[0]}: PID={r[1]}, Jersey={r[2]}')
    
    # Pick last record as displacement candidate
    if recs:
        last = recs[-1]
        print(f'  -> Displacing rec {last[0]} (last entry)')

# Also check: for CBJ (team 8/9), which record was displaced?
# MS displaced rec 769. Where is rec 769 in the list?
for target_team, team_name in [(8, 'CBJ')]:
    recs = []
    for i in range(data_start, len(lines)):
        line = lines[i].strip()
        if not line or (len(line) == 4 and line.isascii() and line.isalpha()):
            break
        vals = line.split(',')
        if len(vals) > team_idx and vals[team_idx] == str(target_team):
            rec = i - data_start
            pid = vals[xswt_idx] if xswt_idx < len(vals) else '?'
            recs.append((rec, pid))
    
    print(f'\n{team_name} (team {target_team}): {len(recs)} records')
    for idx, (r, pid) in enumerate(recs):
        marker = ' <-- DISPLACED' if r == 769 else ''
        print(f'  #{idx} rec {r}: PID={pid}{marker}')

# Now: how to compute 0x1B97D4 (0xAC)?
# Let me check: does 0xAC = Matthews ubPc record % 256?
# Matthews CSV record = 5592 (0-indexed in CSV)
# 5592 % 256 = 216 = 0xD8. Not 0xAC.
# Matthews PID = 13516. 13516 % 256 = 204 = 0xCC. Not 0xAC.
# Matthews eGlu... wait, Matthews isn't in eGlu
# 
# What about the DISPLACED player?
# Displaced rec 769 has PID 6670
# 6670 % 256 = 14 = 0x0E
# Displaced record index = 769
# 769 % 256 = 1 = 0x01
# 
# What about relationship to target team?
# Target team = CBJ = 9 (1-indexed)
# 9 * 19 + 1 = 172 = 0xAC  !!
# 
# Let me check: 9 * 19 = 171 = 0xAB. But 0xAC = 172.
# Hmm, 9 * 19 = 171, not 172.
# 0xAC = 172. 172 - 9*19 = 1.
# 
# Wait: team 8 (0-indexed) * 19 = 152 = 0x98 (which is a TRADEEDIT5 edit-log byte!)
# In TRADEEDIT5: t5[0x1B97F4] = 0x98 (this was team*19 for Hedman's baseline)
# 
# Actually, in move_player.rs:
# fn team_editlog_byte(team_id: u8) -> u8 { match team_id { 5 => 0x5D, _ => team_id * 19 } }
# For team 9 (CBJ): 9 * 19 = 171 = 0xAB. NOT 0xAC.
# For team 8 (0-indexed): 8 * 19 = 152 = 0x98.
# 
# So 0xAC doesn't match team*19 either.

# Let me try: team_editlog_byte for team 9 (1-indexed) might be wrong in our code.
# 9 * 19 = 171 = 0xAB. But MS wrote 0xAC = 172.
# Difference of 1.

# Maybe the formula is different for the clean baseline vs TRADEEDIT5?
# In TRADEEDIT5: Matthews wasn't moved. Only Crosby, Ovechkin, Hedman.
# For Hedman to STL (team 27 = 1-indexed): t5[0x1B97F4] = 0x98
# Hmm, 27 * 19 = 513 = 0x201. Not 0x98.
# But team 27 - 19 = 8. And 8 * 19 = 152 = 0x98.
# 
# Wait. Hedman moved FROM TBL (28) TO STL (27). The write was at 0x1B97F4 for normalization.
# In TRADEEDIT5, Hedman started at TBL (28) and was moved to STL (27) as part of normalization.
# 27 * 19 = 513 which is >255, so that doesn't work.
# 
# Let me check the original TRADEEDIT5 diffs more carefully.
# In the original Hedman normalization:
# t5[0x1B97F4] = 0x98  # This was "team*19"
# 
# Actually, looking at move_player.rs line 131:
# fn team_editlog_byte(team_id: u8) -> u8 {
#     match team_id {
#         5 => 0x5D,  // CGY special case
#         _ => team_id * 19,
#     }
# }
# 
# For COL (team 8): 8 * 19 = 152 = 0x98. Correct!
# For CGY (team 5): 0x5D special case.
# 
# For CBJ (team 9): 9 * 19 = 171 = 0xAB. But MS wrote 0xAC = 172.
# 172 = 0xAC. Difference of exactly 1 from 0xAB.
# 
# Could it be (team_id - 1) * 19? For COL: 7*19=133=0x85. But MS wrote 0x98.
# (team_id + 1) * 19? For COL: 9*19=171=0xAB. Nope.
# 
# Hmm. Let me check: for Matthews-CBJ on default_orig:
# 0x1B97D4 = 0xAC
# 0x1B97D5 = 0x80 (constant)
# 
# For the Crosby/Ovechkin/TRADEEDIT5 case:
# Crosby: 0x1B97E1 = prefix(0x41), 0x1B97E2 = marker(0x10), team*19 at +3
# In TRADEEDIT5 Crosby moved to COL:
# t5[0x1B9804] = team_editlog_byte(8) = 8*19 = 152 = 0x98
# BUT in the normalization, the slot at 0x1B97F1 was Hedman's: 
# t5[0x1B97F1] = 0x70; t5[0x1B97F2] = 0x50  # prefix+marker
# t5[0x1B97F4] = 0x98  # team*19? for team COL=8? That's 8*19=152=0x98. Yes!
# 
# So in TRADEEDIT5, the pattern is: [prefix][marker][xx][team*19]
# In default_orig, the pattern at 0x1B97CC is: [team-1][xx][saved_bytes][prefix][0x80]
# where prefix = 0xAC, and 0xAC = 172.
# 
# 172 / 19 = 9.05... Neither cleanly divides.
# 
# Anyway, for now I'll just try:
# 0x1B97D4 = team_editlog_byte(target_team)
# For ANA (team 1): 1*19 = 19 = 0x13
# For LAK (team 14): 14*19 = 266 = 0x10A which >255!
# So the formula is probably different.

# Maybe 0xAC is a checksum or derived from the DISPLACED record?
# Displaced rec 769, bytes 4-6 = 0x01 0x9B 0x90
# (0x01 + 0x9B + 0x90 + target_team) % 256? 
# = (1 + 155 + 144 + 9) % 256 = 309 % 256 = 53 = 0x35. Nope.
# 
# Or maybe 0xAC is just a constant for all "new player" moves on clean baseline?
# Let me try using 0xAC for ALL moves. If it's a constant header/magic byte, it should work.
# 
# Actually, let me try another approach: just try the move and see if it works.

print("\n\nFor testing, I'll use the SIMPLEST possible hypothesis:")
print("Pattern: displace LAST eGlu record for target team, use constant 0xAC prefix")
print("If it fails, we need more MS samples to reverse the pattern.")

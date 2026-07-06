#!/usr/bin/env python3
"""Analyze MS diffs: categorize every changed byte by its structural role."""
import struct, zlib as zl

BIN = "_local/game-saves/xbox"

with open(f"{BIN}/TRADEEDIT5", "rb") as f:
    t5_db = bytearray(zl.decompress(f.read()[48:]))

# MS1: Crosby->COL(0x40), Ovechkin->CGY(0x28)
with open(f"{BIN}/ms_crsbcol_ovicgy.db", "rb") as f:
    ms1 = f.read()
# MS2: Crosby->CGY(0x28), Ovechkin->COL(0x40)
with open(f"{BIN}/ms_crsbcgy_ovicol.db", "rb") as f:
    ms2 = f.read()

# Raw equivalent edits
raw1 = bytearray(t5_db)
raw1[0x0B949B] = 0x40; raw1[0x0B9837] = 0x28
raw1 = bytes(raw1)

raw2 = bytearray(t5_db)
raw2[0x0B949B] = 0x28; raw2[0x0B9837] = 0x40
raw2 = bytes(raw2)

# Get ea-tdb to parse record layout for cPbu
# For now, manually analyze offsets

# Key offsets (from McTavish test):
# proteam bit_offset=920, byte_offset=115 from record start
# Record length for cPbu: need to compute

# We can derive record start for Crosby from proteam byte location
# Crosby proteam at 0x0B949B -> record_start = 0x0B949B - 115 = 0x0B9426
# Let me verify with Ovechkin: proteam at 0x0B9837 -> record_start = 0x0B9837 - 115 = 0x0B97C2

# Wait, that gives different deltas: 0x0B949B-0x0B9426=0x75=117, not 115
# Let me re-derive. proteam bit_offset=920, byte_offset=920//8=115

# Actually the test output said: DB_offset=0x0B949B for Crosby
# That's the ABSOLUTE file offset of the proteam byte.
# record_bit_offset=920 means 920 bits from record start = 115 bytes
# So record_start = 0x0B949B - 115 = 0x0B949B - 0x73 = 0x0B9428

# Let me compute Ovechkin's record start
# Ovechkin proteam at 0x0B9837 -> record_start = 0x0B9837 - 115 = 0x0B9837-0x73 = 0x0B97C4
# Difference between records: 0x0B97C4 - 0x0B9428 = 0x39C = 924 bytes
# Number of records apart: Ovechkin(695) - Crosby(688) = 7
# Record length = 924/7 = 132 bytes? No, that doesn't match.
# Actually 0x39C is 924. 924/7 = 132. But the McTavish test said record_bit_offset=920, which is 115 bytes per record.
# Something's off.

# Let me look at record_length_bytes. The test shows: 
# WBbd: record_bit_offset=920 bit_width=5
# That's within cPbu records.
# The record_length_bytes comes from layout.info.record_length_bytes
# We don't have it directly, but we know each record has multiple fields.

# Actually, the test stored rec_start inline: rec_start = base + rec * rlb
# Let me check if 0x0B9428 and 0x0B97C4 are 924 apart.
# 0x0B97C4 - 0x0B9428 = 0x39C. 0x39C = 924. 
# 7 records apart (688 to 695), so rlb = 924/7 = 132.

# Hmm, but 115 bytes for proteam doesn't fit in a 132-byte record nicely.
# Let me check: if rlb=132, then Ovechkin is 7*132=924 after Crosby. ✓

# Crosby record_start = 0x0B9428
# proteam byte at record_start+115 = 0x0B9428+0x73 = 0x0B949B ✓

# Now, what's the byte at 0x0B942E?
# 0x0B942E - 0x0B9428 = 6 bytes from record start = 48 bits
# This is field bit_offset=48 in the cPbu record (6 bytes * 8)

# Let me look for nearby fields in the MS diffs:
# MS1: 0x0B942E changed 0x1E->0x08 (Crosby COL)
# MS2: 0x0B942E changed 0x1E->0x05 (Crosby CGY)
# 0x08 = Colorado, 0x05 = Calgary
# This looks like... a DIFFERENT representation of the team ID!
# 0x1E = 30 = Pittsburgh (original team)
# These match the proteam values but at a different byte position.

# Let me verify: 0x40 (proteam byte for COL) vs 0x08 (this byte for COL)
# And 0x28 (proteam for CGY) vs 0x05 (this byte for CGY)
# 0x40 >> 3 = 0x08. 0x28 >> 3 = 0x05.
# So byte at offset+6 stores proteam >> 3 (without the WfTt bits)!

# This makes sense: proteam at offset+115 stores full 5 bits packed with WfTt,
# while offset+6 stores a shifted-down version elsewhere.

# Now let me check Ovechkin:
# Ovechkin record at offset 0x0B97C4
# MS1 Ovechkin->CGY: diff at 0x0B97CA. 0x0B97CA - 0x0B97C4 = 6. 0x1B->0x05. 0x1B=27=Tampa original. 0x05=5=CGY.
# MS2 Ovechkin->COL: diff at 0x0B97CA. 0x1B->0x08. 0x08=8=COL.
# So offset+6 in each player record stores (team_id - 1)! Since proteam is 1-indexed, 
# (team-1) stored as a byte. 0x40 = 8 = COL proteam value. COL is team 8 in the game.
# 0x40 & 0x1F = 0, which is proteam=0? No.
# Actually: proteam field stores team_id-1 in 5 bits. 
# COL team_id = 8. proteam = 8. Stored as 0x40 (00100000 in top 5 of byte).
# The byte at offset+6: 0x08 = team_id. Or team_id-1? 0x08 could be 8 (team_id) or 7+1.
# For original PIT: proteam=30 (11110 in 5 bits = 0x1E). The byte at offset+6 is also 0x1E.
# So it stores proteam directly (as a full byte), not shifted.

# So the byte at record_offset+6 is a redundant copy of the team ID stored as a full byte.

# Now, 0x0CACAE: Hedman is at record 1232.
# 0x0CACAE - 1232*132 - records_offset = record_start. But we need records_offset.
# The proteam byte for Hedman is at 0x0CAD1B = record_start + 115
# So record_start = 0x0CAD1B - 115 = 0x0CACA8
# record_offset+6 = 0x0CACAE. That's the same pattern.

# MS1 Hedman diff at 0x0CACAE: 0x18->0x08 (PIT->COL). But wait, MS1 is supposed to just edit Crosby and Ovechkin.
# The user said no explicit Hedman edit. Yet MS changed Hedman from PIT (0x18=24?) to COL (0x08=COL).
# Wait, 0x18 is not PIT (30). 0x18=24=Tampa?
# Let me check: TRADEEDIT5 has Hedman on PIT. proteam=0xC0.
# 0xC0 >> 3 = 0x18 = 24. That's not PIT (30). 
# 0xC0 = 11000000. Proteam bits 4:0 = 00000 = 0. But that's wrong.
# Actually proteam=30 in 5 bits is '11110'. Stored as '11110xxx' = 0xF0.
# But TRADEEDIT5 Hedman protem byte is 0xC0 = 11000000 = '11000' = 24 = TB? But TRADEEDIT5 moved Hedman to PIT.
# Hmm, let me recheck.

# Actually from the dump_wbbd test earlier:
# Crosby  rec= 688 proteam= 30 DB_offset=0x0B949B span=1 bytes=[F0]
# Ovechkin rec= 695 proteam= 27 DB_offset=0x0B9837 span=1 bytes=[D8]
# Hedman  rec=1232 proteam= 24 DB_offset=0x0CAD1B span=1 bytes=[C0]

# So Hedman proteam=24 originally, not 30. 24 = ? Let me check team list.
# 24 in the game... could be Tampa? Or Philadelphia?
# Anyway, the point is: 0xC0 = 11000000. proteam=24 (11000). The byte at offset+6 would be 0x18=24.
# And MS changed it to 0x08 = COL.

# OK so the key finding is:
# MS updates a SECOND copy of the team ID at record_offset+6 of each MOVED player.
# This second copy stores the team_id as a full byte (not packed 5-bit).

# Now let me look at the other diffs:
# The zeroing clusters at 0x1B97xx-0x1B98xx and the CRC clusters at 0x1A48xx, 0x1AB2xx, 0x1D5Fxx

# These are likely table-level CRC updates and normalization MS does.
# The CRC clusters might be: MS resets internal table CRCs.
# The zeroing is MS clearing out old data.

# To confirm, I should ask the user to:
# 1. Make an MS save with just Crosby->COL (single edit)
# 2. Make an MS save with just Ovechkin->CGY (single edit, different player)
# 3. Make an MS save with NO edits (just open and re-save)

# This would isolate which changes are per-player vs per-save normalization.

print("Analysis: MS changes two things:")
print("1. At record_offset+6: a full-byte copy of the team_id")
print("   Crosby: T5(0x1E=30=PIT) -> MS1(0x08=COL) MS2(0x05=CGY)")
print("   Ovechkin: T5(0x1B=27=TB) -> MS1(0x05=CGY) MS2(0x08=COL)")
print("   Hedman: T5(0x18=24=PIT?) -> MS(0x08=COL) in BOTH")
print()
print("2. Other clusters need isolation:")
print("   - Zeroing: 0x1B97D1-0x1B9824 area")
print("   - CRCs: 0x1A4838, 0x1AB24B, 0x1D5F2C areas")

# Suggest user actions
print("\nRecommended MS saves to isolate:")
print("  A) Just Crosby->COL (single edit from TRADEEDIT5)")
print("  B) Just Ovechkin->CGY (single edit from TRADEEDIT5)")
print("  C) Open TRADEEDIT5 in MS and re-save with NO edits")

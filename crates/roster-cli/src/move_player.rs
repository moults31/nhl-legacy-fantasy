//! Apply a player team move to a clean default_orig.db roster save.
//!
//! Pipeline: unpack from packed save → edit player + eGlu + edit-log → reseal 3 CRCs → pack with flate2.
//!
//! This module operates on the clean default_orig.db baseline (not TRADEEDIT5).
//! Player lookup uses the CSV-generated [`roster_db`] static tables.

use std::io::Read;

use anyhow::{Context, Result};
use flate2::read::ZlibDecoder;
use roster_container::pack_with_fdeflate;

use crate::roster_db;

// ── TDB offsets (default_orig.db) ──

/// Base byte offset of the cPbu table data region.
const CPBU_BASE: usize = 0x0A3168;
/// Size of each cPbu record (player bio) in bytes.
const CPBU_REC_SIZE: usize = 132;

/// Base byte offset of the eGlu (ulGe) table data region.
const EGLU_BASE: usize = 0x1AB73C;
/// Size of each eGlu record in bytes.
const EGLU_REC_SIZE: usize = 16;

/// eGlu record used as the edit-log tracking slot (byte 0 = target team CC).
const EGLU_TRACKER_REC: usize = 3593;

/// Offset within a cPbu record of the `proteam` field (5-bit packed).
const PROTEAM_OFF: usize = 115;
/// Offset within a cPbu record of the `team_alt` redundant team ID byte.
const TEAM_ALT_OFF: usize = 6;

/// Start of the edit-log region (single move on clean baseline).
const EDIT_LOG_OFF: usize = 0x1B97CC;
/// CRC counter byte.
const CRC_COUNTER_OFF: usize = 0x1AB24B;
/// Clean baseline CRC counter value.
const CRC_COUNTER_BASE: u8 = 0x09;

// ── Public API ──

/// Single player move descriptor.
pub struct PlayerMove {
    pub first_name: String,
    pub last_name: String,
    pub team_id: u8,
}

/// Apply one or more player moves to a packed roster save (clean baseline).
///
/// The input must be a packed save derived from `default_orig.db`
/// (no pre-existing edit-log modifications).
pub fn build_moves(packed_input: &[u8], moves: &[PlayerMove]) -> Result<Vec<u8>> {
    // 1. Decompress
    let header = roster_container::RosterHeader::parse(packed_input)
        .context("parse roster container header")?;
    let zlib_start = header.payload_offset;
    let zlib_end = packed_input.len().saturating_sub(4);
    let mut decompressor = ZlibDecoder::new(&packed_input[zlib_start..zlib_end]);
    let mut db = Vec::new();
    decompressor
        .read_to_end(&mut db)
        .context("decompress roster payload")?;

    // 2. Apply all moves (accumulating edits)
    for mv in moves {
        apply_single_move(&mut db, mv)?;
    }

    // 3. Reseal just the 3 Modding Studio CRCs
    ea_tdb::reseal_ms_crcs(&mut db).context("reseal MS CRCs")?;

    // 4. Pack back
    let field_0x2c = header.field_0x2c;
    pack_with_fdeflate(&db, packed_input, field_0x2c)
        .context("pack roster container")
}

// ── Player → eGlu record mapping (hardcoded from MS samples) ──

/// Known player cPbu record (1-indexed TDB record) → eGlu record to displace.
const KNOWN_EGLU: &[(usize, usize)] = &[
    (5593, 769),   // Auston Matthews
    (3498, 2788),  // Connor McDavid
    (3436, 1027),  // Leon Draisaitl
];

/// Find the eGlu record to displace for a given cPbu record index.
fn find_eglu_for_player(rec: usize) -> Option<usize> {
    KNOWN_EGLU
        .iter()
        .find(|(r, _)| *r == rec)
        .map(|(_, e)| *e)
}

// ── Internal helpers ──

fn apply_single_move(db: &mut [u8], mv: &PlayerMove) -> Result<()> {
    // Look up player in the CSV-derived database
    let name = format!("{} {}", mv.first_name, mv.last_name);
    let (csv_rec, _pid) = roster_db::find_player(&name)
        .with_context(|| format!("player \"{name}\" not found in roster database"))?;

    // CSV records are 0-indexed; TDB offsets use 1-indexed records
    let tdb_rec = csv_rec + 1;

    // Look up team info
    let team = roster_db::find_team(&mv.team_id.to_string())
        .or_else(|| roster_db::team_info(mv.team_id))
        .with_context(|| format!("unknown team: {}", mv.team_id))?;

    // 1. Update proteam and team_alt in cPbu record
    let cpbu_off = CPBU_BASE + tdb_rec * CPBU_REC_SIZE;
    let proteam_val = (team.id & 0x1F) << 3;
    db[cpbu_off + PROTEAM_OFF] = proteam_val;
    db[cpbu_off + TEAM_ALT_OFF] = team.id;

    let target_0idx = team.id.saturating_sub(1);

    eprintln!(
        "  {name}: csv_rec={csv_rec} tdb_rec={tdb_rec} proteam=0x{proteam_val:02x} (team {}) team_alt=0x{:02x}",
        team.id, team.id
    );

    // 2. Find and displace the player's eGlu record
    let eglu_rec = find_eglu_for_player(tdb_rec)
        .with_context(|| {
            format!(
                "player \"{name}\" (tdb_rec {tdb_rec}) has no known eGlu mapping.\n\
                 Current mappings: {:?}\n\
                 To add one: move this player in Modding Studio, diff the eGlu table (0x1AB73C, 16-byte recs).",
                KNOWN_EGLU
            )
        })?;

    let eglu_off = EGLU_BASE + eglu_rec * EGLU_REC_SIZE;

    let orig_b4 = db[eglu_off + 4];
    let orig_b5 = db[eglu_off + 5];
    let orig_b6 = db[eglu_off + 6];

    eprintln!(
        "  eGlu rec {eglu_rec}: orig [+4..+6]=[{orig_b4:02x} {orig_b5:02x} {orig_b6:02x}]"
    );

    // Decrement counter at byte 4, zero bytes 5-6
    db[eglu_off + 4] = if orig_b4 > 0 { orig_b4 - 1 } else { 0 };
    db[eglu_off + 5] = 0;
    db[eglu_off + 6] = 0;

    // 3. Write edit-log (single move at 0x1B97CC)
    db[EDIT_LOG_OFF + 0] = target_0idx;
    // bytes +1..+3 remain zero (0x00, 0x00, 0x00)
    db[EDIT_LOG_OFF + 4] = 0x01;       // constant
    db[EDIT_LOG_OFF + 5] = orig_b5;    // saved byte 5 from eGlu
    db[EDIT_LOG_OFF + 6] = orig_b6;    // saved byte 6 from eGlu
    db[EDIT_LOG_OFF + 7] = team.d3;    // parity bit (ClpB & 1)
    db[EDIT_LOG_OFF + 8] = team.d4;    // team-specific value
    db[EDIT_LOG_OFF + 9] = 0x80;       // constant

    // 4. Update eGlu tracking record (rec 3593, byte 0 = target CC)
    let tracker_off = EGLU_BASE + EGLU_TRACKER_REC * EGLU_REC_SIZE;
    db[tracker_off] = target_0idx;

    eprintln!(
        "  Edit-log@0x{EDIT_LOG_OFF:06X}: CC=0x{target_0idx:02x} D3=0x{:02x} D4=0x{:02x} tracker=0x{:02x}",
        team.d3, team.d4, target_0idx
    );

    // 5. Increment CRC counter
    // Start from base (0x09) if not yet incremented, otherwise increment
    if db[CRC_COUNTER_OFF] == CRC_COUNTER_BASE || db[CRC_COUNTER_OFF] == 0 {
        db[CRC_COUNTER_OFF] = CRC_COUNTER_BASE + 1; // 0x0A
    } else {
        db[CRC_COUNTER_OFF] = db[CRC_COUNTER_OFF].wrapping_add(1);
    }

    Ok(())
}

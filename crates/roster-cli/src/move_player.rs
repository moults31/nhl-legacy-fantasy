//! Apply a player team move to a roster save (TRADEEDIT5-based).
//!
//! Uses the proven Modding Studio normalization + byte-patching approach,
//! then packs with flate2 zlib compression and correct container checksums.

use std::io::Read;

use anyhow::{Context, Result};
use flate2::read::ZlibDecoder;
use roster_container::pack_with_fdeflate;

/// Pre-computed MS normalization bytes (21 positions from no-edit re-save vs TRADEEDIT5).
const NORMALIZATION_PATCHES: &[(usize, u8)] = &[
    // Hedman: PIT(24) → COL(8)
    (0x0CACAE, 0x08), // team_alt (record 1232 + 6)
    (0x0CAD1B, 0x40), // proteam (record 1232 + 115, team 8)
    // Edit-log baseline
    (0x1B97D1, 0x00), // zero old tracking marker 1
    (0x1B97D2, 0x00), // zero old tracking marker 2
    (0x1B97EC, 0x07), // restore tracking (team 8 - 1)
    (0x1B97F1, 0x70), // player marker byte 1
    (0x1B97F2, 0x50), // player marker byte 2
    (0x1B97F4, 0x98), // team * 19 (team 8)
    // CRC counter: 0x0B → 0x0C
    (0x1AB24B, 0x0C),
];

/// CRC region sizes (4 bytes each).
const CRC_A_OFFSET: usize = 0x1A4838;
const CRC_C_OFFSET: usize = 0x1AB258;
const CRC_D_OFFSET: usize = 0x1D5F2C;
const CRC_SIZE: usize = 4;

/// Known players with their record index (0-based) and tracking byte.
#[derive(Debug, Clone, Copy)]
pub struct KnownPlayer {
    pub first_name: &'static str,
    pub last_name: &'static str,
    pub record: usize,
    pub ctrl_off: usize,   // old entry zero position
    pub marker: u8,        // player identifier byte in edit log
}

pub const KNOWN_PLAYERS: &[KnownPlayer] = &[
    KnownPlayer {
        first_name: "Sidney",
        last_name: "Crosby",
        record: 688,
        ctrl_off: 0x1B97E1,
        marker: 0x10,
    },
    KnownPlayer {
        first_name: "Alex",
        last_name: "Ovechkin",
        record: 695,
        ctrl_off: 0x1ACE71,
        marker: 0xD0,
    },
    KnownPlayer {
        first_name: "Victor",
        last_name: "Hedman",
        record: 1232,
        ctrl_off: 0x1B97D1,
        marker: 0x50,
    },
];

/// Team name → team_id mapping.
pub fn find_team(name_or_id: &str) -> Result<u8> {
    // Try parsing as integer first
    if let Ok(id) = name_or_id.parse::<u8>() {
        if id >= 1 && id <= 32 {
            return Ok(id);
        }
    }
    let upper = name_or_id.to_uppercase();
    match upper.as_str() {
        "ANA" | "ANAH" | "ANAHEIM" => Ok(1),
        "BOS" | "BOSTON" => Ok(2),
        "BUF" | "BUFFALO" => Ok(3),
        "CGY" | "CALGARY" => Ok(5),
        "CAR" | "CAROLINA" => Ok(6),
        "CHI" | "CHICAGO" => Ok(7),
        "COL" | "COLORADO" => Ok(8),
        "CBJ" | "COLUMBUS" => Ok(9),
        "DAL" | "DALLAS" => Ok(10),
        "DET" | "DETROIT" => Ok(11),
        "EDM" | "EDMONTON" => Ok(12),
        "FLA" | "FLORIDA" => Ok(13),
        "LAK" | "LA" | "LOS ANGELES" => Ok(14),
        "MIN" | "MINNESOTA" => Ok(15),
        "MTL" | "MONTREAL" => Ok(16),
        "NSH" | "NASHVILLE" => Ok(17),
        "NJD" | "NJ" | "NEW JERSEY" => Ok(18),
        "NYI" | "NY ISLANDERS" => Ok(19),
        "NYR" | "NY RANGERS" => Ok(20),
        "OTT" | "OTTAWA" => Ok(21),
        "PHI" | "PHILADELPHIA" => Ok(22),
        "PIT" | "PITTSBURGH" => Ok(24),
        "SJS" | "SJ" | "SAN JOSE" => Ok(25),
        "STL" | "ST LOUIS" | "ST. LOUIS" => Ok(27),
        "TBL" | "TB" | "TAMPA BAY" => Ok(28),
        "TOR" | "TORONTO" => Ok(29),
        "VAN" | "VANCOUVER" => Ok(30),
        "VGK" | "VEGAS" => Ok(31),
        "WPG" | "WINNIPEG" => Ok(32),
        "WSH" | "WASHINGTON" => Ok(33),
        _ => anyhow::bail!("unknown team: {name_or_id}"),
    }
}

/// Apply MS normalization (21 bytes) to a TRADEEDIT5 decompressed DB.
pub fn apply_normalization(db: &mut [u8]) {
    for &(offset, value) in NORMALIZATION_PATCHES {
        db[offset] = value;
    }
}

/// Apply a single player team move (byte-patch: proteam, team_alt, edit-log, CRC counter).
///
/// After calling this for all players, copy CRCs from a reference MS file
/// via `copy_crcs_from_reference`.
pub fn apply_player_move(db: &mut [u8], player: &KnownPlayer, team_id: u8) {
    let base = 0x0A3168u64;
    let rs = base as usize + player.record * 132;

    // Player data: proteam (5-bit, high bits) and team_alt (full byte)
    db[rs + 115] = (team_id & 0x1F) << 3;
    db[rs + 6] = team_id;

    // Edit log: zero old tracking
    db[player.ctrl_off] = 0x00;
    db[player.ctrl_off + 1] = 0x00;

    // Edit log: write new tracking (slot at 0x1B97FC-0x1B9805)
    db[0x1B97FC] = team_id - 1;
    db[0x1B9801] = 0x41; // player ID prefix
    db[0x1B9802] = player.marker;
    db[0x1B9804] = team_editlog_byte(team_id);
    db[0x1B9805] = 0x80; // constant

    // CRC counter increment
    db[0x1AB24B] = db[0x1AB24B].wrapping_add(1);
}

/// Team-specific edit-log byte at +4 (offset from CRC-track slot base).
fn team_editlog_byte(team_id: u8) -> u8 {
    // Most teams: team_id * 19; CGY is off by 2
    match team_id {
        5 => 0x5D, // CGY (should be 0x5F by formula)
        _ => team_id * 19,
    }
}

/// Copy the 3 unknown CRC regions from a reference MS save.
pub fn copy_crcs_from_reference(db: &mut [u8], reference: &[u8]) -> Result<()> {
    if reference.len() < CRC_D_OFFSET + CRC_SIZE {
        anyhow::bail!("reference file too small for CRC regions");
    }
    db[CRC_A_OFFSET..CRC_A_OFFSET + CRC_SIZE]
        .copy_from_slice(&reference[CRC_A_OFFSET..CRC_A_OFFSET + CRC_SIZE]);
    db[CRC_C_OFFSET..CRC_C_OFFSET + CRC_SIZE]
        .copy_from_slice(&reference[CRC_C_OFFSET..CRC_C_OFFSET + CRC_SIZE]);
    db[CRC_D_OFFSET..CRC_D_OFFSET + CRC_SIZE]
        .copy_from_slice(&reference[CRC_D_OFFSET..CRC_D_OFFSET + CRC_SIZE]);
    Ok(())
}

/// Build a full move: unpack input → normalize → edit → pack with flate2.
pub fn build_move(
    packed_input: &[u8],
    player: &KnownPlayer,
    team_id: u8,
    reference_db: Option<&[u8]>,
) -> Result<Vec<u8>> {
    // Unpack: decompress zlib payload after 48-byte header
    let header = roster_container::RosterHeader::parse(packed_input)
        .context("parse roster container header")?;
    let zlib_start = header.payload_offset;
    let zlib_end = packed_input.len().saturating_sub(4); // last 4 are padding/container crc
    let mut decompressor = ZlibDecoder::new(&packed_input[zlib_start..zlib_end]);
    let mut db = Vec::new();
    decompressor
        .read_to_end(&mut db)
        .context("decompress roster payload")?;

    // Apply normalization (from TRADEEDIT5 baseline)
    apply_normalization(&mut db);

    // Apply player edit
    apply_player_move(&mut db, player, team_id);

    // Copy CRCs from reference if provided
    if let Some(reference) = reference_db {
        copy_crcs_from_reference(&mut db, reference)?;
    }

    // Pack with flate2
    let field_0x2c = header.field_0x2c;
    pack_with_fdeflate(&db, packed_input, field_0x2c)
        .context("pack roster container")
}

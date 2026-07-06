//! Apply a player team move to a roster save (TRADEEDIT5-based).
//!
//! Pipeline: unpack → MS normalization → player edit → reseal 3 CRCs → pack with flate2.

use std::io::Read;

use anyhow::{Context, Result};
use flate2::read::ZlibDecoder;
use roster_container::pack_with_fdeflate;

/// Pre-computed MS normalization bytes from no-edit re-save vs TRADEEDIT5 (9 positions).
const NORMALIZATION_PATCHES: &[(usize, u8)] = &[
    (0x0CACAE, 0x08), // Hedman team_alt
    (0x0CAD1B, 0x40), // Hedman proteam
    (0x1B97D1, 0x00), // edit-log: zero old marker 1
    (0x1B97D2, 0x00), // edit-log: zero old marker 2
    (0x1B97EC, 0x07), // edit-log: restore team-1
    (0x1B97F1, 0x70), // edit-log: player marker 1
    (0x1B97F2, 0x50), // edit-log: player marker 2
    (0x1B97F4, 0x98), // edit-log: team*19
    (0x1AB24B, 0x0C), // CRC counter: 0x0B → 0x0C
];

/// Known players with their record index (0-based) and edit-log tracking byte.
#[derive(Debug, Clone, Copy)]
pub struct KnownPlayer {
    pub first_name: &'static str,
    pub last_name: &'static str,
    pub record: usize,
    pub ctrl_off: usize,
    pub marker: u8,
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
    if let Ok(id) = name_or_id.parse::<u8>() {
        if (1..=33).contains(&id) {
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

/// Apply MS normalization (9 bytes) to a TRADEEDIT5 decompressed DB.
pub fn apply_normalization(db: &mut [u8]) {
    for &(offset, value) in NORMALIZATION_PATCHES {
        db[offset] = value;
    }
}

/// Apply a single player team move (proteam, team_alt, edit-log, CRC counter).
///
/// Call [`apply_normalization`] first, then this for each player move,
/// then [`ea_tdb::reseal_ms_crcs`] to recompute the 3 affected CRCs.
pub fn apply_player_move(db: &mut [u8], player: &KnownPlayer, team_id: u8) {
    let base = 0x0A3168u64;
    let rs = base as usize + player.record * 132;

    db[rs + 115] = (team_id & 0x1F) << 3;
    db[rs + 6] = team_id;

    db[player.ctrl_off] = 0x00;
    db[player.ctrl_off + 1] = 0x00;

    db[0x1B97FC] = team_id - 1;
    db[0x1B9801] = 0x41;
    db[0x1B9802] = player.marker;
    db[0x1B9804] = team_editlog_byte(team_id);
    db[0x1B9805] = 0x80;

    db[0x1AB24B] = db[0x1AB24B].wrapping_add(1);
}

fn team_editlog_byte(team_id: u8) -> u8 {
    match team_id {
        5 => 0x5D,
        _ => team_id * 19,
    }
}

/// Build a full move: unpack → normalize → edit → reseal CRCs → pack with flate2.
pub fn build_move(
    packed_input: &[u8],
    player: &KnownPlayer,
    team_id: u8,
) -> Result<Vec<u8>> {
    let header = roster_container::RosterHeader::parse(packed_input)
        .context("parse roster container header")?;
    let zlib_start = header.payload_offset;
    let zlib_end = packed_input.len().saturating_sub(4);
    let mut decompressor = ZlibDecoder::new(&packed_input[zlib_start..zlib_end]);
    let mut db = Vec::new();
    decompressor
        .read_to_end(&mut db)
        .context("decompress roster payload")?;

    apply_normalization(&mut db);
    apply_player_move(&mut db, player, team_id);
    ea_tdb::reseal_ms_crcs(&mut db).context("reseal MS CRCs")?;

    let field_0x2c = header.field_0x2c;
    pack_with_fdeflate(&db, packed_input, field_0x2c)
        .context("pack roster container")
}

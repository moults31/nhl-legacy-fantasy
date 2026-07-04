use ea_tdb::TdbFile;

use crate::export::{PlayerExport, RosterExport};
use crate::legacy::LegacyRosterTables;
use crate::string_field::read_string_field;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ImportPatch {
    pub record: usize,
    pub proteam_before: u64,
    pub proteam_after: u64,
}

pub fn apply_import(db: &mut [u8], import: &RosterExport) -> ea_tdb::Result<Vec<ImportPatch>> {
    if import.schema != "nhl-legacy-roster/0.1" {
        return Err(ea_tdb::Error::InvalidRecordAccess {
            reason: "unsupported roster JSON schema",
        });
    }

    let file = TdbFile::parse(db)?;
    let entry = file
        .directory
        .get(LegacyRosterTables::PLAYER_BIO)
        .ok_or(ea_tdb::Error::InvalidRecordAccess {
            reason: "player bio table cPbu missing",
        })?;
    let layout = file.table_layout(db, entry)?;
    let proteam_field = layout
        .find_field(LegacyRosterTables::PLAYER_PROTEAM)
        .ok_or(ea_tdb::Error::InvalidRecordAccess {
            reason: "player proteam field WBbd missing",
        })?;
    let first_name = layout
        .find_field(LegacyRosterTables::PLAYER_FIRST_NAME)
        .ok_or(ea_tdb::Error::InvalidRecordAccess {
            reason: "player first name field PedH missing",
        })?;
    let last_name = layout
        .find_field(LegacyRosterTables::PLAYER_LAST_NAME)
        .ok_or(ea_tdb::Error::InvalidRecordAccess {
            reason: "player last name field RMbQ missing",
        })?;

    let mut patches = Vec::new();
    for player in &import.players {
        let record = resolve_player_record(db, &layout, first_name, last_name, player)?;
        let before = layout.read_field(db, record, proteam_field, file.header.endian)?;
        let after = player.proteam as u64;
        if before == after {
            continue;
        }
        layout.write_field(db, record, proteam_field, after, file.header.endian)?;
        patches.push(ImportPatch {
            record,
            proteam_before: before,
            proteam_after: after,
        });
    }
    Ok(patches)
}

fn resolve_player_record(
    db: &[u8],
    layout: &ea_tdb::TableLayout,
    first_name: &ea_tdb::FieldDescriptor,
    last_name: &ea_tdb::FieldDescriptor,
    player: &PlayerExport,
) -> ea_tdb::Result<usize> {
    let max_records = layout.info.current_records as usize;
    if (player.record as usize) < max_records {
        let record = player.record as usize;
        if player_matches(db, layout, first_name, last_name, record, player)? {
            return Ok(record);
        }
    }

    for record in 0..max_records {
        if player_matches(db, layout, first_name, last_name, record, player)? {
            return Ok(record);
        }
    }

    Err(ea_tdb::Error::InvalidRecordAccess {
        reason: "import player not found in cPbu",
    })
}

fn player_matches(
    db: &[u8],
    layout: &ea_tdb::TableLayout,
    first_name: &ea_tdb::FieldDescriptor,
    last_name: &ea_tdb::FieldDescriptor,
    record: usize,
    player: &PlayerExport,
) -> ea_tdb::Result<bool> {
    let last = read_string_field(layout, db, record, last_name)?;
    if last != player.last_name {
        return Ok(false);
    }
    let first = read_string_field(layout, db, record, first_name)?;
    Ok(first == player.first_name)
}

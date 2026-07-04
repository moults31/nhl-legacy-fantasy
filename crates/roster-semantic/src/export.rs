use ea_tdb::TdbFile;

use crate::legacy::LegacyRosterTables;
use crate::string_field::read_string_field;

const SCHEMA: &str = "nhl-legacy-roster/0.1";

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct RosterExport {
    pub schema: String,
    pub teams: Vec<TeamExport>,
    pub players: Vec<PlayerExport>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct TeamExport {
    pub record: u32,
    pub city: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub full_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub abbrev: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct PlayerExport {
    pub record: u32,
    pub first_name: String,
    pub last_name: String,
    /// Exhibition roster assignment (`cPbu.WBbd` / `proteam`).
    pub proteam: u32,
}

pub fn export_roster(db: &[u8]) -> ea_tdb::Result<RosterExport> {
    let file = TdbFile::parse(db)?;
    let teams = export_teams(db, &file)?;
    let players = export_players(db, &file)?;
    Ok(RosterExport {
        schema: SCHEMA.to_string(),
        teams,
        players,
    })
}

fn export_teams(db: &[u8], file: &TdbFile) -> ea_tdb::Result<Vec<TeamExport>> {
    let entry = file
        .directory
        .get(LegacyRosterTables::TEAMS)
        .ok_or(ea_tdb::Error::InvalidRecordAccess {
            reason: "teams table ttOk missing",
        })?;
    let layout = file.table_layout(db, entry)?;
    let city = layout
        .find_field(LegacyRosterTables::TEAM_CITY)
        .ok_or(ea_tdb::Error::InvalidRecordAccess {
            reason: "team city field ITNQ missing",
        })?;
    let full_name = layout.find_field(LegacyRosterTables::TEAM_FULL_NAME);
    let abbrev = layout.find_field(LegacyRosterTables::TEAM_ABBREV);

    let mut teams = Vec::with_capacity(layout.info.current_records as usize);
    for record in 0..layout.info.current_records as usize {
        let city_name = read_string_field(&layout, db, record, city)?;
        if city_name.is_empty() {
            continue;
        }
        teams.push(TeamExport {
            record: record as u32,
            city: city_name,
            full_name: full_name
                .map(|field| read_string_field(&layout, db, record, field))
                .transpose()?,
            abbrev: abbrev
                .map(|field| read_string_field(&layout, db, record, field))
                .transpose()?,
        });
    }
    Ok(teams)
}

fn export_players(db: &[u8], file: &TdbFile) -> ea_tdb::Result<Vec<PlayerExport>> {
    let entry = file
        .directory
        .get(LegacyRosterTables::PLAYER_BIO)
        .ok_or(ea_tdb::Error::InvalidRecordAccess {
            reason: "player bio table cPbu missing",
        })?;
    let layout = file.table_layout(db, entry)?;
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
    let proteam = layout
        .find_field(LegacyRosterTables::PLAYER_PROTEAM)
        .ok_or(ea_tdb::Error::InvalidRecordAccess {
            reason: "player proteam field WBbd missing",
        })?;

    let mut players = Vec::with_capacity(layout.info.current_records as usize);
    for record in 0..layout.info.current_records as usize {
        let last = read_string_field(&layout, db, record, last_name)?;
        if last.is_empty() {
            continue;
        }
        let first = read_string_field(&layout, db, record, first_name)?;
        let team_id = layout.read_field(db, record, proteam, file.header.endian)? as u32;
        players.push(PlayerExport {
            record: record as u32,
            first_name: first,
            last_name: last,
            proteam: team_id,
        });
    }
    Ok(players)
}

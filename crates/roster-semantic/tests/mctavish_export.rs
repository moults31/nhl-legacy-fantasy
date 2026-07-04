//! Export/import integration tests using the McTavish fixture pair.

use std::path::PathBuf;

use roster_semantic::{apply_import, export_roster, RosterExport};

fn load_db(name: &str) -> Option<Vec<u8>> {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../_local/game-saves/xbox")
        .join(name);
    if !path.is_file() {
        eprintln!("skip: {} missing", path.display());
        return None;
    }
    let container = std::fs::read(&path).ok()?;
    roster_container::unpack(&container).ok()
}

fn find_mctavish(export: &RosterExport) -> Option<&roster_semantic::PlayerExport> {
    export
        .players
        .iter()
        .find(|p| p.last_name == "McTavish" && p.first_name == "Mason")
}

#[test]
fn export_mctavish_proteam_roster1() {
    let Some(db) = load_db("roster1.bin") else {
        return;
    };
    let export = export_roster(&db).expect("export");
    assert_eq!(export.schema, "nhl-legacy-roster/0.1");
    assert!(!export.teams.is_empty());
    assert!(!export.players.is_empty());

    let mct = find_mctavish(&export).expect("McTavish");
    assert_eq!(mct.proteam, 1);
    assert_eq!(mct.record, 1424);

    let anaheim = export
        .teams
        .iter()
        .find(|t| t.city == "Anaheim")
        .expect("Anaheim team row");
    assert_eq!(anaheim.record, 0);
    assert_eq!(anaheim.abbrev.as_deref(), Some("ANA"));
}

#[test]
fn export_mctavish_proteam_testroster() {
    let Some(db) = load_db("testroster.bin") else {
        return;
    };
    let export = export_roster(&db).expect("export");
    let mct = find_mctavish(&export).expect("McTavish");
    assert_eq!(mct.proteam, 25);
}

#[test]
fn import_proteam_patch_round_trip() {
    let Some(mut db) = load_db("testroster.bin") else {
        return;
    };
    let export = export_roster(&db).expect("export");
    let mut import = export.clone();
    let mct = find_mctavish(&mut import).expect("McTavish");
    assert_eq!(mct.proteam, 25);

    import.players.retain(|p| p.last_name == "McTavish" && p.first_name == "Mason");
    import.players[0].proteam = 1;

    let patches = apply_import(&mut db, &import).expect("import");
    assert_eq!(patches.len(), 1);
    assert_eq!(patches[0].proteam_before, 25);
    assert_eq!(patches[0].proteam_after, 1);

    let after = export_roster(&db).expect("re-export");
    let mct = find_mctavish(&after).expect("McTavish");
    assert_eq!(mct.proteam, 1);
}

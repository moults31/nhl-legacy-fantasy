//! M3 acceptance: edit a bit-packed field in Rust, reseal TDB CRCs, verify self-consistency.
//!
//! This tests the complete TDB edit pipeline without Modding Studio:
//!   unpack game save → reseal baseline CRCs → edit field → reseal → verify CRCs

use ea_tdb::{reseal_checksums, verify_checksums, TdbFile};
use roster_container::unpack;
use std::path::{Path, PathBuf};

fn roster_save_path() -> Option<PathBuf> {
    // Try the McTavish pair first.
    let pair = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../_local/game-saves/xbox/testroster.bin");
    if pair.is_file() {
        return Some(pair);
    }
    // Fall back to the Proton save directory.
    let proton = Path::new(
        r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\00000001\ROSTER 20260307213511\ROSTER 20260307213511",
    );
    if proton.is_file() {
        return Some(proton.to_path_buf());
    }
    None
}

#[test]
fn edit_field_reseal_self_verifies() {
    let Some(path) = roster_save_path() else {
        eprintln!("skip: no roster save available");
        return;
    };
    let container = std::fs::read(&path).expect("read save");
    let mut db = unpack(&container).expect("unpack");

    // Step 1: Reseal the stale game-saved CRCs to establish a clean baseline.
    reseal_checksums(&mut db).expect("baseline reseal");
    verify_checksums(&db).expect("baseline self-verifies");

    // Step 2: Pick any cPbu record and edit its proteam field.
    let file = TdbFile::parse(&db).expect("parse");
    let entry = file.directory.get("cPbu").expect("cPbu must exist");
    let layout = file.table_layout(&db, entry).expect("cpbu layout");
    let proteam = layout.find_field("WBbd").expect("proteam field must exist");

    let original = layout
        .read_field(&db, 0, proteam, file.header.endian)
        .expect("read proteam record 0");
    let edited = if original == 0 { 1 } else { 0 };

    layout
        .write_field(&mut db, 0, proteam, edited, file.header.endian)
        .expect("write proteam");

    let readback = layout
        .read_field(&db, 0, proteam, file.header.endian)
        .expect("read back");
    assert_eq!(readback, edited, "edit persisted in-memory");

    // Step 3: Reseal after edit — the CRC chain must self-verify.
    reseal_checksums(&mut db).expect("reseal after edit");
    verify_checksums(&db).expect("resealed DB should self-verify");

    // Step 4: Idempotency — resealing again produces identical bytes.
    let after_edit = db.clone();
    reseal_checksums(&mut db).expect("second reseal");
    assert_eq!(db, after_edit, "reseal must be idempotent after edit");

    // Step 5: Restore original value and confirm the chain stays consistent.
    layout
        .write_field(&mut db, 0, proteam, original, file.header.endian)
        .expect("restore proteam");
    reseal_checksums(&mut db).expect("reseal after restore");
    verify_checksums(&db).expect("restored DB should self-verify");
}

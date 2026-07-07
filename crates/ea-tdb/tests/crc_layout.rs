//! Validates EA DB Editor CRC layout and reseal self-consistency on full TDB payloads.

use ea_tdb::{reseal_checksums, verify_checksums, TdbFile};
use std::fs;

fn try_unpacked_roster_db() -> Option<Vec<u8>> {
    let db_path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../tests/fixtures/xbox/roster.bin"
    );
    if !std::path::Path::new(db_path).exists() {
        eprintln!("skip: no roster fixture");
        return None;
    }
    let container = fs::read(db_path).ok()?;
    roster_container::unpack(&container).ok()
}

#[test]
fn reseal_is_idempotent_on_full_unpacked_db() {
    let Some(mut db) = try_unpacked_roster_db() else {
        return;
    };
    reseal_checksums(&mut db).expect("first reseal");
    let once = db.clone();
    reseal_checksums(&mut db).expect("second reseal");
    assert_eq!(db, once);
}

#[test]
fn resealed_unpacked_roster_self_verifies() {
    let Some(mut db) = try_unpacked_roster_db() else {
        return;
    };
    reseal_checksums(&mut db).expect("reseal");
    verify_checksums(&db).expect("resealed TDB CRCs should self-verify");
}

#[test]
fn header_and_table_crc_formulas_on_resealed_db() {
    let Some(mut db) = try_unpacked_roster_db() else {
        return;
    };
    reseal_checksums(&mut db).expect("reseal");

    let file = TdbFile::parse(&db).expect("parse");
    // Stored header CRC is !crc32_be_standard over first 20 bytes
    assert_eq!(file.header_crc, !ea_tdb::crc32_be_standard(&db[..20]));

    let ajmx = file.directory.get("ajmx").expect("ajmx");
    let info_off = file.directory.table_data_start + ajmx.data_offset as usize;
    let stored_header_crc =
        u32::from_be_bytes(db[info_off + 36..info_off + 40].try_into().unwrap());
    // Stored table header CRC is !crc32_be_standard over 32 bytes at info+4
    assert_eq!(
        stored_header_crc,
        !ea_tdb::crc32_be_standard(&db[info_off + 4..info_off + 36])
    );
}

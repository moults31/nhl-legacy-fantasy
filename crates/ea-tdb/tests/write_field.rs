//! Patch a bit-packed field and reseal TDB CRCs.

use ea_tdb::{reseal_checksums, verify_checksums, Endian, TdbFile};

#[test]
fn write_field_round_trip_and_reseal_self_verifies() {
    let db_path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../tests/fixtures/xbox/roster.bin"
    );
    if !std::path::Path::new(db_path).exists() {
        eprintln!("skip: no roster fixture");
        return;
    }

    let container = std::fs::read(db_path).expect("roster");
    let mut db = roster_container::unpack(&container).expect("unpack");
    reseal_checksums(&mut db).expect("establish tool-written CRC baseline");

    let file = TdbFile::parse(&db).expect("parse");
    let ajmx = file.directory.get("ajmx").expect("ajmx");
    let info_off = file.directory.table_data_start + ajmx.data_offset as usize;
    let layout = ea_tdb::TableLayout::parse(&db, info_off).expect("layout");
    let field = layout.find_field("xFXw").expect("xFXw");
    let endian = file.header.endian;

    let before = layout
        .read_field(&db, 0, field, endian)
        .expect("read record 0");
    layout
        .write_field(&mut db, 0, field, before, endian)
        .expect("write same value");
    reseal_checksums(&mut db).expect("reseal");
    verify_checksums(&db).expect("resealed db self-verifies");

    let after = layout
        .read_field(&db, 0, field, endian)
        .expect("read back");
    assert_eq!(before, after);
}

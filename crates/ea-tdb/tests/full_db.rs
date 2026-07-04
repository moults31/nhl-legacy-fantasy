//! Integration tests requiring the gitignored Proton roster fixture.

use ea_tdb::{Endian, TdbFile};

#[test]
fn parses_full_legacy_roster_db() {
    let roster = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../tests/fixtures/xbox/roster.bin"
    );
    if !std::path::Path::new(roster).exists() {
        eprintln!("skip: {roster} not present");
        return;
    }
    let container = std::fs::read(roster).expect("roster");
    let db = roster_container::unpack(&container).expect("unpack");
    let file = TdbFile::parse(&db).expect("tdb");
    assert_eq!(file.directory.entries.len(), 39);
    let ajmx = file.directory.get("ajmx").expect("ajmx");
    let layout = file.table_layout(&db, ajmx).expect("ajmx layout");
    let xfxw = layout.find_field("xFXw").expect("xFXw ref");
    assert_eq!(xfxw.bit_width, 7);
    let _ = layout
        .read_field(&db, 0, xfxw, Endian::Big)
        .expect("read xFXw ref from record 0");
}

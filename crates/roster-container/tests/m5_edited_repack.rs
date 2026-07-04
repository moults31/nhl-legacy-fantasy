//! Build M5 verification saves into `_local/game-saves/xbox/m5-staging/`.
//!
//! `M5MCT01` is a **research artifact**: TDB edit + repack seals container checksums but
//! is known to fail in-game load until we port Modding Studio `pack_xbox_save` deflate.
//! Do not install without `--remove` cleanup if testing.

use std::path::Path;

use ea_tdb::TdbFile;
use roster_container::{pack_with_field_0x2c, unpack, verify_checksums, RosterHeader};

fn fixture_root() -> std::path::PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../_local/game-saves/xbox")
}

fn staging_dir() -> std::path::PathBuf {
    fixture_root().join("m5-staging")
}

fn mctavish_proteam(db: &[u8]) -> Option<(usize, u64)> {
    let file = TdbFile::parse(db).ok()?;
    let entry = file.directory.get("cPbu")?;
    let layout = file.table_layout(db, entry).ok()?;
    let proteam = layout.find_field("WBbd")?;
    let rlb = layout.info.record_length_bytes as usize;
    let base = layout.records_offset();
    for record in 0..layout.info.current_records as usize {
        let start = base + record * rlb;
        let end = start + rlb;
        if db.get(start..end)?.windows(8).any(|w| w == b"McTavish") {
            let team_id = layout
                .read_field(db, record, proteam, file.header.endian)
                .ok()?;
            return Some((record, team_id));
        }
    }
    None
}

fn write_mctavish_proteam(db: &mut [u8], team: u64) {
    let file = TdbFile::parse(db).expect("parse");
    let entry = file.directory.get("cPbu").expect("cPbu");
    let layout = file.table_layout(db, entry).expect("layout");
    let proteam = layout.find_field("WBbd").expect("WBbd");
    let (record, _) = mctavish_proteam(db).expect("McTavish");
    layout
        .write_field(db, record, proteam, team, file.header.endian)
        .expect("write proteam");
}

#[test]
fn build_m5mct01_edited_repack() {
    let root = fixture_root();
    let testroster = root.join("testroster.bin");
    if !testroster.is_file() {
        eprintln!("skip: McTavish pair not present");
        return;
    }

    let test_container = std::fs::read(&testroster).expect("testroster");
    let mut db = unpack(&test_container).expect("unpack testroster");

    let (_, team_before) = mctavish_proteam(&db).expect("McTavish on STL");
    assert_eq!(team_before, 25);

    write_mctavish_proteam(&mut db, 1);
    let (_, team_after) = mctavish_proteam(&db).expect("McTavish after edit");
    assert_eq!(team_after, 1);

    let h_test = RosterHeader::parse(&test_container).expect("testroster header");
    // Edited DB keeps testroster layout; use testroster @0x2c (roster1 value failed load at ~818 KB).
    let packed = pack_with_field_0x2c(&db, &test_container, h_test.field_0x2c)
        .expect("pack edited db");

    verify_checksums(&packed).expect("sealed checksums");
    assert_eq!(&packed[48..50], [0x78, 0x9c]);
    assert!(
        packed.len() > 2_000_000,
        "edited save should use near-stored deflate (~2.45 MB), got {}",
        packed.len()
    );

    let out = staging_dir().join("M5MCT01.bin");
    std::fs::create_dir_all(staging_dir()).expect("staging dir");
    std::fs::write(&out, &packed).expect("write M5MCT01");
    eprintln!("wrote {} ({} bytes)", out.display(), packed.len());
}

//! McTavish Anaheim → St. Louis edit pair from the 2026-07-04 in-game session.
//!
//! Requires `_local/game-saves/xbox/{roster1,testroster}.bin` (see docs/LOCAL-ARTIFACTS.md).

use std::path::{Path, PathBuf};

use roster_container::{unpack, RosterHeader};

fn fixture_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../_local/game-saves/xbox")
}

fn try_read_pair() -> Option<(Vec<u8>, Vec<u8>)> {
    let root = fixture_root();
    let before = root.join("roster1.bin");
    let after = root.join("testroster.bin");
    if !before.is_file() || !after.is_file() {
        eprintln!(
            "skip: McTavish pair not present (expected {} and {})",
            before.display(),
            after.display()
        );
        return None;
    }
    Some((
        std::fs::read(&before).expect("roster1.bin"),
        std::fs::read(&after).expect("testroster.bin"),
    ))
}

fn mctavish_offset(db: &[u8]) -> Option<usize> {
    db.windows(8).position(|w| w == b"McTavish")
}

fn diff_byte_count(a: &[u8], b: &[u8]) -> usize {
    a.iter().zip(b.iter()).filter(|(x, y)| x != y).count()
}

#[test]
fn mctavish_present_in_both_saves() {
    let Some((before_container, after_container)) = try_read_pair() else {
        return;
    };

    let before = unpack(&before_container).expect("unpack roster1");
    let after = unpack(&after_container).expect("unpack testroster");

    assert!(mctavish_offset(&before).is_some(), "McTavish in roster1 TDB");
    assert!(mctavish_offset(&after).is_some(), "McTavish in testroster TDB");
}

#[test]
fn mctavish_pair_edited_but_same_shape() {
    let Some((before_container, after_container)) = try_read_pair() else {
        return;
    };

    let before = unpack(&before_container).expect("unpack roster1");
    let after = unpack(&after_container).expect("unpack testroster");

    assert_eq!(before.len(), after.len());
    let diffs = diff_byte_count(&before, &after);
    assert!(
        diffs > 0 && diffs < before.len(),
        "expected partial TDB edit, got {diffs} differing bytes of {}",
        before.len()
    );

    let file_before = ea_tdb::TdbFile::parse(&before).expect("parse roster1 TDB");
    let file_after = ea_tdb::TdbFile::parse(&after).expect("parse testroster TDB");
    assert_eq!(file_before.directory.entries.len(), 39);
    assert_eq!(
        file_before.directory.entries.len(),
        file_after.directory.entries.len()
    );
}

#[test]
fn mctavish_pair_container_checksums_differ() {
    let Some((before_container, after_container)) = try_read_pair() else {
        return;
    };

    let h_before = RosterHeader::parse(&before_container).expect("header roster1");
    let h_after = RosterHeader::parse(&after_container).expect("header testroster");

    assert_eq!(h_before.uncompressed_size, h_after.uncompressed_size);
    assert_ne!(
        h_before.checksum, h_after.checksum,
        "edited save should change RosterFile checksum @ 0x10"
    );
}

#[test]
fn mctavish_save_reorders_records() {
    let Some((before_container, after_container)) = try_read_pair() else {
        return;
    };

    let before = unpack(&before_container).expect("unpack roster1");
    let after = unpack(&after_container).expect("unpack testroster");

    let off_before = mctavish_offset(&before).expect("McTavish in roster1");
    let off_after = mctavish_offset(&after).expect("McTavish in testroster");

    // In-game save rewrites shift record layout; do not assume stable file offsets.
    assert_ne!(
        off_before, off_after,
        "McTavish bio offset should move when the DB is re-saved"
    );
}

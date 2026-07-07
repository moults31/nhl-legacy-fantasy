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

fn mctavish_cpbu_record(db: &[u8]) -> Option<(usize, u64)> {
    let file = ea_tdb::TdbFile::parse(db).ok()?;
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
fn mctavish_pair_tdb_internal_crcs_unchanged_on_game_save() {
    let Some((before_container, after_container)) = try_read_pair() else {
        return;
    };

    let before = unpack(&before_container).expect("unpack roster1");
    let after = unpack(&after_container).expect("unpack testroster");

    let file_before = ea_tdb::TdbFile::parse(&before).expect("parse roster1 TDB");
    let file_after = ea_tdb::TdbFile::parse(&after).expect("parse testroster TDB");

    assert_eq!(
        file_before.header_crc, file_after.header_crc,
        "Legacy in-game save does not rewrite TDB header CRC @ 0x14"
    );

    let ajmx_before = file_before.directory.get("ajmx").expect("ajmx");
    let ajmx_after = file_after.directory.get("ajmx").expect("ajmx");
    let info_before =
        file_before.directory.table_data_start + ajmx_before.data_offset as usize;
    let info_after = file_after.directory.table_data_start + ajmx_after.data_offset as usize;

    let prior_before = u32::from_be_bytes(
        before[info_before..info_before + 4]
            .try_into()
            .expect("prior"),
    );
    let prior_after = u32::from_be_bytes(
        after[info_after..info_after + 4]
            .try_into()
            .expect("prior"),
    );
    let hcrc_before = u32::from_be_bytes(
        before[info_before + 36..info_before + 40]
            .try_into()
            .expect("hcrc"),
    );
    let hcrc_after = u32::from_be_bytes(
        after[info_after + 36..info_after + 40]
            .try_into()
            .expect("hcrc"),
    );

    assert_eq!(prior_before, prior_after);
    assert_eq!(hcrc_before, hcrc_after);
}

/// In-game player movement updates `cPbu.WBbd` (`proteam`), not `BSXd` (`team`).
#[test]
fn mctavish_proteam_on_cpbu() {
    let Some((before_container, after_container)) = try_read_pair() else {
        return;
    };

    let before = unpack(&before_container).expect("unpack roster1");
    let after = unpack(&after_container).expect("unpack testroster");

    let (rec_before, team_before) =
        mctavish_cpbu_record(&before).expect("McTavish in roster1 cPbu");
    let (rec_after, team_after) =
        mctavish_cpbu_record(&after).expect("McTavish in testroster cPbu");

    assert_eq!(rec_before, rec_after, "record index stable across pair");
    assert_eq!(team_before, 1, "roster1: McTavish on Anaheim (proteam=1)");
    assert_eq!(team_after, 25, "testroster: McTavish on St. Louis (proteam=25)");
}

#[test]
fn mctavish_write_proteam_round_trip() {
    let Some((_before_container, after_container)) = try_read_pair() else {
        return;
    };

    let mut db = unpack(&after_container).expect("unpack testroster");
    let file = ea_tdb::TdbFile::parse(&db).expect("parse");
    let entry = file.directory.get("cPbu").expect("cPbu");
    let layout = file.table_layout(&db, entry).expect("layout");
    let proteam = layout.find_field("WBbd").expect("WBbd");

    let (record, team_before) = mctavish_cpbu_record(&db).expect("McTavish");
    assert_eq!(team_before, 25);

    layout
        .write_field(&mut db, record, proteam, 1, file.header.endian)
        .expect("write Anaheim");
    let team_after = layout
        .read_field(&db, record, proteam, file.header.endian)
        .expect("read back");
    assert_eq!(team_after, 1);
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

#[test]
fn dump_wbbd_byte_layout() {
    let t5 = std::path::Path::new(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../_local/game-saves/xbox/TRADEEDIT5"
    ));
    if !t5.exists() {
        eprintln!("TRADEEDIT5 not found, skip");
        return;
    }
    let container = std::fs::read(t5).expect("read TRADEEDIT5");
    let db = ::roster_container::unpack(&container).expect("unpack");

    let file = ea_tdb::TdbFile::parse(&db).expect("parse");
    let entry = file.directory.get("cPbu").expect("cPbu");
    let layout = file.table_layout(&db, entry).expect("layout");
    let proteam = layout.find_field("WBbd").expect("WBbd");

    eprintln!(
        "WBbd: record_bit_offset={} bit_width={}",
        proteam.record_bit_offset, proteam.bit_width
    );

    let rlb = layout.info.record_length_bytes as usize;
    let base = layout.records_offset();

    for (name, rec) in &[("Crosby", 688usize), ("Ovechkin", 695), ("Hedman", 1232)] {
        let val = layout
            .read_field(&db, *rec, proteam, file.header.endian)
            .expect("read field");
        let bit_off = proteam.record_bit_offset as usize;
        let byte_start = bit_off / 8;
        let byte_end = (bit_off + proteam.bit_width as usize + 7) / 8;
        let rec_start = base + rec * rlb;
        let abs_off = rec_start + byte_start;
        let bytes: Vec<_> = (rec_start + byte_start..rec_start + byte_end)
            .map(|i| format!("{:02X}", db[i]))
            .collect();

        // Also show the NEXT field to understand byte sharing
        let next_field = layout.fields.iter()
            .filter(|f| f.record_bit_offset > proteam.record_bit_offset)
            .min_by_key(|f| f.record_bit_offset);
        
        let next_info = if let Some(nf) = next_field {
            let n_byte_start = nf.record_bit_offset as usize / 8;
            let shares_byte = n_byte_start == byte_start;
            format!("next_field={} bit_off={} shares_byte={}", nf.field_id.as_str(), nf.record_bit_offset, shares_byte)
        } else {
            "no next field".to_string()
        };

        eprintln!(
            "{name:>10} rec={rec:4} proteam={val:3} DB_offset=0x{abs_off:06X} span={} bytes=[{}] | {next_info}",
            byte_end - byte_start,
            bytes.join(" ")
        );
    }
}

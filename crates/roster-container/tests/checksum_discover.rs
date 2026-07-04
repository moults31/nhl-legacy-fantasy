//! Brute-force discovery for RosterFile header hashes @ 0x10 and 0x28.
//!
//! Run: `cargo test -p roster-container discover_ -- --nocapture`

use roster_container::EaChecksum;
use ea_tdb::Crc32Be;

fn fixture_paths() -> Option<(std::path::PathBuf, std::path::PathBuf)> {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../_local/game-saves/xbox");
    let a = root.join("roster1.bin");
    let b = root.join("testroster.bin");
    if a.is_file() && b.is_file() {
        Some((a, b))
    } else {
        None
    }
}

fn read_be32(data: &[u8], off: usize) -> u32 {
    u32::from_be_bytes(data[off..off + 4].try_into().unwrap())
}

fn try_hash(label: &str, data: &[u8], expected: u32, hits: &mut Vec<String>) {
    let ea = EaChecksum::hash(data);
    if ea == expected {
        hits.push(format!("EaChecksum {label}"));
    }
    let crc = Crc32Be::new().hash(data);
    if crc == expected {
        hits.push(format!("Crc32Be {label}"));
    }
}

fn try_xor_combo(
    label: &str,
    a: u32,
    b: u32,
    expected: u32,
    hits: &mut Vec<String>,
) {
    for (name, v) in [
        ("xor", a ^ b),
        ("add", a.wrapping_add(b)),
        ("sub", a.wrapping_sub(b)),
    ] {
        if v == expected {
            hits.push(format!("{label}/{name}"));
        }
    }
}

#[test]
fn discover_rosterfile_checksum_candidates() {
    let paths = [
        concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../tests/fixtures/xbox/roster.bin"
        ),
        concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../_local/game-saves/xbox/roster1.bin"
        ),
        concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../_local/game-saves/xbox/testroster.bin"
        ),
    ];

    for path in paths {
        let Ok(data) = std::fs::read(path) else {
            eprintln!("skip missing {path}");
            continue;
        };

        for (slot, name) in [(0x10, "chk0x10"), (0x28, "chk0x28")] {
            let expected = read_be32(&data, slot);
            let mut hits = Vec::new();

            let mut zero_primary = data.clone();
            zero_primary[0x10..0x14].fill(0);
            let mut zero_secondary = data.clone();
            zero_secondary[0x28..0x2c].fill(0);
            let mut zero_both = data.clone();
            zero_both[0x10..0x14].fill(0);
            zero_both[0x28..0x2c].fill(0);

            try_hash("full", &data, expected, &mut hits);
            try_hash("payload@30", &data[0x30..], expected, &mut hits);
            try_hash("from14", &data[0x14..], expected, &mut hits);
            try_hash("hdr14_27", &data[0x14..0x28], expected, &mut hits);
            try_hash("hdr14_2f", &data[0x14..0x30], expected, &mut hits);
            try_hash("zero_primary", &zero_primary, expected, &mut hits);
            try_hash("zero_secondary", &zero_secondary, expected, &mut hits);
            try_hash("zero_both", &zero_both, expected, &mut hits);

            let mut magic_rest = Vec::new();
            magic_rest.extend_from_slice(&data[0..0x10]);
            magic_rest.extend_from_slice(&data[0x14..]);
            try_hash("magic+from14", &magic_rest, expected, &mut hits);

            let mut hdr_fields_payload = Vec::new();
            hdr_fields_payload.extend_from_slice(&data[0x14..0x30]);
            hdr_fields_payload.extend_from_slice(&data[0x30..]);
            try_hash("hdr14_30+payload", &hdr_fields_payload, expected, &mut hits);

            if let Ok(db) = roster_container::unpack(&data) {
                try_hash("uncompressed_db", &db, expected, &mut hits);
                try_hash("db_from14", &db[0x14..], expected, &mut hits);
            }

            let crc = Crc32Be::new();
            let ea = EaChecksum::hash(&data[0x30..]);
            let crc_payload = crc.hash(&data[0x30..]);
            try_xor_combo("payload_hashes", ea, crc_payload, expected, &mut hits);

            eprintln!("{path} {name}=0x{expected:08X} hits={hits:?}");
            assert!(
                hits.is_empty(),
                "unexpected easy match for {path} {name}: {hits:?}"
            );
        }
    }
}

#[test]
fn discover_checksum_pair_relationship() {
    let Some((a_path, b_path)) = fixture_paths() else {
        eprintln!("skip: McTavish pair not present");
        return;
    };

    let a = std::fs::read(&a_path).unwrap();
    let b = std::fs::read(&b_path).unwrap();

    eprintln!("roster1     @0x10=0x{:08X} @0x28=0x{:08X}", read_be32(&a, 0x10), read_be32(&a, 0x28));
    eprintln!("testroster  @0x10=0x{:08X} @0x28=0x{:08X}", read_be32(&b, 0x10), read_be32(&b, 0x28));

    let crc = Crc32Be::new();
    for (label, x) in [("roster1", &a), ("testroster", &b)] {
        eprintln!(
            "{label} Crc32Be payload=0x{:08X} db=0x{:08X}",
            crc.hash(&x[0x30..]),
            crc.hash(&roster_container::unpack(x).unwrap())
        );
    }

    assert_ne!(read_be32(&a, 0x10), read_be32(&b, 0x10));
    assert_ne!(read_be32(&a, 0x28), read_be32(&b, 0x28));
}

#[test]
fn header_field_0x2c_low_bits_stable_on_legacy_saves() {
    let Some((a_path, b_path)) = fixture_paths() else {
        return;
    };
    let a = std::fs::read(a_path).unwrap();
    let b = std::fs::read(b_path).unwrap();
    assert_eq!(read_be32(&a, 0x2c) & 0xFFFF, 0x0C00);
    assert_eq!(read_be32(&b, 0x2c) & 0xFFFF, 0x0C00);
}

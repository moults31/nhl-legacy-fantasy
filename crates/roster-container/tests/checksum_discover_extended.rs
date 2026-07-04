//! Extended brute-force discovery for RosterFile @0x10 / @0x28.
//!
//! Run: `cargo test -p roster-container discover_extended -- --nocapture`

use roster_container::EaChecksum;
use ea_tdb::Crc32Be;

fn read_be32(data: &[u8], off: usize) -> u32 {
    u32::from_be_bytes(data[off..off + 4].try_into().unwrap())
}

fn concat(parts: &[&[u8]]) -> Vec<u8> {
    parts.iter().copied().flatten().copied().collect()
}

fn with_zero(data: &[u8], start: usize, end: usize) -> Vec<u8> {
    let mut out = data.to_vec();
    out[start..end].fill(0);
    out
}

fn try_slices(
    label: &str,
    data: &[u8],
    chk10: u32,
    chk28: u32,
    hits: &mut Vec<String>,
) {
    let ea = EaChecksum::hash(data);
    if ea == chk10 {
        hits.push(format!("EaChecksum chk10 {label}"));
    }
    if ea == chk28 {
        hits.push(format!("EaChecksum chk28 {label}"));
    }

    let crc = Crc32Be::new();
    let c = crc.crc32_be(0, data, data.len() as u32, 0);
    let inv = !c;
    if c == chk10 {
        hits.push(format!("Crc32Be chk10 {label}"));
    }
    if c == chk28 {
        hits.push(format!("Crc32Be chk28 {label}"));
    }
    if inv == chk10 {
        hits.push(format!("!Crc32Be chk10 {label}"));
    }
    if inv == chk28 {
        hits.push(format!("!Crc32Be chk28 {label}"));
    }
}

#[test]
fn discover_extended_checksum_candidates() {
    let paths = [
        (
            "roster1",
            concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../_local/game-saves/xbox/roster1.bin"
            ),
        ),
        (
            "testroster",
            concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../_local/game-saves/xbox/testroster.bin"
            ),
        ),
        (
            "fixture",
            concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../tests/fixtures/xbox/roster.bin"
            ),
        ),
    ];

    for (name, path) in paths {
        let Ok(data) = std::fs::read(path) else {
            eprintln!("skip {name}");
            continue;
        };
        let chk10 = read_be32(&data, 0x10);
        let chk28 = read_be32(&data, 0x28);
        let comp = &data[0x30..];
        let db = roster_container::unpack(&data).expect("unpack");
        let mut hits = Vec::new();

        try_slices("full", &data, chk10, chk28, &mut hits);
        try_slices("comp", comp, chk10, chk28, &mut hits);
        try_slices("db", &db, chk10, chk28, &mut hits);
        try_slices("hdr14_2f", &data[0x14..0x30], chk10, chk28, &mut hits);
        try_slices("hdr14_27", &data[0x14..0x28], chk10, chk28, &mut hits);
        try_slices(
            "magic+14_2f",
            &concat(&[&data[0..0x10], &data[0x14..0x30]]),
            chk10,
            chk28,
            &mut hits,
        );
        try_slices(
            "hdr14_27+comp",
            &concat(&[&data[0x14..0x28], comp]),
            chk10,
            chk28,
            &mut hits,
        );
        try_slices(
            "hdr14_2f+comp",
            &concat(&[&data[0x14..0x30], comp]),
            chk10,
            chk28,
            &mut hits,
        );
        try_slices(
            "hdr24+comp",
            &concat(&[&data[0x24..0x30], comp]),
            chk10,
            chk28,
            &mut hits,
        );
        try_slices(
            "zero10",
            &with_zero(&data, 0x10, 0x14),
            chk10,
            chk28,
            &mut hits,
        );
        try_slices(
            "zero28",
            &with_zero(&data, 0x28, 0x2c),
            chk10,
            chk28,
            &mut hits,
        );
        try_slices(
            "zero_both",
            &with_zero(&with_zero(&data, 0x10, 0x14), 0x28, 0x2c),
            chk10,
            chk28,
            &mut hits,
        );
        try_slices(
            "hdr30_zero10",
            &concat(&[
                &data[0..0x10],
                &[0, 0, 0, 0],
                &data[0x14..0x30],
            ]),
            chk10,
            chk28,
            &mut hits,
        );
        try_slices(
            "hdr30_zero28",
            &concat(&[
                &data[0..0x28],
                &[0, 0, 0, 0],
                &data[0x2c..0x30],
            ]),
            chk10,
            chk28,
            &mut hits,
        );
        try_slices(
            "hdr30_zero_both",
            &concat(&[
                &data[0..0x10],
                &[0, 0, 0, 0],
                &data[0x14..0x28],
                &[0, 0, 0, 0],
                &data[0x2c..0x30],
            ]),
            chk10,
            chk28,
            &mut hits,
        );

        // Chained: hash header fields then payload with seed
        let crc = Crc32Be::new();
        for (label, hdr) in [
            ("14_27", &data[0x14..0x28]),
            ("14_2f", &data[0x14..0x30]),
            ("24_2f", &data[0x24..0x30]),
        ] {
            let seed = crc.crc32_be(0, hdr, hdr.len() as u32, 0);
            let v = crc.crc32_be(seed, comp, comp.len() as u32, 0);
            if v == chk10 {
                hits.push(format!("crc_chain chk10 hdr {label}"));
            }
            if v == chk28 {
                hits.push(format!("crc_chain chk28 hdr {label}"));
            }
            let v = !crc.crc32_be(!crc.crc32_be(0, hdr, hdr.len() as u32, 0), comp, comp.len() as u32, 0);
            if v == chk10 {
                hits.push(format!("!crc_chain chk10 hdr {label}"));
            }
            if v == chk28 {
                hits.push(format!("!crc_chain chk28 hdr {label}"));
            }
        }

        eprintln!("{name} chk10=0x{chk10:08X} chk28=0x{chk28:08X} hits={hits:?}");
    }
}

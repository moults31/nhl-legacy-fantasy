//! Inspect live save zlib/deflate layout (run with `--nocapture`).

use roster_container::{unpack, RosterHeader};

#[test]
fn analyze_live_save_deflate_layout() {
    let path = std::path::Path::new(
        r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\00000001\ROSTER 20260307213511\ROSTER 20260307213511",
    );
    if !path.is_file() {
        eprintln!("skip: live save not present");
        return;
    }

    let data = std::fs::read(path).expect("read");
    let header = RosterHeader::parse(&data).expect("header");
    let payload = &data[header.payload_offset..];
    let db = unpack(&data).expect("unpack");

    eprintln!("file_len={}", data.len());
    eprintln!("payload_len={}", payload.len());
    eprintln!("uncompressed_len={}", db.len());
    eprintln!("payload/uncompressed ratio={:.6}", payload.len() as f64 / db.len() as f64);
    eprintln!("zlib magic={:02x}{:02x}", payload[0], payload[1]);
    eprintln!("deflate head={:02x?}", &payload[2..18.min(payload.len())]);
    eprintln!(
        "header @0x2c=0x{:08x} @0x24={}",
        header.field_0x2c,
        header.uncompressed_size
    );

    // Count non-final / final stored-block signatures in raw deflate stream.
    let deflate = &payload[2..payload.len() - 4];
    let mut stored_blocks = 0usize;
    let mut pos = 0usize;
    while pos < deflate.len() {
        let b = deflate[pos];
        let bfinal = b & 1;
        let btype = (b >> 1) & 0b11;
        eprintln!("block@{pos}: raw=0x{b:02x} bfinal={bfinal} btype={btype}");
        if btype == 0 {
            stored_blocks += 1;
            let aligned = pos + 1;
            if aligned + 4 > deflate.len() {
                break;
            }
            let len = u16::from_le_bytes([deflate[aligned], deflate[aligned + 1]]) as usize;
            let nlen = u16::from_le_bytes([deflate[aligned + 2], deflate[aligned + 3]]) as usize;
            eprintln!("  stored len={len} nlen={nlen} (~len={})", !nlen & 0xFFFF);
            pos = aligned + 4 + len;
        } else {
            break;
        }
        if bfinal != 0 {
            break;
        }
    }
    eprintln!("stored_blocks_seen={stored_blocks}");

    // Compare flate2 levels vs game payload size.
    use flate2::write::ZlibEncoder;
    use flate2::Compression;
    use std::io::Write;
    let target_len = payload.len();
    for level in [0, 1, 2, 3, 4, 5, 6, 9] {
        let mut enc = ZlibEncoder::new(Vec::new(), Compression::new(level));
        enc.write_all(&db).unwrap();
        let out = enc.finish().unwrap();
        eprintln!(
            "flate2 level {level}: len={} delta={} head={:02x?}",
            out.len(),
            out.len() as i64 - target_len as i64,
            &out[..12.min(out.len())]
        );
    }
}

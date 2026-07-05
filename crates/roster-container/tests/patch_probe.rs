//! Test whether edited TDB bytes can be patched into the template zlib payload in-place.

use flate2::read::ZlibDecoder;
use std::io::Read;

#[test]
fn probe_in_place_zlib_patch() {
    let dir = std::path::Path::new(
        r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\00000001\ROSTER 20260307213511",
    );
    let container_path = dir.join("ROSTER 20260307213511");
    let edited_path = dir.join("default.db");
    let backup_path = dir.join("default.db.bak");
    if !container_path.is_file() || !edited_path.is_file() || !backup_path.is_file() {
        eprintln!("skip: live paths missing");
        return;
    }

    let container = std::fs::read(&container_path).expect("container");
    let edited = std::fs::read(&edited_path).expect("edited");
    let backup = std::fs::read(&backup_path).expect("backup");

    let mut diffs = Vec::new();
    for (i, (&a, &b)) in edited.iter().zip(backup.iter()).enumerate() {
        if a != b {
            diffs.push((i, b, a));
        }
    }
    eprintln!("diff count {}", diffs.len());
    for (i, (off, was, now)) in diffs.iter().take(10).enumerate() {
        eprintln!("  diff[{i}] off=0x{off:x} {was:02x}->{now:02x}");
    }

    let mut payload = container[48..].to_vec();
    let zlib_off = 2usize;
    for (off, _was, now) in &diffs {
        let co = zlib_off + *off;
        if co < payload.len() {
            payload[co] = *now;
        }
    }

    let mut dec = ZlibDecoder::new(payload.as_slice());
    let mut out = Vec::new();
    match dec.read_to_end(&mut out) {
        Ok(_) => {
            let mut literal_matches = 0usize;
            for (off, _was, now) in &diffs {
                if out.get(*off) == Some(now) {
                    literal_matches += 1;
                }
            }
            eprintln!(
                "naive same-offset patch: decompressed {} bytes, literal matches {}/{}",
                out.len(),
                literal_matches,
                diffs.len()
            );
            eprintln!("full match edited db: {}", out == edited);
        }
        Err(e) => eprintln!("naive patch decompress failed: {e}"),
    }
}

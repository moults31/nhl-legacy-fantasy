//! Probe fdeflate decompress + compress variants.

use fdeflate::{compress_to_vec, decompress_to_vec, StoredOnlyCompressor};
use roster_container::unpack;
use std::io::Cursor;

#[test]
fn probe_fdeflate_against_live_save() {
    let tpl = std::path::Path::new(
        r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\00000001\ROSTER 20260307213511\ROSTER 20260307213511",
    );
    if !tpl.is_file() {
        eprintln!("skip");
        return;
    }
    let data = std::fs::read(tpl).expect("read");
    let target = &data[48..];
    let db = unpack(&data).expect("unpack");

    let round = decompress_to_vec(target).expect("fdeflate decompress game payload");
    eprintln!("fdeflate decompress game payload: {} bytes, matches db {}", round.len(), round == db);

    let fixed = compress_to_vec(&db);
    eprintln!(
        "fdeflate compress_to_vec: len={} delta={} head={:02x?}",
        fixed.len(),
        fixed.len() as i64 - target.len() as i64,
        &fixed[..16.min(fixed.len())]
    );

    let mut buf = Vec::new();
    {
        let mut stored = StoredOnlyCompressor::new(Cursor::new(&mut buf)).expect("stored new");
        stored.write_data(&db).expect("stored write");
        stored.finish().expect("stored finish");
    }
    let stored_out = buf;
    eprintln!(
        "fdeflate StoredOnly: len={} delta={} head={:02x?} predicted={}",
        stored_out.len(),
        stored_out.len() as i64 - target.len() as i64,
        &stored_out[..16.min(stored_out.len())],
        StoredOnlyCompressor::<Cursor<Vec<u8>>>::compressed_size(db.len())
    );

    eprintln!(
        "game target: len={} head={:02x?}",
        target.len(),
        &target[..16.min(target.len())]
    );
}

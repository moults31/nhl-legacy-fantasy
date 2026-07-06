/// Generate all test rosters with proper in-game display names patched into header.
/// Run: cargo test -p roster-cli --test make_rosters -- --nocapture

use std::path::Path;
use ea_tdb::{TdbFile, reseal_checksums};
use roster_container::{unpack, pack};

#[test]
fn make_all() {
    make_zbac_vfeq();
    make_zbac_swap();
    make_combined();
}

fn write_header_name(data: &mut [u8], name: &str) {
    // Display name at offset 0x09, UCS-2/UTF-16LE, max 11 chars (22 bytes)
    // Set null terminator at 0x08 (the 'e' in 'RosterFile')
    data[0x08] = 0x00;
    // Clear name area (0x09..0x1F)
    for i in 0x09..0x20 { data[i] = 0x00; }
    // Write name in UCS-2 LE
    let mut off = 0x09;
    for ch in name.chars() {
        if off + 1 >= 0x20 { break; }
        let code = ch as u32;
        data[off] = (code & 0xFF) as u8;
        data[off + 1] = ((code >> 8) & 0xFF) as u8;
        off += 2;
    }
    data[off] = 0x00;
    data[off + 1] = 0x00;

    // Also set the folder/timestamp block at 0x108 for compatibility
    let folder = format!("ROSTER {}\0", name);
    let ascii = folder.as_bytes();
    let len = ascii.len().min(32);
    for i in 0..len {
        if 0x108 + i < data.len() {
            data[0x108 + i] = ascii[i];
        }
    }
}

fn save_roster(mut db: Vec<u8>, template: &[u8], name: &str) {
    reseal_checksums(&mut db).expect("reseal");
    let mut packed = pack(&db, template).expect("pack");
    write_header_name(&mut packed, name);

    let out = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("_local/game-saves/checkpoint")
        .join(format!("{}.bin", name));
    std::fs::write(&out, &packed).expect("write");
    eprintln!("Wrote {} ({} bytes)", out.display(), packed.len());
}

fn load_db() -> (Vec<u8>, Vec<u8>, TdbFile) {
    let unch_path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("_local/game-saves/xbox/m5-staging/UNCHANGED.bin");
    let container = std::fs::read(&unch_path).expect("read unch");
    let db = unpack(&container).expect("unpack");
    let file = TdbFile::parse(&db).expect("parse");
    (db, container, file)
}

fn make_zbac_vfeq() {
    let (mut db, container, file) = load_db();
    let endian = file.header.endian;

    // ZBac (T17): change r0 vfEq 7→0
    let entry = &file.directory.entries[17];
    let layout = file.table_layout(&db, entry).expect("zbac");
    let vfeq_f = layout.fields.iter().find(|f| f.field_id.as_str() == "qEfv").unwrap();
    let old = layout.read_field(&db, 0, vfeq_f, endian).unwrap();
    layout.write_field(&mut db, 0, vfeq_f, 0, endian).expect("write");
    eprintln!("ZBAC_VFEQ: r0 vfEq {}→0", old);

    save_roster(db, &container, "ZBAC_VFEQ");
}

fn make_zbac_swap() {
    let (mut db, container, file) = load_db();
    let endian = file.header.endian;

    let entry = &file.directory.entries[17];
    let layout = file.table_layout(&db, entry).expect("zbac");
    let vfeq_f = layout.fields.iter().find(|f| f.field_id.as_str() == "qEfv").unwrap();
    let v0 = layout.read_field(&db, 0, vfeq_f, endian).unwrap();
    let v1 = layout.read_field(&db, 1, vfeq_f, endian).unwrap();
    layout.write_field(&mut db, 0, vfeq_f, v1, endian).unwrap();
    layout.write_field(&mut db, 1, vfeq_f, v0, endian).unwrap();
    eprintln!("ZBAC_SWAP: r0↔r1 vfEq ({}↔{})", v0, v1);

    save_roster(db, &container, "ZBAC_SWAP");
}

fn make_combined() {
    let (mut db, container, file) = load_db();
    let endian = file.header.endian;

    // T25 r0: BSXd 110→0
    {
        let layout = file.table_layout(&db, &file.directory.entries[25]).expect("T25");
        let f = layout.fields.iter().find(|f| f.field_id.as_str() == "BSXd").unwrap();
        layout.write_field(&mut db, 0, f, 0, endian).unwrap();
        eprintln!("COMBINED: T25 r0 BSXd→0");
    }
    // T26 r2: BSXd 1→0  
    {
        let layout = file.table_layout(&db, &file.directory.entries[26]).expect("T26");
        let f = layout.fields.iter().find(|f| f.field_id.as_str() == "BSXd").unwrap();
        layout.write_field(&mut db, 2, f, 0, endian).unwrap();
        eprintln!("COMBINED: T26 r2 BSXd→0");
    }
    // T33 r0-r4: BSXd 223→0
    {
        let layout = file.table_layout(&db, &file.directory.entries[33]).expect("T33");
        let f = layout.fields.iter().find(|f| f.field_id.as_str() == "BSXd").unwrap();
        for r in 0..5 { layout.write_field(&mut db, r, f, 0, endian).unwrap(); }
        eprintln!("COMBINED: T33 r0-r4 BSXd→0");
    }
    // T38 r0: BSXd 1→0
    {
        let layout = file.table_layout(&db, &file.directory.entries[38]).expect("T38");
        let f = layout.fields.iter().find(|f| f.field_id.as_str() == "BSXd").unwrap();
        layout.write_field(&mut db, 0, f, 0, endian).unwrap();
        eprintln!("COMBINED: T38 r0 BSXd→0");
    }

    save_roster(db, &container, "COMBINED");
}

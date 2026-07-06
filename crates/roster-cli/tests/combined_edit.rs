/// Combined edit across T25, T26, T33 (safe tables). Change BSXd for
/// a specific record in each to Anaheim (team 0) and generate ONE roster.
/// Run: cargo test -p roster-cli --test combined_edit -- --nocapture

use std::collections::BTreeMap;
use std::path::Path;
use ea_tdb::{TdbFile, reseal_checksums};
use roster_container::{unpack, pack};

#[test]
fn combined_safe_edit() {
    let unch_path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("_local/game-saves/xbox/m5-staging/UNCHANGED.bin");
    let container = std::fs::read(&unch_path).expect("read unch");
    let mut db = unpack(&container).expect("unpack");
    let file = TdbFile::parse(&db).expect("parse");
    let endian = file.header.endian;

    // ---- Dump field layouts for each target ----
    let targets: [(usize, &str); 3] = [(25, "T25"), (26, "T26"), (33, "T33")];

    for &(idx, label) in &targets {
        let entry = &file.directory.entries[idx];
        let layout = file.table_layout(&db, entry).expect(label);
        eprintln!("=== {} ({}) fields ===", label, entry.table_id.as_str());
        for f in &layout.fields {
            let fn_r: String = f.field_id.as_str().chars().rev().collect();
            eprintln!("  {:4} ({:4}) width={}bit off={}bit", 
                f.field_id.as_str(), fn_r, f.bit_width, f.record_bit_offset);
        }
        eprintln!();
    }

    // ---- Read all field values for first 5 records in each table ----
    for &(idx, label) in &targets {
        let entry = &file.directory.entries[idx];
        let layout = file.table_layout(&db, entry).expect(label);
        eprintln!("=== {} first 5 records ===", label);
        for rec in 0..layout.info.current_records.min(5) {
            let r = rec as usize;
            let vals: Vec<String> = layout.fields.iter()
                .map(|f| {
                    let v = layout.read_field(&db, r, f, endian).unwrap_or(999);
                    format!("{}={}", f.field_id.as_str(), v)
                })
                .collect();
            eprintln!("  r{}: {}", rec, vals.join(", "));
        }
    }

    // ---- Now edit: change BSXd to 0 (Anaheim) for specific records ----
    eprintln!("\n=== Applying edits ===");

    // T25 r0: BSXd 110→0 (pick a visible-looking record)
    {
        let entry = &file.directory.entries[25];
        let layout = file.table_layout(&db, entry).expect("T25 layout");
        let bsxd_f = layout.fields.iter().find(|f| f.field_id.as_str() == "BSXd").unwrap();
        let old = layout.read_field(&db, 0, bsxd_f, endian).unwrap();
        layout.write_field(&mut db, 0, bsxd_f, 0, endian).expect("write T25");
        eprintln!("T25 r0: BSXd {}→0", old);
    }

    // T26 r2: BSXd 1→0
    {
        let entry = &file.directory.entries[26];
        let layout = file.table_layout(&db, entry).expect("T26 layout");
        let bsxd_f = layout.fields.iter().find(|f| f.field_id.as_str() == "BSXd").unwrap();
        let old = layout.read_field(&db, 2, bsxd_f, endian).unwrap();
        layout.write_field(&mut db, 2, bsxd_f, 0, endian).expect("write T26");
        eprintln!("T26 r2: BSXd {}→0", old);
    }

    // T33 r0-r5: BSXd 223→0 (change multiple records)
    {
        let entry = &file.directory.entries[33];
        let layout = file.table_layout(&db, entry).expect("T33 layout");
        let bsxd_f = layout.fields.iter().find(|f| f.field_id.as_str() == "BSXd").unwrap();
        for r in 0..5usize {
            let old = layout.read_field(&db, r, bsxd_f, endian).unwrap();
            layout.write_field(&mut db, r, bsxd_f, 0, endian).expect("write T33");
            eprintln!("T33 r{}: BSXd {}→0", r, old);
        }
    }

    // T38 r0: BSXd 1→0
    {
        let entry = &file.directory.entries[38];
        let layout = file.table_layout(&db, entry).expect("T38 layout");
        let bsxd_f = layout.fields.iter().find(|f| f.field_id.as_str() == "BSXd").unwrap();
        let old = layout.read_field(&db, 0, bsxd_f, endian).unwrap();
        layout.write_field(&mut db, 0, bsxd_f, 0, endian).expect("write T38");
        eprintln!("T38 r0: BSXd {}→0", old);
    }

    // Reseal and pack
    reseal_checksums(&mut db).expect("reseal");
    let packed = pack(&db, &container).expect("pack");

    let out = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("_local/game-saves/checkpoint/combined_t2533.bin");
    std::fs::write(&out, &packed).expect("write");
    eprintln!("\nWrote {} ({} bytes)", out.display(), packed.len());
}

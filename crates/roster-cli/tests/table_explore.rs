/// Edit ZBac.vfEq (team reference) — NOT ykFq (player index).
/// ZBac is fully in safe blocks 13-14.
#[test]
fn edit_zbac_vfeq() {
    use std::path::Path;
    use ea_tdb::TdbFile;

    let unch_path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("_local/game-saves/xbox/m5-staging/UNCHANGED.bin");
    let container = std::fs::read(&unch_path).expect("read unch");
    let mut db = roster_container::unpack(&container).expect("unpack");
    let file = ea_tdb::TdbFile::parse(&db).expect("parse");
    let endian = file.header.endian;

    // ZBac = T17
    let zbac_entry = &file.directory.entries[17];
    let zbac_layout = file.table_layout(&db, zbac_entry).expect("zbac");
    let vfeq_f = zbac_layout.fields.iter().find(|f| f.field_id.as_str() == "qEfv").unwrap();
    let ykfq_f = zbac_layout.fields.iter().find(|f| f.field_id.as_str() == "qFky").unwrap();

    eprintln!("=== First 30 ZBac records ===");
    for rec in 0..30usize {
        let v = zbac_layout.read_field(&db, rec, vfeq_f, endian).unwrap_or(999);
        let y = zbac_layout.read_field(&db, rec, ykfq_f, endian).unwrap_or(999);
        eprintln!("  r{:4}: vfEq={:3} ykFq={:4}", rec, v, y);
    }

    // Edit: change ZBac r0 vfEq from 7→0 (move player to team 0 / Anaheim)
    let old_v = zbac_layout.read_field(&db, 0, vfeq_f, endian).unwrap();
    eprintln!("\nChanging ZBac r0 vfEq: {} → 0", old_v);
    zbac_layout.write_field(&mut db, 0, vfeq_f, 0, endian).expect("write");

    ea_tdb::reseal_checksums(&mut db).expect("reseal");

    // Pack into full container
    let packed = roster_container::pack(&db, &container).expect("pack");

    let out = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("_local/game-saves/checkpoint/zbac_vfeq.bin");
    std::fs::write(&out, &packed).expect("write");
    eprintln!("Wrote {} ({} bytes)", out.display(), packed.len());

    // Also try: change vfEq for multiple records
    eprintln!("\n=== Multi-edit: swap ZBac r0 and r1 vfEq ===");
    let mut db2 = db.clone();
    let v0 = zbac_layout.read_field(&db2, 0, vfeq_f, endian).unwrap();
    let v1 = zbac_layout.read_field(&db2, 1, vfeq_f, endian).unwrap();
    zbac_layout.write_field(&mut db2, 0, vfeq_f, v1, endian).unwrap();
    zbac_layout.write_field(&mut db2, 1, vfeq_f, v0, endian).unwrap();
    eprintln!("Swapped: r0 vfEq {}↔{}, r1 vfEq {}↔{}", v0, v1, v1, v0);

    ea_tdb::reseal_checksums(&mut db2).expect("reseal");
    let packed2 = roster_container::pack(&db2, &container).expect("pack");

    let out2 = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("_local/game-saves/checkpoint/zbac_vfeq_swap.bin");
    std::fs::write(&out2, &packed2).expect("write");
    eprintln!("Wrote {} ({} bytes)", out2.display(), packed2.len());
}

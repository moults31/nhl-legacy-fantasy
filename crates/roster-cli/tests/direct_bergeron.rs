/// Deep-dive into specific tables: T26 (LScw), T32 (Roup/puoR), T33 (NDEo), T34 (cTuP/PuTc).
/// Check ALL fields, all records, to understand what they contain.
#[test]
fn deep_dive_tables() {
    let unch_path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("_local/game-saves/xbox/m5-staging/UNCHANGED.bin");
    let container = std::fs::read(&unch_path).expect("read unch");
    let db = unpack(&container).expect("unpack");
    let file = TdbFile::parse(&db).expect("parse");

    let tables_to_check = [17, 23, 25, 26, 32, 33, 34, 38];

    for &idx in &tables_to_check {
        let entry = &file.directory.entries[idx];
        if entry.data_offset == 0 { continue; }
        let layout = file.table_layout(&db, entry).expect("layout");

        let name = entry.table_id.as_str();
        let name_rev: String = name.chars().rev().collect();
        eprintln!(
            "\n=== T{:2}: {:4} ({}) | {}r × {}B ===",
            idx, name, name_rev,
            layout.info.current_records, layout.info.record_length_bytes,
        );

        // Show ALL fields
        eprintln!("Fields:");
        for f in &layout.fields {
            let fn_s = f.field_id.as_str();
            let fn_rev: String = fn_s.chars().rev().collect();
            eprintln!(
                "  {:4} ({}) width={:3}bit off={:4}bit kind={:#x}",
                fn_s, fn_rev, f.bit_width, f.record_bit_offset, f.kind_code,
            );
        }

        // Dump first 10 records as hex
        eprint!("Samples:");
        let data_off = layout.info_offset + 40 + layout.info.num_fields as usize * 16;
        let n = layout.info.current_records.min(10);
        for rec in 0..n {
            let off = data_off + rec as usize * layout.info.record_length_bytes as usize;
            let bytes = &db[off..off + layout.info.record_length_bytes as usize];
            eprint!(" r{}[", rec);
            // Show as decimal values per field
            let mut f_strs = Vec::new();
            for f in &layout.fields {
                let val = layout.read_field(&db, rec, f, file.header.endian).unwrap_or(999);
                f_strs.push(format!("{}={}", f.field_id.as_str(), val));
            }
            eprint!("{}", f_strs.join(", "));
            eprintln!("]");
        }
    }
}

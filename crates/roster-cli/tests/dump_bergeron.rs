/// Dump cPbu layout and Bergeron's full record from TRADEEDIT5.
#[test]
fn dump_bergeron_record() {
    use std::path::Path;
    use ea_tdb::TdbFile;

    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../_local/game-saves/xbox");
    let source = root.join("TRADEEDIT5");
    if !source.is_file() {
        eprintln!("SKIP: TRADEEDIT5 not found");
        return;
    }

    let container = std::fs::read(&source).expect("read TRADEEDIT5");
    let db = roster_container::unpack(&container).expect("unpack");

    let file = TdbFile::parse(&db).expect("parse");
    let entry = file.directory.get("cPbu").expect("cPbu");
    let layout = file.table_layout(&db, entry).expect("layout");

    println!("cPbu: {} records, {} bytes/record, {} fields",
        layout.info.current_records, layout.info.record_length_bytes,
        layout.fields.len());
    println!("cPbu fields:");
    for f in &layout.fields {
        let id = std::str::from_utf8(&f.field_id.0).unwrap_or("???");
        println!("  {:4}  kind={:02X}  bit_width={:3}  rec_bit_off={:5}",
            id, f.kind_code, f.bit_width, f.record_bit_offset);
    }

    let last_name_field = layout.find_field("RMbQ").expect("RMbQ");
    let first_name_field = layout.find_field("PedH").expect("PedH");

    for rec in 0..layout.info.current_records as usize {
        let last = roster_semantic::read_string_field(
            &layout, &db, rec, last_name_field
        ).expect("read last name");
        if last != "Bergeron" {
            continue;
        }
        let first = roster_semantic::read_string_field(
            &layout, &db, rec, first_name_field
        ).expect("read first name");
        if first != "Patrice" {
            continue;
        }

        println!("\n=== Patrice Bergeron (record {}) ===", rec);
        for f in &layout.fields {
            let id = std::str::from_utf8(&f.field_id.0).unwrap_or("???");
            let val = layout.read_field(&db, rec, f, file.header.endian);
            match val {
                Ok(v) => println!("  {:4} = {} (0x{:X})", id, v, v),
                Err(_) => println!("  {:4} = READ_ERROR", id),
            }
        }
        return;
    }
    println!("Bergeron NOT FOUND in cPbu by name match");
}

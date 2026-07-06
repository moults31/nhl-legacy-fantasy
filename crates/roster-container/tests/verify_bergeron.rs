/// No-edit round-trip through compress_zlib_from_template:
/// re-compress unchanged DB and compare deflate byte-for-byte with template.
/// If any diffs exist, deflate_template is altering the stream structure
/// in ways the game's inflater might not tolerate.
#[test]
fn no_edit_compress_preserves_deflate() {
    use roster_container::deflate_template::compress_zlib_from_template;
    use roster_container::unpack;

    let fixture_path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../tests/fixtures/xbox/roster.bin");
    if !fixture_path.is_file() {
        eprintln!("SKIP: fixture not found (make fixture available)");
        return;
    }

    let container = std::fs::read(&fixture_path).expect("read");
    let db = unpack(&container).expect("unpack");
    let tpl_zlib = &container[0x30..];

    let recompressed = compress_zlib_from_template(&db, tpl_zlib).expect("recompress");

    assert_eq!(recompressed.len(), tpl_zlib.len(), "zlib size must match (same padding rules)");

    let mut diffs = 0usize;
    let mut first_byte = None;
    let mut first_bit = None;
    for i in 0..tpl_zlib.len() {
        if tpl_zlib[i] != recompressed[i] {
            if first_byte.is_none() {
                first_byte = Some(i);
                // Find the first differing bit
                let byte_diff = tpl_zlib[i] ^ recompressed[i];
                let bit = byte_diff.trailing_zeros() as usize;
                first_bit = Some(i * 8 + bit);
            }
            diffs += 1;
        }
    }

    if diffs == 0 {
        eprintln!("PASS: no-edit recompress is bit-identical to template");
    } else {
        eprintln!("FAIL: {} byte diffs, first at byte {} (bit {})",
            diffs, first_byte.unwrap(), first_bit.unwrap());
        // Show first few diffs
        let mut shown = 0;
        for i in 0..tpl_zlib.len() {
            if tpl_zlib[i] != recompressed[i] {
                eprintln!("  byte {:08X}: tpl={:02X} rec={:02X} xor={:02X}",
                    i, tpl_zlib[i], recompressed[i], tpl_zlib[i] ^ recompressed[i]);
                shown += 1;
                if shown >= 20 { break; }
            }
        }
        panic!("no-edit recompress altered deflate stream");
    }

    // Also verify: round-trip decompress with fdeflate
    use roster_container::deflate_fdeflate_ops::Decompressor;
    let mut out = vec![0u8; 3_000_000];
    let (_, produced) = Decompressor::new()
        .read(&recompressed, &mut out, 0, true)
        .expect("fdeflate decode");
    assert_eq!(&out[..produced], db, "round-trip TDB mismatch");
}

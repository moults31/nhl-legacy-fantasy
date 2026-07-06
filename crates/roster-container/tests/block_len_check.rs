/// Check: when blocks are re-encoded, does their bit-length match the template?
/// If not, subsequent copy_from_template blocks are shifted (corrupted).
use roster_container::deflate_template;

const T5: &str = "../../_local/game-saves/xbox/TRADEEDIT5";
const MS_DB: &str = "../../_local/game-saves/xbox/hedman_col.db";

#[test]
fn block_bit_length_consistency() {
    let t5 = std::fs::read(T5).expect("T5");
    let t5_zlib = &t5[48..];
    let ms = std::fs::read(MS_DB).expect("MS");
    let template_deflate = &t5_zlib[2..t5_zlib.len() - 4];

    // Get template block boundaries
    let tmpl_blocks = roster_container::deflate_template::inspect_deflate_blocks(t5_zlib)
        .expect("inspect template");

    for (label, db) in &[
        ("T0", ms.clone()),
        ("T1", { let mut d = ms.clone(); d[0x0B949B] = 0x40; d }),
        ("T2", { let mut d = ms.clone(); d[0x0B949B] = 0x40; d[0x0B9837] = 0x40; d }),
    ] {
        let zlib = deflate_template::compress_zlib_from_template(db, t5_zlib).expect(label);
        let test_blocks = roster_container::deflate_template::inspect_deflate_blocks(&zlib)
            .expect("inspect test");

        println!("\n=== {label} ===");
        for (i, (tmpl, test)) in tmpl_blocks.iter().zip(test_blocks.iter()).enumerate() {
            let tmpl_len = tmpl.end_bit - tmpl.start_bit;
            let test_len = test.end_bit - test.start_bit;
            let match_len = tmpl_len == test_len;
            let prefix = if match_len { "  OK" } else { "*** MISMATCH" };
            println!(
                "{prefix} block[{i:2}]: tmpl_len={tmpl_len} test_len={test_len} diff={} copy=? tdb=[0x{:06X}..0x{:06X})",
                test_len as i64 - tmpl_len as i64,
                test.tdb_start, test.tdb_end,
            );
        }
    }
}

/// Diagnose: T0_CLEAN works in-game, T1_CRSB fails.
/// Both re-encode blocks [6, 12, 13]. Compare block 6 zlib output.
use roster_container::deflate_template;

const T5: &str = "../../_local/game-saves/xbox/TRADEEDIT5";
const MS_DB: &str = "../../_local/game-saves/xbox/hedman_col.db";

#[test]
fn t0_vs_t1_block6_diff() {
    let t5 = std::fs::read(T5).expect("T5");
    let t5_zlib = &t5[48..];
    let mut ms = std::fs::read(MS_DB).expect("MS");

    // T0: no edit
    let z0 = deflate_template::compress_zlib_from_template(&ms, t5_zlib).expect("T0");

    // T1: Crosby edit
    ms[0x0B949B] = 0x40;
    let z1 = deflate_template::compress_zlib_from_template(&ms, t5_zlib).expect("T1");

    let deflate0 = &z0[2..z0.len() - 4];
    let deflate1 = &z1[2..z1.len() - 4];
    assert_eq!(deflate0.len(), deflate1.len(), "deflate length differs");

    let diffs: Vec<(usize, u8, u8)> = deflate0.iter().zip(deflate1.iter()).enumerate()
        .filter(|(_, (a, b))| a != b)
        .map(|(i, (a, b))| (i, *a, *b))
        .collect();

    println!("deflate diffs: {}", diffs.len());
    for (off, a, b) in diffs.iter().take(30) {
        println!("  deflate byte {off}: T0=0x{a:02X} T1=0x{b:02X}");
    }

    // Find which block each diff belongs to
    let blocks = deflate_template::inspect_deflate_blocks(t5_zlib).expect("inspect");
    for (off, a, b) in diffs.iter().take(10) {
        let bit = *off * 8;
        if let Some(meta) = blocks.iter().find(|m| bit >= m.start_bit && bit < m.end_bit) {
            let bi = blocks.iter().position(|m| m.start_bit == meta.start_bit).unwrap();
            println!(
                "  diff at byte {off} (bit {bit}): block[{bi}] covers DB [0x{:06X}..0x{:06X})",
                meta.tdb_start, meta.tdb_end
            );
        }
    }
}

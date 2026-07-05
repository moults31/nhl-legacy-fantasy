//! Parse-only probe for template deflate trees.

use roster_container::unpack;

#[test]
fn probe_template_tree_header() {
    let path = std::path::Path::new(
        r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\00000001\ROSTER 20260307213511\ROSTER 20260307213511",
    );
    if !path.is_file() {
        eprintln!("skip");
        return;
    }
    let container = std::fs::read(path).expect("read");
    let zlib = &container[48..];
    let db = unpack(zlib).expect("unpack");
    eprintln!("db len={}", db.len());

    let deflate = &zlib[2..zlib.len() - 4];
    let mut p = 0usize;
    let mut rb = |n: u32| -> u32 {
        let mut v = 0u32;
        for i in 0..n {
            v |= u32::from((deflate[p / 8] >> (p % 8)) & 1) << i;
            p += 1;
        }
        v
    };
    let bfinal = rb(1);
    let btype = rb(2);
    let hlit = rb(5) as usize + 257;
    let hdist = rb(5) as usize + 1;
    let hclen = rb(4) as usize + 4;
    eprintln!("bfinal={bfinal} btype={btype} hlit={hlit} hdist={hdist} hclen={hclen} pos={p}");
}

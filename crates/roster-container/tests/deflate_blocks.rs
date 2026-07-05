//! Full deflate block walk on live roster save.

#[test]
fn walk_all_deflate_blocks() {
    let path = std::path::Path::new(
        r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\00000001\ROSTER 20260307213511\ROSTER 20260307213511",
    );
    if !path.is_file() {
        eprintln!("skip");
        return;
    }
    let data = std::fs::read(path).expect("read");
    let payload = &data[48..];
    let deflate = &payload[2..payload.len() - 4];

    let mut pos = 0usize;
    let mut block = 0usize;
    while pos < deflate.len() {
        if pos + 1 >= deflate.len() {
            eprintln!("block {block}: truncated at {pos}");
            break;
        }
        let b = deflate[pos];
        let bfinal = b & 1;
        let btype = (b >> 1) & 0b11;
        eprintln!("block {block}@{pos}: bfinal={bfinal} btype={btype} raw=0x{b:02x}");
        pos += 1;
        match btype {
            0 => {
                // align to byte boundary - after 3-bit header we're already byte aligned if pos started on byte boundary after reading 1 byte from previous... 
                // Actually after reading block header byte, we're byte aligned.
                if pos + 4 > deflate.len() {
                    break;
                }
                let len = u16::from_le_bytes([deflate[pos], deflate[pos + 1]]) as usize;
                let nlen = u16::from_le_bytes([deflate[pos + 2], deflate[pos + 3]]) as usize;
                eprintln!("  stored len={len} nlen={nlen:x}");
                pos += 4 + len;
            }
            1 | 2 => {
                eprintln!("  compressed block (fixed/dynamic) - stop parse");
                break;
            }
            _ => break,
        }
        block += 1;
        if bfinal != 0 {
            eprintln!("final block at {pos}");
            break;
        }
    }
    eprintln!("total deflate bytes={}, parsed to {}", deflate.len(), pos);
}

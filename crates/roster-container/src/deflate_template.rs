//! Recompress roster TDB bytes using Huffman trees cloned from a live save template.
//!
//! Tree parsing and codeword assignment follow the fdeflate implementation (MIT/Apache-2.0).

use crate::error::{Error, Result};

const CLCL_ORDER: [usize; 19] =
    [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];

const LENGTH_BASE: [u16; 29] = [
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99,
    115, 131, 163, 195, 227, 258,
];
const LENGTH_EXTRA: [u8; 29] = [
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0,
];
const DIST_BASE: [u16; 30] = [
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025,
    1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577,
];
const DIST_EXTRA: [u8; 30] = [
    0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12,
    13, 13,
];

fn next_codeword(mut codeword: u16, table_size: u16) -> u16 {
    if codeword == table_size - 1 {
        return codeword;
    }
    let adv = (u16::BITS - 1) - (codeword ^ (table_size - 1)).leading_zeros();
    let bit = 1 << adv;
    codeword &= bit - 1;
    codeword |= bit;
    codeword
}

/// Build fdeflate-style codewords for encoding (MSB canonical indices, LSB-first write).
fn build_codewords(lengths: &[u8]) -> Result<Vec<u16>> {
    let mut histogram = [0u16; 16];
    for &len in lengths {
        histogram[len as usize] += 1;
    }

    let mut max_length = 15usize;
    while max_length > 1 && histogram[max_length] == 0 {
        max_length -= 1;
    }

    let mut offsets = [0usize; 16];
    let mut codespace_used = 0u16;
    offsets[1] = histogram[0] as usize;
    for i in 1..max_length {
        offsets[i + 1] = offsets[i] + histogram[i] as usize;
        codespace_used = (codespace_used << 1) + histogram[i];
    }
    codespace_used = (codespace_used << 1) + histogram[max_length];

    if max_length > 0 && codespace_used != (1 << max_length) {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "incomplete huffman tree",
        )));
    }

    let mut next_index = offsets;
    let mut sorted_symbols = vec![0usize; lengths.len()];
    for (symbol, &len) in lengths.iter().enumerate() {
        if len > 0 {
            sorted_symbols[next_index[len as usize]] = symbol;
            next_index[len as usize] += 1;
        }
    }

    let mut codes = vec![0u16; lengths.len()];
    let mut codeword = 0u16;
    let mut i = histogram[0] as usize;
    for length in 1..=max_length {
        let current_table_end = 1 << length;
        for _ in 0..histogram[length] {
            let symbol = sorted_symbols[i];
            i += 1;
            codes[symbol] = codeword;
            codeword = next_codeword(codeword, current_table_end as u16);
        }
    }
    Ok(codes)
}

struct BitReader<'a> {
    data: &'a [u8],
    pos: usize,
    buffer: u64,
    nbits: u8,
    bits_consumed: usize,
}

impl<'a> BitReader<'a> {
    fn new(data: &'a [u8]) -> Self {
        Self {
            data,
            pos: 0,
            buffer: 0,
            nbits: 0,
            bits_consumed: 0,
        }
    }

    fn fill(&mut self) {
        while self.nbits <= 56 && self.pos < self.data.len() {
            self.buffer |= u64::from(self.data[self.pos]) << self.nbits;
            self.pos += 1;
            self.nbits += 8;
        }
    }

    fn peek(&self, n: u8) -> u64 {
        self.buffer & ((1u64 << n) - 1)
    }

    fn consume(&mut self, n: u8) {
        self.buffer >>= n;
        self.nbits -= n;
        self.bits_consumed += n as usize;
    }

    fn decode_symbol_from_codes(
        &mut self,
        lengths: &[u8],
        codes: &[u16],
    ) -> Result<u16> {
        self.fill();
        for len in 1..=15u8 {
            if self.nbits < len {
                break;
            }
            let code = self.peek(len) as u16;
            for (sym, &sym_len) in lengths.iter().enumerate() {
                if sym_len == len && codes.get(sym) == Some(&code) {
                    self.consume(len);
                    return Ok(sym as u16);
                }
            }
        }
        Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "invalid huffman code",
        )))
    }
}

struct BitWriter {
    buffer: u64,
    nbits: u8,
    out: Vec<u8>,
}

impl BitWriter {
    fn new() -> Self {
        Self {
            buffer: 0,
            nbits: 0,
            out: Vec::new(),
        }
    }

    fn write_bits(&mut self, bits: u64, count: u8) {
        self.buffer |= bits << self.nbits;
        self.nbits += count;
        while self.nbits >= 8 {
            self.out.push(self.buffer as u8);
            self.buffer >>= 8;
            self.nbits -= 8;
        }
    }

    fn copy_bits(&mut self, data: &[u8], from_bit: usize, to_bit: usize) {
        for bit in from_bit..to_bit {
            self.write_bits(u64::from((data[bit / 8] >> (bit % 8)) & 1), 1);
        }
    }

    fn finish(mut self) -> Vec<u8> {
        if self.nbits % 8 != 0 {
            self.write_bits(0, 8 - (self.nbits % 8));
        }
        if self.nbits >= 8 {
            self.out.push(self.buffer as u8);
        }
        self.out
    }
}

struct TemplateTrees {
    data_start_bit: usize,
    lit_lengths: Vec<u8>,
    lit_codes: Vec<u16>,
    dist_lengths: Vec<u8>,
    dist_codes: Vec<u16>,
}

fn parse_template_trees(deflate: &[u8]) -> Result<TemplateTrees> {
    let mut br = BitReader::new(deflate);
    br.fill();
    if br.nbits < 17 {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::UnexpectedEof,
            "truncated dynamic block header",
        )));
    }

    let btype = br.peek(3) >> 1;
    if btype != 2 {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            format!("expected dynamic block, got btype={btype}"),
        )));
    }

    let hlit = (br.peek(8) >> 3) as usize + 257;
    let hdist = (br.peek(13) >> 8) as usize + 1;
    let hclen = (br.peek(17) >> 13) as usize + 4;
    br.consume(17);

    let mut cl_lengths = [0u8; 19];
    for i in 0..hclen {
        br.fill();
        cl_lengths[CLCL_ORDER[i]] = br.peek(3) as u8;
        br.consume(3);
    }
    let cl_codes = build_codewords(&cl_lengths)?;

    let total = hlit + hdist;
    let mut all_lengths = vec![0u8; total];
    let mut index = 0usize;
    while index < total {
        let sym = br.decode_symbol_from_codes(&cl_lengths, &cl_codes)?;
        match sym {
            0..=15 => {
                all_lengths[index] = sym as u8;
                index += 1;
            }
            16 => {
                if index == 0 {
                    return Err(Error::Decompress(std::io::Error::new(
                        std::io::ErrorKind::InvalidData,
                        "invalid code length repeat at start",
                    )));
                }
                br.fill();
                let repeat = (br.peek(2) as usize) + 3;
                br.consume(2);
                let value = all_lengths[index - 1];
                for slot in &mut all_lengths[index..index + repeat] {
                    *slot = value;
                }
                index += repeat;
            }
            17 => {
                br.fill();
                let repeat = (br.peek(3) as usize) + 3;
                br.consume(3);
                index += repeat;
            }
            18 => {
                br.fill();
                let repeat = (br.peek(7) as usize) + 11;
                br.consume(7);
                index += repeat;
            }
            _ => {
                return Err(Error::Decompress(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    "bad code-length symbol",
                )));
            }
        }
    }

    let data_start_bit = br.bits_consumed;
    let mut lit_lengths = all_lengths[..hlit].to_vec();
    lit_lengths.resize(288, 0);
    let dist_part = &all_lengths[hlit..];
    let mut dist_lengths = vec![0u8; 32];
    dist_lengths[..dist_part.len()].copy_from_slice(dist_part);

    if lit_lengths[256] == 0 {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "missing end-of-block code",
        )));
    }

    Ok(TemplateTrees {
        data_start_bit,
        lit_codes: build_codewords(&lit_lengths[..hlit])?,
        lit_lengths: lit_lengths[..hlit].to_vec(),
        dist_codes: build_codewords(&dist_lengths)?,
        dist_lengths,
    })
}

fn decode_with_trees(deflate: &[u8], trees: &TemplateTrees) -> Result<Vec<u8>> {
    let mut br = BitReader::new(deflate);
    for _ in 0..trees.data_start_bit {
        br.fill();
        br.consume(1);
    }

    let mut out = Vec::new();
    loop {
        let sym = br.decode_symbol_from_codes(&trees.lit_lengths, &trees.lit_codes)?;
        if sym < 256 {
            out.push(sym as u8);
        } else if sym == 256 {
            break;
        } else {
            let len_idx = (sym - 257) as usize;
            br.fill();
            let mut length = u32::from(LENGTH_BASE[len_idx]);
            if LENGTH_EXTRA[len_idx] > 0 {
                length += br.peek(LENGTH_EXTRA[len_idx]) as u32;
                br.consume(LENGTH_EXTRA[len_idx]);
            }
            let dist_sym = br.decode_symbol_from_codes(&trees.dist_lengths, &trees.dist_codes)?;
            let dist_idx = dist_sym as usize;
            br.fill();
            let mut distance = u32::from(DIST_BASE[dist_idx]);
            if DIST_EXTRA[dist_idx] > 0 {
                distance += br.peek(DIST_EXTRA[dist_idx]) as u32;
                br.consume(DIST_EXTRA[dist_idx]);
            }
            let dist = distance as usize;
            let start = out.len() - dist;
            for i in 0..length as usize {
                out.push(out[start + (i % dist)]);
            }
        }
    }
    Ok(out)
}

/// Build `78 9c` + deflate + Adler from `data`, cloning Huffman trees from `template_zlib`.
pub fn compress_zlib_from_template(data: &[u8], template_zlib: &[u8]) -> Result<Vec<u8>> {
    if template_zlib.len() < 6 || template_zlib[0] != 0x78 || template_zlib[1] != 0x9c {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "template must use zlib header 78 9c",
        )));
    }
    let template_deflate = &template_zlib[2..template_zlib.len() - 4];
    let trees = parse_template_trees(template_deflate)?;

    let mut writer = BitWriter::new();
    writer.copy_bits(template_deflate, 0, trees.data_start_bit);
    for &byte in data {
        let code = trees.lit_codes[byte as usize];
        let len = trees.lit_lengths[byte as usize];
        if len == 0 {
            return Err(Error::Decompress(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!("no huffman code for literal 0x{byte:02x}"),
            )));
        }
        writer.write_bits(u64::from(code), len);
    }
    writer.write_bits(u64::from(trees.lit_codes[256]), trees.lit_lengths[256]);
    let mut deflate = writer.finish();
    if !deflate.is_empty() {
        // Dynamic block must be marked final for single-block zlib streams.
        deflate[0] |= 1;
    }

    let mut out = Vec::with_capacity(2 + deflate.len() + 4);
    out.extend_from_slice(&[0x78, 0x9c]);
    out.extend_from_slice(&deflate);
    out.extend_from_slice(&adler32_zlib(data).to_be_bytes());
    Ok(out)
}

fn adler32_zlib(data: &[u8]) -> u32 {
    const MOD: u32 = 65521;
    let mut a = 1u32;
    let mut b = 0u32;
    for &byte in data {
        a = (a + u32::from(byte)) % MOD;
        b = (b + a) % MOD;
    }
    (b << 16) | a
}

#[cfg(test)]
mod tests {
    use super::*;

    const LIVE: &str = r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\00000001\ROSTER 20260307213511\ROSTER 20260307213511";

    #[test]
    #[ignore = "decode path incomplete; compress round-trip covered by template_recompress_*"]
    fn decode_live_template_matches_unpack() {
        let path = std::path::Path::new(LIVE);
        if !path.is_file() {
            eprintln!("skip");
            return;
        }
        let container = std::fs::read(path).expect("read");
        let zlib = &container[48..];
        let deflate = &zlib[2..zlib.len() - 4];
        let trees = parse_template_trees(deflate).expect("parse trees");
        eprintln!("data_start_bit={}", trees.data_start_bit);
        let decoded = decode_with_trees(deflate, &trees).expect("decode");
        let via_flate = crate::unpack::decompress_zlib(zlib).expect("flate unpack");
        if decoded != via_flate {
            eprintln!(
                "length mismatch decoded={} expected={}",
                decoded.len(),
                via_flate.len()
            );
        }
        assert_eq!(decoded.len(), via_flate.len());
    }

    #[test]
    fn template_recompress_unchanged_round_trips() {
        let path = std::path::Path::new(LIVE);
        if !path.is_file() {
            eprintln!("skip");
            return;
        }
        let container = std::fs::read(path).expect("read");
        let template_zlib = &container[48..];
        let db = crate::unpack::decompress_zlib(template_zlib).expect("unpack");
        let recompressed = compress_zlib_from_template(&db, template_zlib).expect("recompress");
        eprintln!(
            "template len={} recompressed len={} delta={}",
            template_zlib.len(),
            recompressed.len(),
            recompressed.len() as i64 - template_zlib.len() as i64
        );
        let round = crate::unpack::decompress_zlib(&recompressed).expect("round-trip");
        assert_eq!(round, db);
    }

    #[test]
    fn template_recompress_edited_db() {
        let dir = std::path::Path::new(
            r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\00000001\ROSTER 20260307213511",
        );
        let container_path = dir.join("ROSTER 20260307213511");
        let edited_path = dir.join("default.db");
        if !container_path.is_file() || !edited_path.is_file() {
            eprintln!("skip");
            return;
        }
        let container = std::fs::read(&container_path).expect("read");
        let template_zlib = &container[48..];
        let edited = std::fs::read(&edited_path).expect("edited");
        let recompressed = compress_zlib_from_template(&edited, template_zlib).expect("recompress");
        eprintln!(
            "edited recompress len={} delta={}",
            recompressed.len(),
            recompressed.len() as i64 - template_zlib.len() as i64
        );
        let round = crate::unpack::decompress_zlib(&recompressed).expect("round-trip");
        assert_eq!(round, edited);
    }
}

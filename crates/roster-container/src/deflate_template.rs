//! Recompress roster TDB bytes using Huffman trees and LZ ops cloned from a live save template.
//!
//! Game roster saves use multi-block dynamic/fixed/stored deflate at ~1:1 ratio under `78 9c`.
//! We decode the full block stream, adapt ops for edited bytes, and re-encode block-by-block.

use crate::deflate_inflate;

#[cfg(test)]
type BitReader<'a> = deflate_inflate::BitReader<'a>;
use crate::error::{Error, Result};

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

#[derive(Debug, Clone, PartialEq, Eq)]
enum DeflateOp {
    Literal {
        byte: u8,
        start_bit: usize,
        bit_len: u8,
    },
    Copy {
        length: u32,
        distance: u32,
        start_bit: usize,
        bit_len: u8,
    },
}

impl DeflateOp {
    fn output_len(&self) -> usize {
        match self {
            DeflateOp::Literal { .. } => 1,
            DeflateOp::Copy { length, .. } => *length as usize,
        }
    }

    fn op_kind_eq(&self, other: &DeflateOp) -> bool {
        match (self, other) {
            (
                DeflateOp::Literal {
                    byte: a,
                    start_bit: sa,
                    bit_len: ba,
                },
                DeflateOp::Literal {
                    byte: b,
                    start_bit: sb,
                    bit_len: bb,
                },
            ) => a == b && sa == sb && ba == bb,
            (
                DeflateOp::Copy {
                    length: la,
                    distance: da,
                    start_bit: sa,
                    bit_len: ba,
                },
                DeflateOp::Copy {
                    length: lb,
                    distance: db,
                    start_bit: sb,
                    bit_len: bb,
                },
            ) => la == lb && da == db && sa == sb && ba == bb,
            _ => false,
        }
    }
}

#[derive(Debug, Clone)]
struct HuffmanTrees {
    lit_lengths: Vec<u8>,
    lit_codes: Vec<u16>,
    dist_lengths: Vec<u8>,
    dist_codes: Vec<u16>,
}

#[derive(Debug, Clone)]
struct DeflateBlock {
    bfinal: bool,
    btype: u8,
    start_bit: usize,
    tree_end_bit: usize,
    end_bit: usize,
    trees: Option<HuffmanTrees>,
    ops: Vec<DeflateOp>,
    /// When true, copy the compressed block body from the template bit-for-bit.
    copy_from_template: bool,
}

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

fn build_codewords(lengths: &[u8]) -> Result<Vec<u16>> {
    let max_len = *lengths.iter().max().unwrap_or(&0);
    if max_len == 0 {
        return Ok(vec![0; lengths.len()]);
    }
    if max_len == 1 && lengths.iter().filter(|&&l| l == 1).count() == 1 {
        let sym = lengths.iter().position(|&l| l == 1).unwrap();
        let mut codes = vec![0u16; lengths.len()];
        codes[sym] = 0;
        return Ok(codes);
    }

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

    if codespace_used != (1 << max_length) {
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

fn fixed_huffman_trees() -> Result<HuffmanTrees> {
    let mut lit_lengths = vec![0u8; 288];
    for i in 0..144 {
        lit_lengths[i] = 8;
    }
    for i in 144..256 {
        lit_lengths[i] = 9;
    }
    for i in 256..280 {
        lit_lengths[i] = 7;
    }
    for i in 280..288 {
        lit_lengths[i] = 8;
    }
    let dist_lengths = vec![5u8; 32];
    Ok(HuffmanTrees {
        lit_codes: build_codewords(&lit_lengths)?,
        lit_lengths,
        dist_codes: build_codewords(&dist_lengths)?,
        dist_lengths,
    })
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

    fn copy_bits(&mut self, data: &[u8], from_bit: usize, to_bit: usize) -> bool {
        let max_bit = data.len() * 8;
        if to_bit > max_bit {
            return false;
        }
        for bit in from_bit..to_bit {
            self.write_bits(u64::from((data[bit / 8] >> (bit % 8)) & 1), 1);
        }
        true
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

fn decode_deflate_blocks(deflate: &[u8]) -> Result<Vec<DeflateBlock>> {
    let raw = crate::deflate_fdeflate_ops::decode_raw_deflate_blocks(deflate)?;
    let mut blocks = Vec::with_capacity(raw.len());

    for rb in raw {
        let trees = match rb.btype {
            0 => None,
            1 => Some(fixed_huffman_trees()?),
            2 => {
                let mut lit_lengths = rb.lit_lengths.clone().unwrap_or_default();
                let mut dist_lengths = rb.dist_lengths.clone().unwrap_or_default();
                lit_lengths.resize(286, 0);
                dist_lengths.resize(32, 0);
                let mut lit_codes = rb.lit_codes.clone().unwrap_or_default();
                let mut dist_codes = rb.dist_codes.clone().unwrap_or_default();
                lit_codes.resize(286, 0);
                dist_codes.resize(32, 0);
                if lit_codes.iter().all(|&c| c == 0) {
                    lit_codes = build_codewords(&lit_lengths)?;
                }
                if dist_codes.iter().all(|&c| c == 0) {
                    dist_codes = build_codewords(&dist_lengths)?;
                }
                Some(HuffmanTrees {
                    lit_codes,
                    lit_lengths,
                    dist_codes,
                    dist_lengths,
                })
            }
            _ => {
                return Err(Error::Decompress(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    format!("invalid block type {}", rb.btype),
                )));
            }
        };
        let ops: Vec<DeflateOp> = rb
            .ops
            .into_iter()
            .map(|op| match op {
                crate::deflate_fdeflate_ops::RecordedOp::Literal {
                    byte,
                    start_bit,
                    bit_len,
                } => DeflateOp::Literal {
                    byte,
                    start_bit,
                    bit_len,
                },
                crate::deflate_fdeflate_ops::RecordedOp::Copy {
                    length,
                    distance,
                    start_bit,
                    bit_len,
                } => DeflateOp::Copy {
                    length,
                    distance,
                    start_bit,
                    bit_len,
                },
            })
            .collect();
        blocks.push(DeflateBlock {
            bfinal: rb.bfinal,
            btype: rb.btype,
            start_bit: rb.start_bit,
            tree_end_bit: rb.tree_end_bit,
            end_bit: rb.end_bit,
            trees,
            ops,
            copy_from_template: false,
        });
    }
    Ok(blocks)
}

fn apply_ops(out: &mut Vec<u8>, ops: &[DeflateOp]) -> Result<()> {
    for op in ops {
        match *op {
            DeflateOp::Literal { byte, .. } => out.push(byte),
            DeflateOp::Copy { length, distance, .. } => {
                let len = length as usize;
                let dist = distance as usize;
                if dist > out.len() {
                    return Err(Error::Decompress(std::io::Error::new(
                        std::io::ErrorKind::InvalidData,
                        "invalid back-reference distance",
                    )));
                }
                for _ in 0..len {
                    out.push(out[out.len() - dist]);
                }
            }
        }
    }
    Ok(())
}

fn adapt_ops_for_edited(
    ops: &[DeflateOp],
    edited_slice: &[u8],
    mut out: Vec<u8>,
) -> Result<(Vec<DeflateOp>, Vec<u8>)> {
    let mut pos = 0usize;
    let mut adapted = Vec::with_capacity(ops.len());

    for op in ops {
        match *op {
            DeflateOp::Literal {
                byte: _,
                start_bit,
                bit_len,
            } => {
                if pos >= edited_slice.len() {
                    return Err(Error::Decompress(std::io::Error::new(
                        std::io::ErrorKind::InvalidData,
                        "edited slice shorter than block ops",
                    )));
                }
                adapted.push(DeflateOp::Literal {
                    byte: edited_slice[pos],
                    start_bit,
                    bit_len,
                });
                out.push(edited_slice[pos]);
                pos += 1;
            }
            DeflateOp::Copy {
                length,
                distance,
                start_bit,
                bit_len,
            } => {
                let len = length as usize;
                let dist = distance as usize;
                if pos + len > edited_slice.len() {
                    return Err(Error::Decompress(std::io::Error::new(
                        std::io::ErrorKind::InvalidData,
                        "edited slice shorter than block ops",
                    )));
                }
                if dist > out.len() {
                    return Err(Error::Decompress(std::io::Error::new(
                        std::io::ErrorKind::InvalidData,
                        "invalid back-reference distance during adapt",
                    )));
                }
                let start = out.len();
                for _ in 0..len {
                    out.push(out[out.len() - dist]);
                }
                if edited_slice[pos..pos + len] == out[start..] {
                    // The back-reference reproduces the edited bytes; keep the copy op.
                    adapted.push(DeflateOp::Copy {
                        length,
                        distance,
                        start_bit,
                        bit_len,
                    });
                    pos += len;
                } else {
                    out.truncate(start);
                    for i in 0..len {
                        adapted.push(DeflateOp::Literal {
                            byte: edited_slice[pos + i],
                            start_bit: 0,
                            bit_len: 0,
                        });
                        out.push(edited_slice[pos + i]);
                    }
                    pos += len;
                }
            }
        }
    }

    if pos != edited_slice.len() {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            format!(
                "block ops covered {pos} bytes, edited slice is {} bytes",
                edited_slice.len()
            ),
        )));
    }
    Ok((adapted, out))
}

fn adapt_blocks_for_edited(blocks: &[DeflateBlock], edited: &[u8]) -> Result<Vec<DeflateBlock>> {
    let mut out = Vec::new();
    let mut pos = 0usize;
    let mut adapted = Vec::with_capacity(blocks.len());

    for block in blocks {
        let block_len: usize = block.ops.iter().map(DeflateOp::output_len).sum();
        let slice = &edited[pos..pos + block_len];
        let (ops, new_out) = adapt_ops_for_edited(&block.ops, slice, out)?;
        let copy_from_template = ops.iter().zip(block.ops.iter()).all(|(a, b)| a.op_kind_eq(b));
        out = new_out;
        pos += block_len;
        adapted.push(DeflateBlock {
            ops,
            copy_from_template,
            ..block.clone()
        });
    }

    if pos != edited.len() {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            format!(
                "blocks covered {pos} bytes, edited db is {} bytes",
                edited.len()
            ),
        )));
    }
    Ok(adapted)
}

fn find_length_symbol(length: u32) -> Result<(u16, u32)> {
    for (idx, &base) in LENGTH_BASE.iter().enumerate() {
        let extra = LENGTH_EXTRA[idx];
        let base = u32::from(base);
        let max = base + ((1u32 << extra) - 1);
        if length >= base && length <= max {
            let extra_bits = if extra > 0 { length - base } else { 0 };
            return Ok((257 + idx as u16, extra_bits));
        }
    }
    Err(Error::Decompress(std::io::Error::new(
        std::io::ErrorKind::InvalidData,
        format!("length {length} out of range"),
    )))
}

fn find_distance_symbol(distance: u32) -> Result<(u16, u32)> {
    for (idx, &base) in DIST_BASE.iter().enumerate() {
        let extra = DIST_EXTRA[idx];
        let base = u32::from(base);
        let max = base + ((1u32 << extra) - 1);
        if distance >= base && distance <= max {
            let extra_bits = if extra > 0 { distance - base } else { 0 };
            return Ok((idx as u16, extra_bits));
        }
    }
    Err(Error::Decompress(std::io::Error::new(
        std::io::ErrorKind::InvalidData,
        format!("distance {distance} out of range"),
    )))
}

fn encode_literal(writer: &mut BitWriter, trees: &HuffmanTrees, byte: u8) -> Result<()> {
    let len = trees.lit_lengths[byte as usize];
    if len == 0 {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            format!("no huffman code for literal 0x{byte:02x}"),
        )));
    }
    writer.write_bits(u64::from(trees.lit_codes[byte as usize]), len);
    Ok(())
}

fn encode_copy(
    writer: &mut BitWriter,
    trees: &HuffmanTrees,
    length: u32,
    distance: u32,
) -> Result<()> {
    // Length 258 has two valid encodings (285 with 0 extras, or 284 + 5 extra bits).
    // zlib-style encoders (and the game) use 285; prefer it when the tree defines it.
    let (len_sym, len_extra) =
        if length == 258 && trees.lit_lengths.get(285).copied().unwrap_or(0) != 0 {
            (285u16, 0u32)
        } else {
            find_length_symbol(length)?
        };
    let len_idx = (len_sym - 257) as usize;
    writer.write_bits(
        u64::from(trees.lit_codes[len_sym as usize]),
        trees.lit_lengths[len_sym as usize],
    );
    if LENGTH_EXTRA[len_idx] > 0 {
        writer.write_bits(u64::from(len_extra), LENGTH_EXTRA[len_idx]);
    }

    let (dist_sym, dist_extra) = find_distance_symbol(distance)?;
    let dist_idx = dist_sym as usize;
    writer.write_bits(
        u64::from(trees.dist_codes[dist_sym as usize]),
        trees.dist_lengths[dist_sym as usize],
    );
    if DIST_EXTRA[dist_idx] > 0 {
        writer.write_bits(u64::from(dist_extra), DIST_EXTRA[dist_idx]);
    }
    Ok(())
}

fn encode_ops(writer: &mut BitWriter, trees: &HuffmanTrees, ops: &[DeflateOp]) -> Result<()> {
    for op in ops {
        match *op {
            DeflateOp::Literal { byte, .. } => encode_literal(writer, trees, byte)?,
            DeflateOp::Copy {
                length,
                distance,
                ..
            } => encode_copy(writer, trees, length, distance)?,
        }
    }
    writer.write_bits(
        u64::from(trees.lit_codes[256]),
        trees.lit_lengths[256],
    );
    Ok(())
}

fn encode_stored_block(
    writer: &mut BitWriter,
    bfinal: bool,
    ops: &[DeflateOp],
) -> Result<()> {
    writer.write_bits(u64::from(bfinal as u64), 1);
    writer.write_bits(0, 2);
    if writer.nbits % 8 != 0 {
        writer.write_bits(0, 8 - (writer.nbits % 8));
    }
    let len = ops.len() as u16;
    writer.write_bits(u64::from(len), 16);
    writer.write_bits(u64::from(!len), 16);
    for op in ops {
        let DeflateOp::Literal { byte, .. } = op else {
            return Err(Error::Decompress(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "stored block ops must be literals",
            )));
        };
        writer.write_bits(u64::from(*byte), 8);
    }
    Ok(())
}

/// Re-emit the full deflate stream: blocks are bit-contiguous (no inter-block padding).
/// Unchanged blocks are copied from the template verbatim; changed dynamic blocks copy their
/// tree header bits and re-encode every op with the exact captured Huffman codes.
fn encode_blocks(
    template_deflate: &[u8],
    blocks: &[DeflateBlock],
) -> Result<Vec<u8>> {
    let mut writer = BitWriter::new();
    for block in blocks {
        match block.btype {
            0 => encode_stored_block(&mut writer, block.bfinal, &block.ops)?,
            1 => {
                writer.write_bits(u64::from(block.bfinal), 1);
                writer.write_bits(1, 2);
                let trees = block.trees.as_ref().ok_or_else(|| {
                    Error::Decompress(std::io::Error::new(
                        std::io::ErrorKind::InvalidData,
                        "fixed block missing trees",
                    ))
                })?;
                encode_ops(&mut writer, trees, &block.ops)?;
            }
            2 => {
                if block.copy_from_template {
                    writer.copy_bits(template_deflate, block.start_bit, block.end_bit);
                } else {
                    // bfinal + btype + Huffman tree definition, bit-exact from the template.
                    writer.copy_bits(template_deflate, block.start_bit, block.tree_end_bit);
                    let trees = block
                        .trees
                        .as_ref()
                        .ok_or_else(|| {
                            Error::Decompress(std::io::Error::new(
                                std::io::ErrorKind::InvalidData,
                                "dynamic block missing trees",
                            ))
                        })?;
                    encode_ops(&mut writer, trees, &block.ops)?;
                }
            }
            _ => {
                return Err(Error::Decompress(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    format!("unsupported block type {}", block.btype),
                )));
            }
        }
    }
    Ok(writer.finish())
}

/// Build `78 9c` + deflate + Adler from `data`, cloning Huffman trees and LZ ops from `template_zlib`.
pub fn compress_zlib_from_template(data: &[u8], template_zlib: &[u8]) -> Result<Vec<u8>> {
    if template_zlib.len() < 6 || template_zlib[0] != 0x78 || template_zlib[1] != 0x9c {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "template must use zlib header 78 9c",
        )));
    }
    let template_deflate = &template_zlib[2..template_zlib.len() - 4];
    let blocks = decode_deflate_blocks(template_deflate)?;
    let adapted = adapt_blocks_for_edited(&blocks, data)?;
    if adapted.iter().all(|b| b.copy_from_template) {
        return Ok(template_zlib.to_vec());
    }

    let deflate = encode_blocks(template_deflate, &adapted)?;

    let mut out = Vec::with_capacity(template_zlib.len());
    out.extend_from_slice(&[0x78, 0x9c]);
    out.extend_from_slice(&deflate);
    out.extend_from_slice(&adler32_zlib(data).to_be_bytes());
    // Game roster inner blobs pad valid zlib to a fixed ~2.46 MB with zero trailer bytes.
    if out.len() < template_zlib.len() {
        out.resize(template_zlib.len(), 0);
    }
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

    fn live_zlib() -> Option<Vec<u8>> {
        let path = std::path::Path::new(LIVE);
        if !path.is_file() {
            return None;
        }
        let container = std::fs::read(path).ok()?;
        Some(container.get(48..)?.to_vec())
    }

    /// Read `n` bits LSB-first starting at absolute bit offset `from` in `data`.
    fn read_bits_at(data: &[u8], from: usize, n: usize) -> u64 {
        let mut v = 0u64;
        for i in 0..n {
            let bit = from + i;
            v |= u64::from((data[bit / 8] >> (bit % 8)) & 1) << i;
        }
        v
    }

    #[test]
    fn tree_capture_diagnostic() {
        let Some(zlib) = live_zlib() else {
            eprintln!("skip");
            return;
        };
        let deflate = &zlib[2..zlib.len() - 4];
        let mut br = BitReader::new(deflate);
        let (lit, dist, _tables) =
            crate::deflate_fdeflate_trees::read_dynamic_trees(&mut br).expect("independent trees");
        let blocks = decode_deflate_blocks(deflate).expect("blocks");
        let t = blocks[0].trees.as_ref().expect("captured trees");

        eprintln!(
            "independent: hlit_len={} lit[0]={} lit[0x25]={} lit[256]={} dist_len={}",
            lit.len(),
            lit[0],
            lit[0x25],
            lit.get(256).copied().unwrap_or(0),
            dist.len()
        );
        eprintln!(
            "captured:    len={} lit[0]={} lit[0x25]={} lit[256]={} dist_len={}",
            t.lit_lengths.len(),
            t.lit_lengths[0],
            t.lit_lengths[0x25],
            t.lit_lengths[256],
            t.dist_lengths.len()
        );
        let n = lit.len().min(t.lit_lengths.len());
        let diffs: Vec<usize> = (0..n).filter(|&i| lit[i] != t.lit_lengths[i]).collect();
        eprintln!("lit length diffs: {} of {}", diffs.len(), n);
        for &i in diffs.iter().take(15) {
            eprintln!(
                "  sym {i}: independent={} captured={}",
                lit[i], t.lit_lengths[i]
            );
        }
        let nd = dist.len().min(t.dist_lengths.len());
        let ddiffs: Vec<usize> = (0..nd).filter(|&i| dist[i] != t.dist_lengths[i]).collect();
        eprintln!("dist length diffs: {} of {}", ddiffs.len(), nd);
        for &i in ddiffs.iter().take(10) {
            eprintln!(
                "  dsym {i}: independent={} captured={}",
                dist[i], t.dist_lengths[i]
            );
        }
    }

    /// Derive the true literal code table from the stream itself: every unpaired literal's
    /// recorded slot gives (byte -> bit_len, codeword). Check internal consistency and compare
    /// against both the captured and independently parsed trees.
    #[test]
    fn derive_lit_codes_from_stream() {
        let Some(zlib) = live_zlib() else {
            eprintln!("skip");
            return;
        };
        let deflate = &zlib[2..zlib.len() - 4];
        let blocks = decode_deflate_blocks(deflate).expect("blocks");
        let block = &blocks[0];
        let captured = block.trees.as_ref().expect("trees");

        eprintln!(
            "block start_bit={} tree_end_bit={} end_bit={}",
            block.start_bit, block.tree_end_bit, block.end_bit
        );
        for (i, op) in block.ops.iter().take(8).enumerate() {
            eprintln!("op[{i}] {op:?}");
        }

        let mut derived_len = [0u8; 286];
        let mut derived_code = [0u64; 286];
        let mut inconsistent = 0usize;
        let mut seen = [false; 286];
        let mut unpaired = 0usize;

        let ops = &block.ops;
        let mut i = 0usize;
        while i < ops.len() {
            if let DeflateOp::Literal {
                byte,
                start_bit,
                bit_len,
            } = ops[i]
            {
                if bit_len == 0 {
                    i += 1;
                    continue;
                }
                let paired = matches!(ops.get(i + 1), Some(DeflateOp::Literal { bit_len: 0, .. }));
                if !paired {
                    unpaired += 1;
                    let code = read_bits_at(deflate, start_bit, bit_len as usize);
                    let b = byte as usize;
                    if !seen[b] {
                        seen[b] = true;
                        derived_len[b] = bit_len;
                        derived_code[b] = code;
                    } else if derived_len[b] != bit_len || derived_code[b] != code {
                        inconsistent += 1;
                        if inconsistent <= 10 {
                            eprintln!(
                                "INCONSISTENT byte={byte:02x} first(len={},code={:b}) now(len={},code={:b}) at op[{i}] start_bit={start_bit}",
                                derived_len[b], derived_code[b], bit_len, code
                            );
                        }
                    }
                    i += 1;
                } else {
                    i += 2;
                }
            } else {
                i += 1;
            }
        }

        let seen_count = seen.iter().filter(|&&s| s).count();
        eprintln!("unpaired={unpaired} distinct_bytes_seen={seen_count} inconsistent={inconsistent}");

        let mut cap_len_diff = 0usize;
        let mut cap_code_diff = 0usize;
        for b in 0..256usize {
            if !seen[b] {
                continue;
            }
            if captured.lit_lengths[b] != derived_len[b] {
                cap_len_diff += 1;
                if cap_len_diff <= 10 {
                    eprintln!(
                        "captured len diff byte={b:02x} captured={} derived={}",
                        captured.lit_lengths[b], derived_len[b]
                    );
                }
            } else if u64::from(captured.lit_codes[b]) != derived_code[b] {
                cap_code_diff += 1;
                if cap_code_diff <= 10 {
                    eprintln!(
                        "captured code diff byte={b:02x} len={} captured={:b} derived={:b}",
                        derived_len[b], captured.lit_codes[b], derived_code[b]
                    );
                }
            }
        }
        eprintln!("captured vs derived: len_diffs={cap_len_diff} code_diffs={cap_code_diff}");
    }

    /// Every recorded op, re-emitted with the captured Huffman codes, must reproduce the
    /// template bitstream bit-for-bit at its recorded offset. This is the master proof that
    /// a full re-encode of adapted ops yields a stream the game's inflater accepts.
    #[test]
    fn op_bits_match_template() {
        let Some(zlib) = live_zlib() else {
            eprintln!("skip");
            return;
        };
        let deflate = &zlib[2..zlib.len() - 4];
        let blocks = decode_deflate_blocks(deflate).expect("decode blocks");
        eprintln!("blocks={}", blocks.len());
        for (bi, b) in blocks.iter().enumerate() {
            eprintln!(
                "block[{bi}] bfinal={} btype={} start_bit={} tree_end={} end_bit={} ops={}",
                b.bfinal,
                b.btype,
                b.start_bit,
                b.tree_end_bit,
                b.end_bit,
                b.ops.len()
            );
        }

        let mut lit_mism = 0usize;
        let mut pair_mism = 0usize;
        let mut copy_len_mism = 0usize;
        let mut copy_bits_mism = 0usize;
        let mut eob_mism = 0usize;
        let mut checked = 0usize;
        let mut reports = 0usize;

        for block in &blocks {
            let trees = block.trees.as_ref().expect("trees");
            let ops = &block.ops;
            let mut i = 0usize;
            while i < ops.len() {
                match ops[i] {
                    DeflateOp::Literal {
                        byte,
                        start_bit,
                        bit_len,
                    } => {
                        if bit_len == 0 {
                            // b1 of a pair; validated together with its b0.
                            i += 1;
                            continue;
                        }
                        let paired = matches!(
                            ops.get(i + 1),
                            Some(DeflateOp::Literal { bit_len: 0, .. })
                        );
                        if paired {
                            let DeflateOp::Literal { byte: b1, .. } = ops[i + 1] else {
                                unreachable!()
                            };
                            let l0 = trees.lit_lengths[byte as usize];
                            let l1 = trees.lit_lengths[b1 as usize];
                            let total = l0 + l1;
                            let code = u64::from(trees.lit_codes[byte as usize])
                                | (u64::from(trees.lit_codes[b1 as usize]) << l0);
                            let want = read_bits_at(deflate, start_bit, bit_len as usize);
                            if total != bit_len || code != want {
                                pair_mism += 1;
                                if reports < 12 {
                                    eprintln!(
                                        "pair mismatch op[{i}] bytes={byte:02x},{b1:02x} l0={l0} l1={l1} slot={bit_len} code={code:0w$b} want={want:0w$b}",
                                        w = bit_len as usize
                                    );
                                    reports += 1;
                                }
                            }
                            i += 2;
                        } else {
                            let l = trees.lit_lengths[byte as usize];
                            let code = u64::from(trees.lit_codes[byte as usize]);
                            let want = read_bits_at(deflate, start_bit, bit_len as usize);
                            if l != bit_len || code != want {
                                lit_mism += 1;
                                if reports < 12 {
                                    eprintln!(
                                        "lit mismatch op[{i}] byte={byte:02x} len={l} slot={bit_len} code={code:b} want={want:b}"
                                    );
                                    reports += 1;
                                }
                            }
                            i += 1;
                        }
                        checked += 1;
                    }
                    DeflateOp::Copy {
                        length,
                        distance,
                        start_bit,
                        bit_len,
                    } => {
                        let mut w = BitWriter::new();
                        encode_copy(&mut w, trees, length, distance).expect("encode copy");
                        let emitted = w.out.len() * 8 + usize::from(w.nbits);
                        let bytes = w.finish();
                        if emitted != usize::from(bit_len) {
                            copy_len_mism += 1;
                            if reports < 12 {
                                eprintln!(
                                    "copy len mismatch op[{i}] len={length} dist={distance} emitted={emitted} slot={bit_len}"
                                );
                                reports += 1;
                            }
                        } else {
                            let got = read_bits_at(&bytes, 0, emitted.min(64));
                            let want = read_bits_at(deflate, start_bit, emitted.min(64));
                            if got != want {
                                copy_bits_mism += 1;
                                if reports < 12 {
                                    eprintln!(
                                        "copy bits mismatch op[{i}] len={length} dist={distance} bits={emitted} got={got:0w$b} want={want:0w$b}",
                                        w = emitted.min(64)
                                    );
                                    reports += 1;
                                }
                            }
                        }
                        checked += 1;
                        i += 1;
                    }
                }
            }

            // EOB codeword sits at the end of the block's bit range.
            let eob_len = usize::from(trees.lit_lengths[256]);
            let eob_code = u64::from(trees.lit_codes[256]);
            let eob_want = read_bits_at(deflate, block.end_bit - eob_len, eob_len);
            if eob_code != eob_want {
                eob_mism += 1;
                eprintln!(
                    "EOB mismatch: code={eob_code:0w$b} want={eob_want:0w$b} len={eob_len}",
                    w = eob_len
                );
            }
        }

        eprintln!(
            "checked={checked} lit_mism={lit_mism} pair_mism={pair_mism} copy_len_mism={copy_len_mism} copy_bits_mism={copy_bits_mism} eob_mism={eob_mism}"
        );
        assert_eq!(
            lit_mism + pair_mism + copy_len_mism + copy_bits_mism + eob_mism,
            0,
            "op re-encode must match template bits exactly"
        );
    }

    #[test]
    fn fdeflate_continues_past_125327() {
        let Some(zlib) = live_zlib() else {
            eprintln!("skip");
            return;
        };
        let deflate = &zlib[2..zlib.len() - 4];

        let mut dec = fdeflate::Decompressor::new();
        dec.ignore_adler32();
        let mut out = vec![0u8; 125_327];
        let (consumed1, produced1) = dec.read(&zlib, &mut out, 0, false).expect("read1");
        eprintln!("fdeflate read1: consumed={consumed1} produced={produced1}");

        let mut full = vec![0u8; 3_000_000];
        full[..125_327].copy_from_slice(&out);
        let (consumed2, produced2) = dec
            .read(&zlib[consumed1..], &mut full, 125_327, true)
            .expect("read2");
        eprintln!(
            "fdeflate read2: consumed={consumed2} produced={produced2} total={}",
            125_327 + produced2
        );
        eprintln!("fdeflate is_done={}", dec.is_done());

        let mut br = BitReader::new(deflate);
        let (_lit, _dist, tables) =
            crate::deflate_fdeflate_trees::read_dynamic_trees(&mut br).expect("trees");
        eprintln!(
            "our tree_end bits={} eof_code={:#x} eof_mask={:#x} eof_bits={}",
            br.bits_consumed(),
            tables.eof_code,
            tables.eof_mask,
            tables.eof_bits
        );
    }

    #[test]
    fn decode_blocks_expand_matches_template_db() {
        let Some(zlib) = live_zlib() else {
            eprintln!("skip");
            return;
        };
        let deflate = &zlib[2..zlib.len() - 4];
        let blocks = decode_deflate_blocks(deflate).expect("decode blocks");
        let mut expanded = Vec::new();
        for block in &blocks {
            apply_ops(&mut expanded, &block.ops).expect("expand");
        }
        let via_flate = crate::unpack::decompress_zlib(&zlib).expect("flate unpack");
        eprintln!(
            "blocks={} expanded={} expected={}",
            blocks.len(),
            expanded.len(),
            via_flate.len()
        );
        for (i, block) in blocks.iter().enumerate() {
            let block_len: usize = block.ops.iter().map(DeflateOp::output_len).sum();
            eprintln!(
                "  block[{i}] bfinal={} btype={} ops={} out={} start_bit={} tree_end_bit={} end_bit={}",
                block.bfinal,
                block.btype,
                block.ops.len(),
                block_len,
                block.start_bit,
                block.tree_end_bit,
                block.end_bit
            );
        }
        if !via_flate.is_empty() && expanded.len() < via_flate.len() {
            let n = expanded.len().min(via_flate.len());
            let first_diff = expanded
                .iter()
                .zip(via_flate.iter())
                .position(|(a, b)| a != b);
            eprintln!("first diff at {first_diff:?}, expanded_len={}", expanded.len());
        }
        assert_eq!(expanded, via_flate);
    }

    #[test]
    fn op_recompress_unchanged_near_template_size() {
        let Some(zlib) = live_zlib() else {
            eprintln!("skip");
            return;
        };
        let db = crate::unpack::decompress_zlib(&zlib).expect("unpack");
        let recompressed = compress_zlib_from_template(&db, &zlib).expect("recompress");
        eprintln!(
            "template len={} recompressed len={} delta={}",
            zlib.len(),
            recompressed.len(),
            recompressed.len() as i64 - zlib.len() as i64
        );
        let round = crate::unpack::decompress_zlib(&recompressed).expect("round-trip");
        assert_eq!(round, db);
        assert!(
            (recompressed.len() as i64 - zlib.len() as i64).abs() <= 128,
            "unchanged op recompress should match template payload size within padding"
        );
    }

    /// Full re-encode of all blocks (early-out bypassed, `copy_from_template = false`) must
    /// reproduce the template deflate stream bit-for-bit through the final EOB.
    #[test]
    fn full_reencode_unchanged_bit_identical() {
        let Some(zlib) = live_zlib() else {
            eprintln!("skip");
            return;
        };
        let deflate = &zlib[2..zlib.len() - 4];
        let blocks = decode_deflate_blocks(deflate).expect("decode");
        let end_bit = blocks.last().expect("blocks").end_bit;
        let encoded = encode_blocks(deflate, &blocks).expect("encode");

        let valid_bytes = end_bit / 8;
        assert!(encoded.len() >= valid_bytes);
        let mut first_diff = None;
        for i in 0..valid_bytes {
            if encoded[i] != deflate[i] {
                first_diff = Some(i);
                break;
            }
        }
        eprintln!(
            "template valid_bytes={valid_bytes} encoded={} first_diff={first_diff:?}",
            encoded.len()
        );
        assert_eq!(first_diff, None, "re-encode must be bit-identical to template");
        // Trailing partial byte: template pads EOB with zero bits, so must we.
        if end_bit % 8 != 0 {
            assert_eq!(encoded[valid_bytes], deflate[valid_bytes]);
        }
    }

    #[test]
    fn edited_diff_op_mapping() {
        let dir = std::path::Path::new(
            r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC\00000001\ROSTER 20260307213511",
        );
        let container_path = dir.join("ROSTER 20260307213511");
        let edited_path = dir.join("default.db");
        let backup_path = dir.join("default.db.bak");
        if !container_path.is_file() || !edited_path.is_file() || !backup_path.is_file() {
            eprintln!("skip");
            return;
        }
        let container = std::fs::read(&container_path).expect("read");
        let edited = std::fs::read(&edited_path).expect("edited");
        let backup = std::fs::read(&backup_path).expect("backup");
        let deflate = &container[48 + 2..container.len() - 4];
        let blocks = decode_deflate_blocks(deflate).expect("decode");
        let adapted = adapt_blocks_for_edited(&blocks, &edited).expect("adapt");
        let mut expanded_adap = Vec::new();
        for block in &adapted {
            apply_ops(&mut expanded_adap, &block.ops).expect("expand");
        }
        assert_eq!(expanded_adap, edited, "adapted ops must expand to edited db");
        eprintln!(
            "blocks={} changed={}",
            adapted.len(),
            adapted.iter().filter(|b| !b.copy_from_template).count()
        );

        let mut diffs = Vec::new();
        for (off, (&a, &b)) in edited.iter().zip(backup.iter()).enumerate() {
            if a != b {
                diffs.push((off, b, a));
            }
        }
        eprintln!("db diffs {}", diffs.len());

        let mut pos = 0usize;
        for (block_idx, block) in blocks.iter().enumerate() {
            let trees = block.trees.as_ref().expect("trees");
            for (op_idx, op) in block.ops.iter().enumerate() {
                let len = op.output_len();
                for (off, was, now) in &diffs {
                    if *off >= pos && *off < pos + len {
                        let patchable = match op {
                            DeflateOp::Literal { bit_len, .. } if *bit_len > 0 => {
                                trees.lit_lengths[*now as usize] == *bit_len
                            }
                            _ => false,
                        };
                        let kind = match op {
                            DeflateOp::Literal { bit_len, .. } => {
                                format!("literal bit_len={bit_len} patchable={patchable}")
                            }
                            DeflateOp::Copy { length, distance, .. } => {
                                format!("copy len={length} dist={distance}")
                            }
                        };
                        eprintln!(
                            "  diff 0x{off:x} {was:02x}->{now:02x} in block[{block_idx}] op[{op_idx}] {kind}"
                        );
                    }
                }
                pos += len;
            }
        }
    }

    #[test]
    fn op_recompress_edited_db() {
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
        let template_zlib = container[48..].to_vec();
        let template_db = crate::unpack::decompress_zlib(&template_zlib).expect("template db");
        let edited = std::fs::read(&edited_path).expect("edited");
        let recompressed = compress_zlib_from_template(&edited, &template_zlib).expect("recompress");
        eprintln!(
            "edited recompress len={} delta={}",
            recompressed.len(),
            recompressed.len() as i64 - template_zlib.len() as i64
        );
        assert!(
            recompressed.len() <= template_zlib.len(),
            "recompressed payload must fit the template allocation"
        );

        // fdeflate-style decode (mirrors the game's inflater) must yield the edited DB.
        let mut dec = crate::deflate_fdeflate_ops::Decompressor::new();
        let mut out = vec![0u8; 3_000_000];
        let (_, produced) = dec
            .read(&recompressed, &mut out, 0, true)
            .expect("fdeflate-style decode");
        let fdef = &out[..produced];
        eprintln!(
            "fdeflate round-trip len={produced} ==edited {} ==backup {}",
            fdef == edited.as_slice(),
            fdef == template_db.as_slice()
        );
        assert_eq!(fdef, edited.as_slice(), "fdeflate round-trip != edited db");

        // flate2 must agree.
        let round = crate::unpack::decompress_zlib(&recompressed).expect("flate2 round-trip");
        assert_eq!(round, edited, "flate2 round-trip != edited db");
    }
}

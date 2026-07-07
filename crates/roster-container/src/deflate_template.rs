//! Recompress roster TDB bytes using Huffman trees and LZ ops cloned from a live save template.
//!
//! Game roster saves use multi-block dynamic/fixed/stored deflate at ~1:1 ratio under `78 9c`.
//! We decode the full block stream, adapt ops for edited bytes, and re-encode block-by-block.

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
    let mut seen_changed = false;

    for block in blocks {
        let block_len: usize = block.ops.iter().map(DeflateOp::output_len).sum();
        let slice = &edited[pos..pos + block_len];
        let (ops, new_out) = adapt_ops_for_edited(&block.ops, slice, out)?;
        let mut copy_from_template = ops.iter().zip(block.ops.iter()).all(|(a, b)| a.op_kind_eq(b));

        // Once any block needs re-encoding, all subsequent blocks must also
        // be re-encoded (not copy-from-template) to avoid bit-shift
        // misalignment when the preceding block's re-encoded bit-length
        // differs from the template.
        if seen_changed {
            copy_from_template = false;
        }
        if !copy_from_template {
            seen_changed = true;
        }

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
/// Inspect deflate block structure for debugging/mapping.
pub fn inspect_deflate_blocks(template_zlib: &[u8]) -> Result<Vec<DeflateBlockMeta>> {
    if template_zlib.len() < 2 {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "zlib too short",
        )));
    }
    let template_deflate = &template_zlib[2..template_zlib.len() - 4];
    let blocks = decode_deflate_blocks(template_deflate)?;
    let mut tdb_pos = 0usize;
    let mut metas = Vec::new();
    for blk in &blocks {
        let uncompressed_size: usize = blk.ops.iter().map(|op| op.output_len()).sum();
        let next_tdb = tdb_pos + uncompressed_size;
        metas.push(DeflateBlockMeta {
            bfinal: blk.bfinal,
            btype: blk.btype,
            start_bit: blk.start_bit,
            end_bit: blk.end_bit,
            uncompressed_size,
            tdb_start: tdb_pos,
            tdb_end: next_tdb,
        });
        tdb_pos = next_tdb;
    }
    Ok(metas)
}

#[derive(Debug, Clone)]
pub struct DeflateBlockMeta {
    pub bfinal: bool,
    pub btype: u8,
    pub start_bit: usize,
    pub end_bit: usize,
    pub uncompressed_size: usize,
    pub tdb_start: usize,
    pub tdb_end: usize,
}

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
    // The game reads exactly template_zlib.len() bytes of zlib; any deviation breaks block alignment
    // for games that decompress in multiple fixed-size chunks.
    out.resize(template_zlib.len(), 0); // Always force exact template size (pad or truncate trailing zeros)
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
            // Fallback to TRADEEDIT5
            let t5 = std::path::Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../../_local/game-saves/xbox/TRADEEDIT5"));
            if t5.is_file() {
                let container = std::fs::read(t5).ok()?;
                return Some(container.get(48..)?.to_vec());
            }
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

    /// Compare flate2 vs fdeflate decompression of the live save. A mismatch would explain
    /// why Rust-unpacked-then-repacked saves corrupt in-game while Modding Studio ones don't.
    #[test]
    fn flate2_vs_fdeflate_decompress_live() {
        let container_path = std::path::Path::new(
            r"C:\Users\galileo\Documents\nhllegacy\B13EBABEBABEBABE\454109EC.backup-20260705\00000001\ROSTER 20260307213511\ROSTER 20260307213511",
        );
        if !container_path.is_file() {
            eprintln!("skip: no live save");
            return;
        }
        let container = std::fs::read(container_path).expect("read");
        let zlib = &container[48..];

        // flate2 decompress
        let flate2_db = crate::unpack::decompress_zlib(zlib).expect("flate2");
        eprintln!("flate2 decompressed: {} bytes", flate2_db.len());

        // fdeflate decompress
        let mut dec = crate::deflate_fdeflate_ops::Decompressor::new();
        let mut out = vec![0u8; 3_000_000];
        let (_, produced) = dec.read(zlib, &mut out, 0, true).expect("fdeflate");
        let fdeflate_db = &out[..produced];
        eprintln!("fdeflate decompressed: {produced} bytes");

        let mut diffs = 0usize;
        let max_len = flate2_db.len().min(fdeflate_db.len());
        let mut first = Vec::new();
        for i in 0..max_len {
            if flate2_db[i] != fdeflate_db[i] {
                diffs += 1;
                if first.len() < 30 {
                    first.push((i, flate2_db[i], fdeflate_db[i]));
                }
            }
        }
        if flate2_db.len() != fdeflate_db.len() {
            eprintln!("LENGTH MISMATCH: flate2={} fdeflate={}", flate2_db.len(), fdeflate_db.len());
        }
        eprintln!("diffs: {diffs}");
        for (offset, fl2, fd) in &first {
            eprintln!("  0x{offset:06X}: flate2=0x{fl2:02X} fdeflate=0x{fd:02X}");
        }
        assert_eq!(diffs, 0, "flate2 and fdeflate must decompress identically");
    }

    /// Map deflate block byte spans so we can identify which block contains a given DB offset.
    #[test]
    fn block_byte_spans() {
        let Some(zlib) = live_zlib() else {
            eprintln!("skip");
            return;
        };
        let deflate = &zlib[2..zlib.len() - 4];
        let blocks = decode_deflate_blocks(deflate).expect("decode blocks");
        let mut pos = 0usize;
        for (i, b) in blocks.iter().enumerate() {
            let len: usize = b.ops.iter().map(DeflateOp::output_len).sum();
            let end = pos + len;
            let kind = match b.btype {
                0 => "stored",
                1 => "fixed ",
                2 => "dynamic",
                _ => "unknown",
            };
            eprintln!(
                "block[{i:2}] {kind} ops={:5} bytes=[0x{pos:06X}..0x{end:06X}) len={len} start_bit={} end_bit={}",
                b.ops.len(),
                b.start_bit,
                b.end_bit
            );
            pos = end;
        }
        eprintln!("total={pos} expected={}", 2456076usize);
    }

    /// Force a full re-encode of the flate2-decompressed DB by editing the first byte of
    /// block 0 (offset 0x40, in the TDB header magic area). If the re-encoder produces a
    /// stream that fails fdeflate round-trip, we've found the root cause.
    #[test]
    fn reencode_edited_flate2_db_fdeflate_roundtrip() {
        let Some(zlib) = live_zlib() else {
            eprintln!("skip");
            return;
        };
        let mut db = crate::unpack::decompress_zlib(&zlib).expect("flate2 decompress");
        // Edit a byte early in block 0 (well past "DB" magic at offset 0)
        db[0x40] ^= 0x01;
        eprintln!("edited db[0x40] 0x{:02X} -> 0x{:02X}", db[0x40] ^ 0x01, db[0x40]);
        eprintln!("flate2: {} bytes", db.len());

        let recompressed = compress_zlib_from_template(&db, &zlib).expect("recompress");
        eprintln!(
            "template={} recompressed={} delta={}",
            zlib.len(), recompressed.len(),
            recompressed.len() as i64 - zlib.len() as i64
        );

        // flate2 round-trip
        let flate2_rt = crate::unpack::decompress_zlib(&recompressed).expect("flate2 rt");
        assert_eq!(flate2_rt, db, "flate2 round-trip must match edited DB");

        // fdeflate round-trip
        let mut dec = crate::deflate_fdeflate_ops::Decompressor::new();
        let mut out = vec![0u8; 3_000_000];
        match dec.read(&recompressed, &mut out, 0, true) {
            Ok((_, produced)) => {
                let fdef = &out[..produced];
                eprintln!("fdeflate rt: {produced} bytes");
                let diffs: Vec<_> = db.iter().zip(fdef.iter()).enumerate()
                    .filter(|(_, (a,b))| a!=b).take(10).collect();
                if diffs.is_empty() && fdef.len() == db.len() {
                    eprintln!("PASS: fdeflate round-trips edited flate2 DB");
                } else {
                    eprintln!("FAIL: {} diffs", db.iter().zip(fdef.iter()).filter(|(a,b)| a!=b).count());
                    for (off, (a,b)) in &diffs {
                        eprintln!("  0x{off:06X}: db=0x{a:02X} fdef=0x{b:02X}");
                    }
                    panic!("fdeflate round-trip failed");
                }
            }
            Err(e) => {
                eprintln!("fdeflate DECODE FAILED: {e:?}");
                panic!("fdeflate cannot decode re-encoded stream");
            }
        }
    }

    /// Compare block-by-block adaptation between Rust-unpacked DB and MS DB.
    #[test]
    fn compare_adaptation_rust_vs_ms() {
        let Some(t5_zlib) = live_zlib() else {
            eprintln!("skip");
            return;
        };
        let deflate = &t5_zlib[2..t5_zlib.len() - 4];
        let template_blocks = decode_deflate_blocks(deflate).expect("decode template");

        // Rust path: flate2-decompressed TRADEEDIT5 + 1-byte edit
        let t5_db = crate::unpack::decompress_zlib(&t5_zlib).expect("flate2 t5");
        let mut rust_db = t5_db.clone();
        rust_db[0x0B949B] = 0x40;
        let rust_adapted = adapt_blocks_for_edited(&template_blocks, &rust_db).expect("adapt rust");
        
        // MS path: Modding Studio-extracted DB
        let ms_db_path = std::path::Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../_local/game-saves/xbox/hedman_col.db"
        ));
        let ms_db = std::fs::read(ms_db_path).expect("read MS DB");
        let ms_adapted = adapt_blocks_for_edited(&template_blocks, &ms_db).expect("adapt MS");

        let mut interesting = 0usize;
        for i in 0..template_blocks.len() {
            let tb = &template_blocks[i];
            let ra = &rust_adapted[i];
            let ma = &ms_adapted[i];
            let r_lits = ra.ops.iter().filter(|o| matches!(o, DeflateOp::Literal{..})).count();
            let r_copys = ra.ops.iter().filter(|o| matches!(o, DeflateOp::Copy{..})).count();
            let m_lits = ma.ops.iter().filter(|o| matches!(o, DeflateOp::Literal{..})).count();
            let m_copys = ma.ops.iter().filter(|o| matches!(o, DeflateOp::Copy{..})).count();
            
            let rc = ra.copy_from_template;
            let mc = ma.copy_from_template;
            if r_lits != m_lits || r_copys != m_copys || rc != mc {
                interesting += 1;
                eprintln!(
                    "block[{i:2}] rust: copy={rc} lits={r_lits:5} copys={r_copys:5} | ms: copy={mc} lits={m_lits:5} copys={m_copys:5} | tpl_ops={}",
                    tb.ops.len()
                );
            }
        }
        eprintln!("blocks with adaptation differences: {interesting}");

        // After fix: with force_reencode, blocks after 6 should re-encode.
        // Simulate encode_blocks logic and show what happens.
        let mut force = false;
        for i in 0..template_blocks.len() {
            let block = &rust_adapted[i];
            let will_reencode;
            if block.copy_from_template && !force {
                will_reencode = "copy";
            } else {
                force = true;
                will_reencode = "REENC";
            }
            eprintln!(
                "block[{i:2}] {:>5} btype={} bfinal={} copy_flag={} start_bit={} end_bit={} tree_end={}",
                will_reencode,
                block.btype,
                block.bfinal,
                block.copy_from_template,
                block.start_bit,
                block.end_bit,
                block.tree_end_bit
            );
        }

        // Encode both and check round-trip
        let rust_encoded = encode_blocks(deflate, &rust_adapted).expect("encode rust");
        let ms_encoded = encode_blocks(deflate, &ms_adapted).expect("encode ms");

        // Verify flate2 round-trip on both
        let rust_full = {
            let mut v = vec![0x78, 0x9c];
            v.extend(&rust_encoded);
            let a = adler32_zlib(&rust_db);
            v.extend(&a.to_be_bytes());
            v
        };
        let rust_rt = crate::unpack::decompress_zlib(&rust_full).expect("rust rt");
        assert_eq!(rust_rt, rust_db, "rust round-trip FAILED");

        let ms_full = {
            let mut v = vec![0x78, 0x9c];
            v.extend(&ms_encoded);
            let a = adler32_zlib(&ms_db);
            v.extend(&a.to_be_bytes());
            v
        };
        let ms_rt = crate::unpack::decompress_zlib(&ms_full).expect("ms rt");
        assert_eq!(ms_rt, ms_db, "ms round-trip FAILED");

        eprintln!(
            "rust encoded={} ms encoded={}",
            rust_encoded.len(), ms_encoded.len()
        );
    }

    /// Direct test: MS DB + 2 proteam edits (block 6 only) — fdeflate round-trip.
    #[test]
    fn two_edits_in_block6_fdeflate_roundtrip() {
        let Some(t5_zlib) = live_zlib() else { eprintln!("skip"); return; };
        let ms_db_path = std::path::Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../_local/game-saves/xbox/hedman_col.db"
        ));
        let mut ms_db = std::fs::read(ms_db_path).expect("read MS DB");

        // 2 edits in block 6
        ms_db[0x0B949B] = 0x40; // Crosby -> COL
        ms_db[0x0B9837] = 0x40; // Ovechkin -> COL

        let recompressed = compress_zlib_from_template(&ms_db, &t5_zlib).expect("compress");
        eprintln!("template={} recompressed={}", t5_zlib.len(), recompressed.len());

        // flate2 round-trip
        let flate2_rt = crate::unpack::decompress_zlib(&recompressed).expect("flate2 rt");
        assert_eq!(flate2_rt, ms_db, "flate2 round-trip FAILED");
        
        // fdeflate round-trip
        let mut dec = crate::deflate_fdeflate_ops::Decompressor::new();
        let mut out = vec![0u8; 3_000_000];
        match dec.read(&recompressed, &mut out, 0, true) {
            Ok((_, produced)) => {
                let fdef = &out[..produced];
                eprintln!("fdeflate produced={produced} expected={}", ms_db.len());
                if fdef == ms_db.as_slice() {
                    eprintln!("PASS: fdeflate round-trip OK for 2 edits");
                } else {
                    let diffs: Vec<_> = ms_db.iter().zip(fdef.iter()).enumerate()
                        .filter(|(_, (a,b))| a!=b).take(20).collect();
                    eprintln!("FAIL: {} total diffs", ms_db.iter().zip(fdef.iter()).filter(|(a,b)| a!=b).count());
                    for (off, (a,b)) in &diffs {
                        eprintln!("  0x{off:06X}: db=0x{a:02X} fdef=0x{b:02X}");
                    }
                    panic!("fdeflate round-trip FAILED");
                }
            }
            Err(e) => {
                eprintln!("fdeflate DECODE FAILED: {e:?}");
                panic!("fdeflate error on 2 edits");
            }
        }
    }

    /// Re-encode the re-encoded output: can the re-encoder process its own output?
    #[test]
    fn gen2_gen3_fdeflate_roundtrip() {
        let Some(t5_zlib) = live_zlib() else { eprintln!("skip"); return; };
        let ms_db_path = std::path::Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../_local/game-saves/xbox/hedman_col.db"
        ));
        let mut ms_db = std::fs::read(ms_db_path).expect("read MS");
        ms_db[0x0B949B] = 0x40; // Crosby

        // gen1: MS-DB + Crosby -> repack with TRADEEDIT5 (simulates TESTL)
        let gen1 = compress_zlib_from_template(&ms_db, &t5_zlib).expect("gen1");
        let gen1_rt = crate::unpack::decompress_zlib(&gen1).expect("gen1 rt");
        assert_eq!(gen1_rt, ms_db, "gen1 rt");

        // gen2: gen1-DB + Ovechkin -> repack with gen1 as template (simulates SURGICAL/MSTL)
        let mut gen1_db = gen1_rt;
        gen1_db[0x0B9837] = 0x40;
        let gen2 = compress_zlib_from_template(&gen1_db, &gen1).expect("gen2");
        let gen2_rt = crate::unpack::decompress_zlib(&gen2).expect("gen2 rt");
        assert_eq!(gen2_rt, gen1_db, "gen2 rt");

        // fdeflate round-trip gen2
        let mut dec = crate::deflate_fdeflate_ops::Decompressor::new();
        let mut out = vec![0u8; 3_000_000];
        match dec.read(&gen2, &mut out, 0, true) {
            Ok((_, produced)) => {
                let fdef = &out[..produced];
                let total = gen1_db.iter().zip(fdef.iter()).filter(|(a,b)| a!=b).count();
                if total > 0 {
                    eprintln!("FAIL: gen2 fdeflate rt: {total} diffs");
                    let diffs: Vec<_> = gen1_db.iter().zip(fdef.iter()).enumerate()
                        .filter(|(_,(a,b))| a!=b).take(15).collect();
                    for (off,(a,b)) in &diffs {
                        eprintln!("  0x{off:06X}: gen1=0x{a:02X} fdef=0x{b:02X}");
                    }
                    panic!("gen2 fdeflate broken");
                } else {
                    eprintln!("PASS: gen2 fdeflate round-trip OK");
                }
            }
            Err(e) => { eprintln!("gen2 fdeflate DECODE FAILED: {e:?}"); panic!("gen2 fdeflate"); }
        }

        // gen3: gen2-DB + Hedman -> repack with gen2 as template
        let mut gen2_db = gen2_rt;
        gen2_db[0x0CAD1B] = 0x40;
        let gen3 = compress_zlib_from_template(&gen2_db, &gen2).expect("gen3");
        let gen3_rt = crate::unpack::decompress_zlib(&gen3).expect("gen3 rt");
        assert_eq!(gen3_rt, gen2_db, "gen3 rt");

        dec = crate::deflate_fdeflate_ops::Decompressor::new();
        out = vec![0u8; 3_000_000];
        match dec.read(&gen3, &mut out, 0, true) {
            Ok((_, produced)) => {
                let fdef = &out[..produced];
                let total = gen2_db.iter().zip(fdef.iter()).filter(|(a,b)| a!=b).count();
                if total > 0 {
                    eprintln!("FAIL: gen3 fdeflate rt: {total} diffs");
                    panic!("gen3 fdeflate broken");
                } else {
                    eprintln!("PASS: gen3 fdeflate round-trip OK");
                }
            }
            Err(e) => { eprintln!("gen3 fdeflate DECODE FAILED: {e:?}"); panic!("gen3 fdeflate"); }
        }
    }

    /// Show which deflate blocks are re-encoded (copy_from_template=false) for each test DB.
    #[test]
    fn block_reencode_diagnostic() {
        let Some(t5_zlib) = live_zlib() else { eprintln!("skip"); return; };
        let ms_path = std::path::Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"), "/../../_local/game-saves/xbox/hedman_col.db"
        ));
        let ms_db = std::fs::read(ms_path).expect("ms");
        let template_deflate = &t5_zlib[2..t5_zlib.len() - 4];

        let edits: Vec<(&str, Vec<usize>)> = vec![
            ("T0_CLEAN", vec![]),
            ("T1_CRSB", vec![0x0B949B]),
            ("T1_OV", vec![0x0B9837]),
            ("T2_CRSBOV", vec![0x0B949B, 0x0B9837]),
            ("T3_ALL", vec![0x0B949B, 0x0B9837, 0x0CAD1B]),
        ];

        let base_blocks = decode_deflate_blocks(template_deflate).expect("decode");

        // Map DB byte offsets to deflate blocks
        let mut byte_to_block = vec![0usize; ms_db.len() + 1];
        {
            let mut tdb_pos = 0usize;
            for (bi, blk) in base_blocks.iter().enumerate() {
                let len: usize = blk.ops.iter().map(|op| op.output_len()).sum();
                for j in 0..len {
                    if tdb_pos + j < byte_to_block.len() {
                        byte_to_block[tdb_pos + j] = bi;
                    }
                }
                tdb_pos += len;
            }
        }

        for (name, edit_offsets) in &edits {
            let mut db = ms_db.clone();
            for &off in edit_offsets {
                db[off] = 0x40;
            }
            let adapted = adapt_blocks_for_edited(&base_blocks, &db).expect("adapt");
            let reencoded: Vec<usize> = adapted.iter().enumerate()
                .filter(|(_, b)| !b.copy_from_template)
                .map(|(i, _)| i)
                .collect();
            let first_byte_per_block: Vec<usize> = adapted.iter().scan(0usize, |pos, b| {
                let cur = *pos;
                let len: usize = b.ops.iter().map(|op| op.output_len()).sum();
                *pos += len;
                Some(cur)
            }).collect();

            eprintln!("{name}: re-encoded blocks: {reencoded:?}");
            for &bi in &reencoded {
                let start = first_byte_per_block[bi];
                let end = start + adapted[bi].ops.iter().map(|op| op.output_len()).sum::<usize>();
                eprintln!("  block[{bi}] covers DB bytes [0x{start:06X}..0x{end:06X})");
            }

            // Also: is the compressed zlib longer than template?
            let compressed = compress_zlib_from_template(&db, &t5_zlib).expect("compress");
            eprintln!("  zlib length: {} bytes (template: {})", compressed.len(), t5_zlib.len());
            if compressed.len() > t5_zlib.len() {
                eprintln!("  *** ZLIB LONGER THAN TEMPLATE — WILL BE TRUNCATED! ***");
            }
        }

        // Compare T0_CLEAN.zlib vs T1_CRSB.zlib byte by byte (both from disk)
        for (a_label, b_label) in &[("T0_CLEAN", "T1_CRSB"), ("T0_CLEAN", "T1_OV")] {
            let path_a = format!("{}/../../_local/game-saves/xbox/{}.bin",
                env!("CARGO_MANIFEST_DIR"), a_label);
            let path_b = format!("{}/../../_local/game-saves/xbox/{}.bin",
                env!("CARGO_MANIFEST_DIR"), b_label);
            if let (Ok(a), Ok(b)) = (std::fs::read(&path_a), std::fs::read(&path_b)) {
                let z_a = &a[48..];
                let z_b = &b[48..];
                let m = z_a.len().min(z_b.len());
                let total: usize = (0..m).filter(|&i| z_a[i] != z_b[i]).count();
                eprintln!("\n{a_label} vs {b_label}: {total} zlib diffs / {m} bytes");
                let mut shown = 0usize;
                for i in 0..m {
                    if z_a[i] != z_b[i] && shown < 5 {
                        let va = z_a[i];
                        let vb = z_b[i];
                        eprintln!("  zlib[{i:>8}]: {a_label}=0x{va:02X} {b_label}=0x{vb:02X}");
                        shown += 1;
                    }
                }
            }
        }
    }

    /// MSTL scenario: build OV edit with TRADEEDIT5 template (OV_T5) vs with gen1/TESTL
    /// template (MS_TL). Compare both zlibs and full containers.
    #[test]
    fn gen1_vs_t5_template_full_comparison() {
        let Some(t5_zlib) = live_zlib() else { eprintln!("skip"); return; };
        
        let ms_db_path = std::path::Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../_local/game-saves/xbox/hedman_col.db"
        ));
        let mut ms_db = std::fs::read(ms_db_path).expect("read MS");

        // gen1 = MS-DB + Crosby -> TRADEEDIT5 template (TESTL)
        ms_db[0x0B949B] = 0x40;
        let gen1_zlib = compress_zlib_from_template(&ms_db, &t5_zlib).expect("gen1");

        // Compare with testL.bin on disk
        let testl_path = std::path::Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"), "/../../_local/game-saves/xbox/testL.bin"
        ));
        if let Ok(tl_bin) = std::fs::read(testl_path) {
            let tl_zlib = &tl_bin[48..];
            let cmp_len = tl_zlib.len().min(gen1_zlib.len());
            let d: usize = (0..cmp_len).filter(|&i| tl_zlib[i] != gen1_zlib[i]).count();
            eprintln!("testL.bin zlib vs gen1 zlib (MS-DB+Crosby): {d} / {cmp_len} diffs ({} identical)",
                if d == 0 { "MATCH" } else if d < 1000 { "NEAR MATCH" } else { "DIVERGE" });
            if d > 0 && d < 100 {
                for i in 0..cmp_len {
                    if tl_zlib[i] != gen1_zlib[i] {
                        eprintln!("  diff at zlib byte {i}: disk=0x{:02X} gen1=0x{:02X}", tl_zlib[i], gen1_zlib[i]);
                    }
                }
            }
        }

        // Now reset and do Ovechkin edit
        let ms_db = std::fs::read(ms_db_path).expect("read MS");
        let mut ov_db = ms_db.clone();
        ov_db[0x0B9837] = 0x40;

        // B1: Pack OV with TRADEEDIT5 template
        let ov_t5_zlib = compress_zlib_from_template(&ov_db, &t5_zlib).expect("ov_t5");
        
        // B2: Pack OV with gen1/TESTL zlib as template
        let ov_gen1_zlib = compress_zlib_from_template(&ov_db, &gen1_zlib).expect("ov_gen1");

        // Compare B1 vs B2 zlib
        let min_zlib = ov_t5_zlib.len().min(ov_gen1_zlib.len());
        let zlib_diffs: usize = (0..min_zlib).filter(|&i| ov_t5_zlib[i] != ov_gen1_zlib[i]).count();
        eprintln!("\nZLIB diff OV+T5 vs OV+gen1: {zlib_diffs} / {min_zlib}");

        // Verify round-trips
        let b1_rt = crate::unpack::decompress_zlib(&ov_t5_zlib).expect("b1");
        let b2_rt = crate::unpack::decompress_zlib(&ov_gen1_zlib).expect("b2");
        assert_eq!(b1_rt, ov_db, "B1 rt");
        assert_eq!(b2_rt, ov_db, "B2 rt");

        // Compare with actual MS_TL.bin on disk
        let ms_tl_path = std::path::Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"), "/../../_local/game-saves/xbox/MS_TL.bin"
        ));
        if let Ok(ms_tl_bin) = std::fs::read(ms_tl_path) {
            eprintln!("\nComparing with MS_TL.bin on disk:");
            let disk_zlib = &ms_tl_bin[48..];
            
            // Compare with B1
            let d1: usize = (0..min_zlib).filter(|&i| disk_zlib.get(i) != ov_t5_zlib.get(i)).count();
            eprintln!("  MS_TL.bin vs B1(OV+T5): {d1} diffs");
            
            // Compare with B2
            let d2: usize = (0..min_zlib).filter(|&i| disk_zlib.get(i) != ov_gen1_zlib.get(i)).count();
            eprintln!("  MS_TL.bin vs B2(OV+gen1): {d2} diffs");
        }
    }
}

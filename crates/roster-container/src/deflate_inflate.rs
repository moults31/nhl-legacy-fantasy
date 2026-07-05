//! fdeflate-compatible inflate tables for roster save deflate streams.
#![allow(dead_code)]
//!
//! Linear canonical Huffman decode mis-decodes some codewords on live roster saves
//! (early false end-of-block at ~125 KiB). Table-based decode matches fdeflate/libz.

use crate::error::{Error, Result};

const LITERAL_ENTRY: u32 = 0x8000;
const EXCEPTIONAL_ENTRY: u32 = 0x4000;
const SECONDARY_TABLE_ENTRY: u32 = 0x2000;

const LENGTH_BASE: [usize; 29] = [
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115,
    131, 163, 195, 227, 258,
];
const LENGTH_EXTRA: [u8; 29] = [
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0,
];
const DIST_BASE: [u16; 30] = [
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537,
    2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577,
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

fn litlen_table_entries() -> [u32; 288] {
    let mut entries = [EXCEPTIONAL_ENTRY; 288];
    for i in 0..256 {
        entries[i] = (i as u32) << 16 | LITERAL_ENTRY | (1 << 8);
    }
    for i in 257..286 {
        entries[i] = (LENGTH_BASE[i - 257] as u32) << 16 | (LENGTH_EXTRA[i - 257] as u32) << 8;
    }
    entries
}

fn dist_table_entries() -> [u32; 32] {
    let mut entries = [0u32; 32];
    for i in 0..30 {
        entries[i] = (DIST_BASE[i] as u32) << 16 | (DIST_EXTRA[i] as u32) << 8 | LITERAL_ENTRY;
    }
    entries
}

pub(crate) fn build_decode_table(
    lengths: &[u8],
    entries: &[u32],
    codes: &mut [u16],
    primary_table: &mut [u32],
    secondary_table: &mut Vec<u16>,
    is_distance_table: bool,
    double_literal: bool,
) -> bool {
    let mut histogram = [0usize; 16];
    for &length in lengths {
        histogram[length as usize] += 1;
    }

    let mut max_length = 15usize;
    while max_length > 1 && histogram[max_length] == 0 {
        max_length -= 1;
    }

    if is_distance_table {
        if max_length == 0 {
            primary_table.fill(0);
            secondary_table.clear();
            return true;
        }
        if max_length == 1 && histogram[1] == 1 {
            let symbol = lengths.iter().position(|&l| l == 1).unwrap();
            codes[symbol] = 0;
            let entry = entries
                .get(symbol)
                .copied()
                .unwrap_or((symbol as u32) << 16 | 1);
            for chunk in primary_table.chunks_mut(2) {
                chunk[0] = entry;
                if chunk.len() > 1 {
                    chunk[1] = 0;
                }
            }
            return true;
        }
    }

    let mut offsets = [0usize; 16];
    let mut codespace_used = 0usize;
    offsets[1] = histogram[0];
    for i in 1..max_length {
        offsets[i + 1] = offsets[i] + histogram[i];
        codespace_used = (codespace_used << 1) + histogram[i];
    }
    codespace_used = (codespace_used << 1) + histogram[max_length];
    if codespace_used != (1 << max_length) {
        return false;
    }

    let mut next_index = offsets;
    let mut sorted_symbols = vec![0usize; lengths.len()];
    for (symbol, &len) in lengths.iter().enumerate() {
        if len > 0 {
            sorted_symbols[next_index[len as usize]] = symbol;
            next_index[len as usize] += 1;
        }
    }

    let mut codeword = 0u16;
    let mut i = histogram[0];
    let primary_table_bits = primary_table.len().trailing_zeros() as usize;
    let primary_table_mask = (1 << primary_table_bits) - 1;

    for length in 1..=primary_table_bits {
        let current_table_end = 1 << length;
        for _ in 0..histogram[length] {
            let symbol = sorted_symbols[i];
            i += 1;
            let entry = entries
                .get(symbol)
                .copied()
                .unwrap_or((symbol as u32) << 16)
                | length as u32;
            primary_table[codeword as usize] = entry;
            codes[symbol] = codeword;
            codeword = next_codeword(codeword, current_table_end as u16);
        }

        if double_literal {
            for len1 in 1..(length - 1) {
                let len2 = length - len1;
                for sym1_index in offsets[len1]..next_index[len1] {
                    for sym2_index in offsets[len2]..next_index[len2] {
                        let sym1 = sorted_symbols[sym1_index];
                        let sym2 = sorted_symbols[sym2_index];
                        if sym1 < 256 && sym2 < 256 {
                            let codeword1 = codes[sym1];
                            let codeword2 = codes[sym2];
                            let combined = codeword1 | (codeword2 << len1);
                            let entry = (sym1 as u32) << 16
                                | (sym2 as u32) << 24
                                | LITERAL_ENTRY
                                | (2 << 8)
                                | length as u32;
                            primary_table[combined as usize] = entry;
                        }
                    }
                }
            }
        }

        if length < primary_table_bits {
            primary_table.copy_within(0..current_table_end, current_table_end);
        }
    }

    secondary_table.clear();
    if max_length > primary_table_bits {
        let mut subtable_start = 0usize;
        let mut subtable_prefix = !0u16;
        for length in (primary_table_bits + 1)..=max_length {
            let subtable_size = 1 << (length - primary_table_bits);
            for _ in 0..histogram[length] {
                if codeword & primary_table_mask != subtable_prefix {
                    subtable_prefix = codeword & primary_table_mask;
                    subtable_start = secondary_table.len();
                    primary_table[subtable_prefix as usize] = ((subtable_start as u32) << 16)
                        | EXCEPTIONAL_ENTRY
                        | SECONDARY_TABLE_ENTRY
                        | (subtable_size as u32 - 1);
                    secondary_table.resize(subtable_start + subtable_size, 0);
                }
                let symbol = sorted_symbols[i];
                i += 1;
                codes[symbol] = codeword;
                secondary_table[subtable_start + (codeword >> primary_table_bits) as usize] =
                    ((symbol as u16) << 4) | (length as u16);
                codeword = next_codeword(codeword, 1 << length);
            }
            if length < max_length && codeword & primary_table_mask == subtable_prefix {
                secondary_table.extend_from_within(subtable_start..);
                let subtable_size = secondary_table.len() - subtable_start;
                primary_table[subtable_prefix as usize] = ((subtable_start as u32) << 16)
                    | EXCEPTIONAL_ENTRY
                    | SECONDARY_TABLE_ENTRY
                    | (subtable_size as u32 - 1);
            }
        }
    }
    true
}

#[derive(Debug, Clone)]
pub struct InflateTables {
    pub litlen_table: [u32; 4096],
    pub litlen_secondary: Vec<u16>,
    pub dist_table: [u32; 512],
    pub dist_secondary: Vec<u16>,
    pub eof_code: u16,
    pub eof_mask: u16,
    pub eof_bits: u8,
}

pub fn build_inflate_tables(lit_lengths: &[u8], dist_lengths: &[u8]) -> Result<InflateTables> {
    let lit_entries = litlen_table_entries();
    let dist_entries = dist_table_entries();
    let mut lit_codes = vec![0u16; lit_lengths.len()];
    let mut litlen_table = [0u32; 4096];
    let mut litlen_secondary = Vec::new();
    if !build_decode_table(
        lit_lengths,
        &lit_entries,
        &mut lit_codes,
        &mut litlen_table,
        &mut litlen_secondary,
        false,
        true,
    ) {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "bad literal/length huffman tree",
        )));
    }

    let mut dist_table = [0u32; 512];
    let mut dist_secondary = Vec::new();
    if dist_lengths.iter().all(|&l| l == 0) {
        dist_table.fill(0);
    } else {
        let mut dist_codes = vec![0u16; dist_lengths.len()];
        if !build_decode_table(
            dist_lengths,
            &dist_entries,
            &mut dist_codes,
            &mut dist_table,
            &mut dist_secondary,
            true,
            false,
        ) {
            return Err(Error::Decompress(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "bad distance huffman tree",
            )));
        }
    }

    Ok(InflateTables {
        litlen_table,
        litlen_secondary,
        dist_table,
        dist_secondary,
        eof_code: lit_codes[256],
        eof_mask: (1u16 << lit_lengths[256]) - 1,
        eof_bits: lit_lengths[256],
    })
}

pub struct BitReader<'a> {
    pub data: &'a [u8],
    remaining: &'a [u8],
    pub buffer: u64,
    pub nbits: u8,
    bits_consumed: usize,
}

impl<'a> BitReader<'a> {
    pub fn new(data: &'a [u8]) -> Self {
        Self {
            data,
            remaining: data,
            buffer: 0,
            nbits: 0,
            bits_consumed: 0,
        }
    }

    pub fn from_state(data: &'a [u8], pos: usize, buffer: u64, nbits: u8, bits_consumed: usize) -> Self {
        Self {
            data,
            remaining: &data[pos..],
            buffer,
            nbits,
            bits_consumed,
        }
    }

    pub fn pos(&self) -> usize {
        self.data.len() - self.remaining.len()
    }

    pub fn bits_consumed(&self) -> usize {
        self.bits_consumed
    }

    pub fn remaining_len(&self) -> usize {
        self.remaining.len()
    }

    pub fn buffer(&self) -> u64 {
        self.buffer
    }

    pub fn nbits(&self) -> u8 {
        self.nbits
    }

    /// fdeflate-compatible refill (see fdeflate 0.3.7 decompress.rs).
    pub fn fill_buffer(&mut self) {
        if self.remaining.len() >= 8 {
            self.buffer |= u64::from_le_bytes(self.remaining[..8].try_into().unwrap()) << self.nbits;
            let advance = (63 - self.nbits as usize) / 8;
            self.remaining = &self.remaining[advance..];
            self.nbits |= 56;
        } else {
            let nbytes = self
                .remaining
                .len()
                .min((63 - self.nbits as usize) / 8);
            let mut input_data = [0u8; 8];
            input_data[..nbytes].copy_from_slice(&self.remaining[..nbytes]);
            self.buffer |= u64::from_le_bytes(input_data)
                .checked_shl(self.nbits as u32)
                .unwrap_or(0);
            self.nbits += nbytes as u8 * 8;
            self.remaining = &self.remaining[nbytes..];
        }
    }

    pub fn peak_bits(&self, nbits: u8) -> u64 {
        self.buffer & ((1u64 << nbits) - 1)
    }

    pub fn consume_bits(&mut self, nbits: u8) {
        self.buffer >>= nbits;
        self.nbits -= nbits;
        self.bits_consumed += nbits as usize;
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum InflateOp {
    Literal(u8),
    Copy { length: u32, distance: u32 },
    EndBlock,
}

pub fn decode_block_ops(br: &mut BitReader<'_>, tables: &InflateTables) -> Result<Vec<InflateOp>> {
    crate::deflate_fdeflate_decode::decode_block_ops(br, tables)
}

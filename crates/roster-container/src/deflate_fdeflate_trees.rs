//! Vendored from fdeflate 0.3.7 `read_code_length_codes` + `read_code_lengths` + `build_tables`.
#![allow(dead_code)]
//!
//! Linear canonical Huffman decode for CLCL symbols mis-reads some code lengths on live roster
//! saves, producing inflate tables that false-trigger end-of-block at ~125 KiB.

use crate::deflate_inflate::{self, BitReader, InflateTables};
use crate::error::{Error, Result};

const CLCL_ORDER: [usize; 19] =
    [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];

/// Parse a dynamic deflate block's Huffman trees using fdeflate-compatible bit I/O.
pub fn read_dynamic_trees(
    br: &mut BitReader<'_>,
) -> Result<(Vec<u8>, Vec<u8>, InflateTables)> {
    br.fill_buffer();
    if br.nbits() < 17 {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::UnexpectedEof,
            "truncated dynamic block header",
        )));
    }

    let btype = br.peak_bits(3) >> 1;
    if btype != 2 {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            format!("expected dynamic block, got btype={btype}"),
        )));
    }

    let hlit = (br.peak_bits(8) >> 3) as usize + 257;
    let hdist = (br.peak_bits(13) >> 8) as usize + 1;
    let hclen = (br.peak_bits(17) >> 13) as usize + 4;
    if hlit > 286 {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "invalid hlit",
        )));
    }
    if hdist > 30 {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "invalid hdist",
        )));
    }
    br.consume_bits(17);

    // read_code_length_codes
    let mut code_length_lengths = [0u8; 19];
    for i in 0..hclen {
        br.fill_buffer();
        code_length_lengths[CLCL_ORDER[i]] = br.peak_bits(3) as u8;
        br.consume_bits(3);
        if i == 17 {
            br.fill_buffer();
        }
    }

    let mut cl_codes = [0u16; 19];
    let mut cl_table = [0u32; 128];
    let mut cl_secondary = Vec::new();
    if !deflate_inflate::build_decode_table(
        &code_length_lengths,
        &[],
        &mut cl_codes,
        &mut cl_table,
        &mut cl_secondary,
        false,
        false,
    ) {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "bad code-length huffman tree",
        )));
    }

    // read_code_lengths
    let total_lengths = hlit + hdist;
    let mut code_lengths = [0u8; 320];
    let mut num_lengths_read = 0usize;

    while num_lengths_read < total_lengths {
        br.fill_buffer();
        if br.nbits() < 7 {
            return Err(Error::Decompress(std::io::Error::new(
                std::io::ErrorKind::UnexpectedEof,
                "truncated code length stream",
            )));
        }

        let code = br.peak_bits(7);
        let entry = cl_table[code as usize];
        let length = (entry & 0x7) as u8;
        let symbol = (entry >> 16) as u8;

        debug_assert!(length != 0);
        match symbol {
            0..=15 => {
                code_lengths[num_lengths_read] = symbol;
                num_lengths_read += 1;
                br.consume_bits(length);
            }
            16..=18 => {
                let (base_repeat, extra_bits) = match symbol {
                    16 => (3, 2),
                    17 => (3, 3),
                    18 => (11, 7),
                    _ => unreachable!(),
                };

                if br.nbits() < length + extra_bits {
                    return Err(Error::Decompress(std::io::Error::new(
                        std::io::ErrorKind::UnexpectedEof,
                        "truncated code length repeat",
                    )));
                }

                let value = match symbol {
                    16 => code_lengths[num_lengths_read
                        .checked_sub(1)
                        .ok_or_else(|| {
                            Error::Decompress(std::io::Error::new(
                                std::io::ErrorKind::InvalidData,
                                "invalid code length repeat",
                            ))
                        })?],
                    17 => 0,
                    18 => 0,
                    _ => unreachable!(),
                };

                let repeat =
                    (br.peak_bits(length + extra_bits) >> length) as usize + base_repeat;
                if num_lengths_read + repeat > total_lengths {
                    return Err(Error::Decompress(std::io::Error::new(
                        std::io::ErrorKind::InvalidData,
                        "code length repeat overflow",
                    )));
                }

                for i in 0..repeat {
                    code_lengths[num_lengths_read + i] = value;
                }
                num_lengths_read += repeat;
                br.consume_bits(length + extra_bits);
            }
            _ => unreachable!(),
        }
    }

    code_lengths.copy_within(hlit..total_lengths, 288);
    for i in hlit..288 {
        code_lengths[i] = 0;
    }
    for i in 288 + hdist..320 {
        code_lengths[i] = 0;
    }

    if code_lengths[256] == 0 {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "missing end-of-block code",
        )));
    }

    let lit_lengths = code_lengths[..hlit].to_vec();
    let mut dist_lengths = [0u8; 32];
    dist_lengths[..hdist].copy_from_slice(&code_lengths[288..288 + hdist]);

    let inflate = deflate_inflate::build_inflate_tables(&lit_lengths, &dist_lengths)?;
    Ok((lit_lengths, dist_lengths.to_vec(), inflate))
}

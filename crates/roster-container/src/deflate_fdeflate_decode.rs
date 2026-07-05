//! Vendored from fdeflate 0.3.7 `read_compressed` — emits LZ ops with identical bit consumption.
#![allow(dead_code)]

use crate::deflate_inflate::{BitReader, InflateOp, InflateTables};
use crate::error::{Error, Result};

const LITERAL_ENTRY: u32 = 0x8000;
const EXCEPTIONAL_ENTRY: u32 = 0x4000;
const SECONDARY_TABLE_ENTRY: u32 = 0x2000;

const LEN_SYM_TO_LEN_BASE: [usize; 29] = [
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115,
    131, 163, 195, 227, 258,
];
const LEN_SYM_TO_LEN_EXTRA: [u8; 29] = [
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0,
];
const DIST_SYM_TO_DIST_BASE: [u16; 30] = [
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537,
    2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577,
];
const DIST_SYM_TO_DIST_EXTRA: [u8; 30] = [
    0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12,
    13, 13,
];

pub fn decode_block_ops(br: &mut BitReader<'_>, tables: &InflateTables) -> Result<Vec<InflateOp>> {
    let mut ops = Vec::new();
    let mut output = vec![0u8; 3_000_000];
    let mut output_index = 0usize;
    let mut queued_rle: Option<(u8, usize)> = None;
    let mut queued_backref: Option<(usize, usize)> = None;
    let mut block_done = false;

    if let Some((data, len)) = queued_rle.take() {
        for _ in 0..len {
            output.push(data);
            ops.push(InflateOp::Literal(data));
            output_index += 1;
        }
    }
    if let Some((dist, len)) = queued_backref.take() {
        emit_copy(&mut output, &mut ops, &mut output_index, dist, len)?;
    }

    br.fill_buffer();

    // Careful decoding loop (fdeflate read_compressed slow path only).
    while !block_done {
        br.fill_buffer();

        let mut bits = br.buffer();
        let litlen_entry = tables.litlen_table[(bits & 0xfff) as usize];
        let litlen_code_bits = litlen_entry as u8;

        if litlen_entry & LITERAL_ENTRY != 0 {
            let advance_output_bytes = ((litlen_entry & 0xf00) >> 8) as usize;
            if br.nbits() < litlen_code_bits {
                break;
            }
            ensure_output(&mut output, output_index + 2);
            output[output_index] = (litlen_entry >> 16) as u8;
            output[output_index + 1] = (litlen_entry >> 24) as u8;
            push_literals(
                &mut ops,
                (litlen_entry >> 16) as u8,
                if advance_output_bytes >= 2 {
                    Some((litlen_entry >> 24) as u8)
                } else {
                    None
                },
            );
            output_index += advance_output_bytes;
            br.consume_bits(litlen_code_bits);
            continue;
        }

        let (length_base, length_extra_bits, litlen_code_bits) =
            if litlen_entry & EXCEPTIONAL_ENTRY == 0 {
                (
                    litlen_entry >> 16,
                    (litlen_entry >> 8) as u8,
                    litlen_code_bits,
                )
            } else if litlen_entry & SECONDARY_TABLE_ENTRY != 0 {
                let secondary_table_index =
                    (litlen_entry >> 16) + ((bits >> 12) as u32 & (litlen_entry & 0xff));
                let secondary_entry = tables.litlen_secondary[secondary_table_index as usize];
                let litlen_symbol = secondary_entry >> 4;
                let litlen_code_bits = (secondary_entry & 0xf) as u8;

                if br.nbits() < litlen_code_bits {
                    break;
                } else if litlen_symbol < 256 {
                    br.consume_bits(litlen_code_bits);
                    ensure_output(&mut output, output_index + 1);
                    output[output_index] = litlen_symbol as u8;
                    ops.push(InflateOp::Literal(litlen_symbol as u8));
                    output_index += 1;
                    continue;
                } else if litlen_symbol == 256 {
                    br.consume_bits(litlen_code_bits);
                    block_done = true;
                    break;
                }

                (
                    LEN_SYM_TO_LEN_BASE[(litlen_symbol - 257) as usize] as u32,
                    LEN_SYM_TO_LEN_EXTRA[(litlen_symbol - 257) as usize],
                    litlen_code_bits,
                )
            } else if litlen_code_bits == 0 {
                return Err(Error::Decompress(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    "invalid litlen code",
                )));
            } else {
                if br.nbits() < litlen_code_bits {
                    break;
                }
                br.consume_bits(litlen_code_bits);
                block_done = true;
                break;
            };
        bits >>= litlen_code_bits;

        let length_extra_mask = (1u64 << length_extra_bits) - 1;
        let length = length_base as usize + (bits & length_extra_mask) as usize;
        bits >>= length_extra_bits;

        let dist_entry = tables.dist_table[(bits & 0x1ff) as usize];
        let (dist_base, dist_extra_bits, dist_code_bits) = if dist_entry & LITERAL_ENTRY != 0 {
            (
                (dist_entry >> 16) as u16,
                (dist_entry >> 8) as u8 & 0xf,
                dist_entry as u8,
            )
        } else if br.nbits() > litlen_code_bits + length_extra_bits + 9 {
            if dist_entry >> 8 == 0 {
                return Err(Error::Decompress(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    "invalid distance code",
                )));
            }
            let secondary_table_index =
                (dist_entry >> 16) + ((bits >> 9) as u32 & (dist_entry & 0xff));
            let secondary_entry = tables.dist_secondary[secondary_table_index as usize];
            let dist_symbol = (secondary_entry >> 4) as usize;
            if dist_symbol >= 30 {
                return Err(Error::Decompress(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    "invalid distance symbol",
                )));
            }
            (
                DIST_SYM_TO_DIST_BASE[dist_symbol],
                DIST_SYM_TO_DIST_EXTRA[dist_symbol],
                (secondary_entry & 0xf) as u8,
            )
        } else {
            break;
        };
        bits >>= dist_code_bits;

        let dist = dist_base as usize + (bits & ((1u64 << dist_extra_bits) - 1)) as usize;
        let total_bits =
            litlen_code_bits + length_extra_bits + dist_code_bits + dist_extra_bits;

        if br.nbits() < total_bits {
            break;
        } else if dist > output_index {
            return Err(Error::Decompress(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "distance too far back",
            )));
        }

        br.consume_bits(total_bits);

        let copy_length = length;
        if dist == 1 {
            let last = output[output_index - 1];
            ensure_output(&mut output, output_index + copy_length);
            output[output_index..output_index + copy_length].fill(last);
            ops.push(InflateOp::Copy {
                length: copy_length as u32,
                distance: 1,
            });
        } else if output_index + length + 15 <= output.len() {
            let start = output_index - dist;
            ensure_output(&mut output, output_index + length + 16);
            output.copy_within(start..start + 16, output_index);
            if length > 16 || dist < 16 {
                for i in (0..length).step_by(dist.min(16)).skip(1) {
                    output.copy_within(start + i..start + i + 16, output_index + i);
                }
            }
            ops.push(InflateOp::Copy {
                length: length as u32,
                distance: dist as u32,
            });
        } else {
            ensure_output(&mut output, output_index + copy_length);
            if dist < copy_length {
                for i in 0..copy_length {
                    output[output_index + i] = output[output_index + i - dist];
                }
            } else {
                output.copy_within(
                    output_index - dist..output_index + copy_length - dist,
                    output_index,
                );
            }
            ops.push(InflateOp::Copy {
                length: copy_length as u32,
                distance: dist as u32,
            });
        }
        output_index += copy_length;
    }

    if !block_done
        && br.nbits() >= 15
        && (br.peak_bits(15) as u16) & tables.eof_mask == tables.eof_code
    {
        br.consume_bits(tables.eof_bits);
        block_done = true;
    }

    if block_done {
        ops.push(InflateOp::EndBlock);
        Ok(ops)
    } else {
        Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            format!(
                "block ended without end-of-block symbol at out={output_index} bits={}",
                br.bits_consumed()
            ),
        )))
    }
}

fn ensure_output(output: &mut Vec<u8>, need: usize) {
    if output.len() < need {
        output.resize(need, 0);
    }
}

fn push_literals(ops: &mut Vec<InflateOp>, b0: u8, b1: Option<u8>) {
    ops.push(InflateOp::Literal(b0));
    if let Some(b1) = b1 {
        ops.push(InflateOp::Literal(b1));
    }
}

fn emit_copy(
    output: &mut Vec<u8>,
    ops: &mut Vec<InflateOp>,
    output_index: &mut usize,
    dist: usize,
    len: usize,
) -> Result<()> {
    if dist > *output_index {
        return Err(Error::Decompress(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "distance too far back",
        )));
    }
    ensure_output(output, *output_index + len);
    let start = *output_index - dist;
    for i in 0..len {
        output[*output_index + i] = output[start + (i % dist)];
    }
    ops.push(InflateOp::Copy {
        length: len as u32,
        distance: dist as u32,
    });
    *output_index += len;
    Ok(())
}

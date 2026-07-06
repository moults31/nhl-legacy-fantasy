//! Build a packed roster save from raw TDB bytes.

use crate::container_checksum;
use crate::error::{Error, Result};
use crate::format::{Platform, RosterHeader, XBOX360_HEADER_SIZE};
use crate::unpack::{decompress_zlib, validate_tdb_magic};

use flate2::write::ZlibEncoder;
use flate2::Compression;
use std::io::Write as _;

// ── public API ──

/// Pack TDB bytes into a roster save container.
///
/// Uses standard flate2 zlib compression with zero-padding to match the
/// template's zlib payload length. This is the canonical pack path used
/// by the move-player pipeline.
pub fn pack(db: &[u8], template: &[u8], field_0x2c: u32) -> Result<Vec<u8>> {
    validate_tdb_magic(db)?;
    let header = RosterHeader::parse(template)?;

    if header.platform != Platform::Xbox360 {
        return Err(Error::UnsupportedPlatform("only Xbox 360 RosterFile pack is implemented"));
    }

    let template_db = decompress_zlib(&template[header.payload_offset..])?;
    if template_db == db {
        return Ok(template.to_vec());
    }

    let template_zlib_len = template.len() - header.payload_offset;
    let mut compressed_zlib = Vec::new();
    {
        let mut enc = ZlibEncoder::new(&mut compressed_zlib, Compression::default());
        enc.write_all(db).map_err(Error::Decompress)?;
        enc.finish().map_err(Error::Decompress)?;
    }

    // Pad with zeros to match the template's zlib payload length.
    // The game ignores the Adler-32 (live saves ship with 0x00000000)
    // and inflate() stops at the deflate end-of-stream marker.
    while compressed_zlib.len() < template_zlib_len {
        compressed_zlib.push(0);
    }
    compressed_zlib.truncate(template_zlib_len);

    build_output(&header, db.len() as u32, field_0x2c, &template, &compressed_zlib)
}

/// Pack using stored deflate blocks (no Huffman), ignoring the template's
/// deflate structure. Slower decompression but works with any inflater.
pub fn pack_stored(db: &[u8], template: &[u8]) -> Result<Vec<u8>> {
    validate_tdb_magic(db)?;
    let header = RosterHeader::parse(template)?;

    if header.platform != Platform::Xbox360 {
        return Err(Error::UnsupportedPlatform("only Xbox 360 RosterFile pack is implemented"));
    }

    let template_db = decompress_zlib(&template[header.payload_offset..])?;
    if template_db == db {
        return Ok(template.to_vec());
    }

    let compressed = compress_zlib_stored_blocks(db);
    build_output(&header, db.len() as u32, header.field_0x2c, &template, &compressed)
}

/// Pack when the caller accepts reusing the template verbatim for unchanged DBs only.
pub fn pack_unchanged(db: &[u8], template: &[u8]) -> Result<Vec<u8>> {
    validate_tdb_magic(db)?;
    let header = RosterHeader::parse(template)?;
    let template_db = decompress_zlib(&template[header.payload_offset..])?;
    if template_db == db {
        Ok(template.to_vec())
    } else {
        Err(Error::ChecksumUnknown)
    }
}

// ── helpers ──

fn build_output(
    header: &RosterHeader,
    db_len: u32,
    field_0x2c: u32,
    template: &[u8],
    compressed: &[u8],
) -> Result<Vec<u8>> {
    let mut out = Vec::with_capacity(XBOX360_HEADER_SIZE + compressed.len());
    out.extend_from_slice(&template[..XBOX360_HEADER_SIZE]);

    write_u32_be(&mut out, 0x10, 0);
    write_u32_be(&mut out, 0x14, header.field_0x14);
    write_u32_be(&mut out, 0x18, header.field_0x18);
    write_u32_be(&mut out, 0x1c, header.field_0x1c);
    write_u32_be(&mut out, 0x20, header.field_0x20);
    write_u32_be(&mut out, 0x24, db_len);
    write_u32_be(&mut out, 0x28, 0);
    write_u32_be(&mut out, 0x2c, field_0x2c);

    debug_assert_eq!(out.len(), XBOX360_HEADER_SIZE);
    out.extend_from_slice(compressed);

    container_checksum::seal(&mut out)?;
    Ok(out)
}

fn write_u32_be(buf: &mut Vec<u8>, offset: usize, value: u32) {
    let bytes = value.to_be_bytes();
    buf[offset..offset + 4].copy_from_slice(&bytes);
}

/// Zlib stream: 78 9c + stored deflate blocks + Adler-32 (BE).
pub fn compress_zlib_stored_blocks(data: &[u8]) -> Vec<u8> {
    let chunk_count = data.len().div_ceil(65_535);
    let mut out = Vec::with_capacity(6 + data.len() + chunk_count * 5);
    out.extend_from_slice(&[0x78, 0x9c]);

    let mut pos = 0;
    while pos < data.len() {
        let end = (pos + 65_535).min(data.len());
        let chunk = &data[pos..end];
        pos = end;
        let is_final = pos >= data.len();
        out.push(u8::from(is_final));
        let len = chunk.len() as u16;
        out.extend_from_slice(&len.to_le_bytes());
        out.extend_from_slice(&(!len).to_le_bytes());
        out.extend_from_slice(chunk);
    }

    out.extend_from_slice(&adler32_zlib(data).to_be_bytes());
    out
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
    use crate::unpack::unpack;

    const FIXTURE: &str = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../tests/fixtures/xbox/roster.bin"
    );

    #[test]
    fn unchanged_round_trip_is_byte_identical() {
        let template = std::fs::read(FIXTURE).expect("fixture");
        let db = unpack(&template).expect("unpack");
        let repacked = pack_unchanged(&db, &template).expect("pack unchanged");
        assert_eq!(repacked, template);
    }

    #[test]
    fn pack_modified_db_seals_container_checksums() {
        let template = std::fs::read(FIXTURE).expect("fixture");
        let mut db = unpack(&template).expect("unpack");
        let header = RosterHeader::parse(&template).expect("parse header");
        if db.is_empty() {
            panic!("empty db");
        }
        db[100] ^= 0x01;
        let packed = pack(&db, &template, header.field_0x2c).expect("pack edited db");
        crate::container_checksum::verify(&packed).expect("sealed checksums verify");
    }
}

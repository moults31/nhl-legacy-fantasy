use flate2::write::ZlibEncoder;
use flate2::Compression;
use std::io::Write;

use crate::container_checksum;
use crate::error::{Error, Result};
use crate::format::{Platform, RosterHeader, XBOX360_HEADER_SIZE};
use crate::unpack::{decompress_zlib, validate_tdb_magic};

/// Rebuild a roster save from TDB bytes, using `template` for header fields and — when
/// the DB is unchanged — the original compressed payload and checksum.
pub fn pack(db: &[u8], template: &[u8]) -> Result<Vec<u8>> {
    validate_tdb_magic(db)?;
    let header = RosterHeader::parse(template)?;

    if header.platform != Platform::Xbox360 {
        return Err(Error::UnsupportedPlatform(
            "only Xbox 360 RosterFile pack is implemented",
        ));
    }

    let template_db = decompress_zlib(&template[header.payload_offset..])?;
    if template_db == db {
        return Ok(template.to_vec());
    }

    let compressed = compress_zlib(db)?;
    let mut out = Vec::with_capacity(XBOX360_HEADER_SIZE + compressed.len());
    out.extend_from_slice(&template[..XBOX360_HEADER_SIZE]);

    write_u32_be(&mut out, 0x10, 0);
    write_u32_be(&mut out, 0x14, header.field_0x14);
    write_u32_be(&mut out, 0x18, header.field_0x18);
    write_u32_be(&mut out, 0x1c, header.field_0x1c);
    write_u32_be(&mut out, 0x20, header.field_0x20);
    write_u32_be(&mut out, 0x24, db.len() as u32);
    write_u32_be(&mut out, 0x28, 0);
    write_u32_be(&mut out, 0x2c, header.field_0x2c);

    debug_assert_eq!(out.len(), XBOX360_HEADER_SIZE);
    out.extend_from_slice(&compressed);

    container_checksum::seal(&mut out)?;
    Ok(out)
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

fn compress_zlib(data: &[u8]) -> Result<Vec<u8>> {
    // Legacy lists/loads saves with standard zlib (`78 9c`). `Compression::new(0)` emits a
    // non-standard wrapper (`08 1d`) that fails our unpack and does not appear in-game.
    let mut encoder = ZlibEncoder::new(Vec::new(), Compression::default());
    encoder
        .write_all(data)
        .map_err(Error::Compress)?;
    encoder.finish().map_err(Error::Compress)
}

/// Like [`pack`], but supplies `@0x2c` explicitly for edited payloads.
///
/// When the TDB changes, `@0x2c` upper bits are content-dependent (roster1 vs
/// testroster differ even at the same compressed size). Until the algorithm is
/// reversed, pass the value from a reference save with matching roster content.
pub fn pack_with_field_0x2c(db: &[u8], template: &[u8], field_0x2c: u32) -> Result<Vec<u8>> {
    validate_tdb_magic(db)?;
    let header = RosterHeader::parse(template)?;

    if header.platform != Platform::Xbox360 {
        return Err(Error::UnsupportedPlatform(
            "only Xbox 360 RosterFile pack is implemented",
        ));
    }

    let template_db = decompress_zlib(&template[header.payload_offset..])?;
    if template_db == db {
        return Ok(template.to_vec());
    }

    let compressed = compress_zlib(db)?;
    let mut out = Vec::with_capacity(XBOX360_HEADER_SIZE + compressed.len());
    out.extend_from_slice(&template[..XBOX360_HEADER_SIZE]);

    write_u32_be(&mut out, 0x10, 0);
    write_u32_be(&mut out, 0x14, header.field_0x14);
    write_u32_be(&mut out, 0x18, header.field_0x18);
    write_u32_be(&mut out, 0x1c, header.field_0x1c);
    write_u32_be(&mut out, 0x20, header.field_0x20);
    write_u32_be(&mut out, 0x24, db.len() as u32);
    write_u32_be(&mut out, 0x28, 0);
    write_u32_be(&mut out, 0x2c, field_0x2c);

    debug_assert_eq!(out.len(), XBOX360_HEADER_SIZE);
    out.extend_from_slice(&compressed);

    container_checksum::seal(&mut out)?;
    Ok(out)
}

fn write_u32_be(buf: &mut Vec<u8>, offset: usize, value: u32) {
    let bytes = value.to_be_bytes();
    buf[offset..offset + 4].copy_from_slice(&bytes);
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
        if db.is_empty() {
            panic!("empty db");
        }
        db[100] ^= 0x01;
        let packed = pack(&db, &template).expect("pack edited db");
        crate::container_checksum::verify(&packed).expect("sealed checksums verify");
    }

    #[test]
    fn compress_edited_db_uses_standard_zlib_magic() {
        let db_path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../_local/game-saves/xbox/m5-staging/testroster.db"
        );
        if !std::path::Path::new(db_path).exists() {
            eprintln!("skip: no testroster.db");
            return;
        }
        let db = std::fs::read(db_path).expect("db");
        let compressed = compress_zlib(&db).expect("compress");
        assert_eq!(
            &compressed[..2],
            crate::format::ZLIB_MAGIC,
            "game requires zlib header 78 9c, got {:02x}{:02x}",
            compressed[0],
            compressed[1]
        );
        // Game saves are ~1:1; default flate2 is ~800 KB and may fail load (M5ANA01).
        // Listing requires valid `78 9c` first — see M5MCT01 install notes.
        assert!(compressed.len() > 100_000, "compressed payload too small");
    }
}

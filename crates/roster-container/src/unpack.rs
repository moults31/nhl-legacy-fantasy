use flate2::read::ZlibDecoder;
use std::io::Read;

use crate::error::{Error, Result};
use crate::format::{Platform, RosterHeader, PS3_MAGIC, XBOX360_MAGIC};

const TDB_MAGIC: [u8; 2] = *b"DB";

/// Detect the roster container platform from file magic.
pub fn detect_platform(data: &[u8]) -> Result<Platform> {
    if data.starts_with(XBOX360_MAGIC) {
        return Ok(Platform::Xbox360);
    }
    if data.starts_with(PS3_MAGIC) {
        return Ok(Platform::Ps3);
    }
    Err(Error::UnknownMagic)
}

/// Unpack a roster save into raw `default.db` bytes.
pub fn unpack(data: &[u8]) -> Result<Vec<u8>> {
    unpack_with_header(data).map(|(db, _)| db)
}

/// Unpack a roster save, returning both the TDB payload and parsed header metadata.
pub fn unpack_with_header(data: &[u8]) -> Result<(Vec<u8>, RosterHeader)> {
    let header = RosterHeader::parse(data)?;
    let compressed = &data[header.payload_offset..];
    let db = decompress_zlib(compressed)?;
    validate_tdb_magic(&db)?;
    Ok((db, header))
}

fn decompress_zlib(compressed: &[u8]) -> Result<Vec<u8>> {
    let mut decoder = ZlibDecoder::new(compressed);
    let mut out = Vec::new();
    decoder.read_to_end(&mut out)?;
    Ok(out)
}

fn validate_tdb_magic(db: &[u8]) -> Result<()> {
    if db.len() < 4 || db[0..2] != TDB_MAGIC {
        let found: [u8; 4] = db
            .get(0..4)
            .and_then(|slice| slice.try_into().ok())
            .unwrap_or([0; 4]);
        return Err(Error::InvalidTdbMagic { found });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use sha2::{Digest, Sha256};

    const FIXTURE: &str = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../tests/fixtures/xbox/roster.bin"
    );

    const GOLDEN_SHA256: &str =
        "d30aef689fde153605470eaaf12f5e2d781028d8c7b934c3adc99f1463aa49d1";

    fn load_fixture() -> Vec<u8> {
        std::fs::read(FIXTURE).expect("copy tests/fixtures/xbox/roster.bin per tests/fixtures/README.md")
    }

    #[test]
    fn detect_xbox_platform() {
        let data = load_fixture();
        assert_eq!(detect_platform(&data).unwrap(), Platform::Xbox360);
    }

    #[test]
    fn unpack_produces_valid_tdb() {
        let data = load_fixture();
        let db = unpack(&data).expect("unpack");
        assert!(db.len() > 2_000_000);
        assert_eq!(&db[0..2], b"DB");
    }

    #[test]
    fn unpack_matches_golden_sha256() {
        let data = load_fixture();
        let db = unpack(&data).expect("unpack");
        let digest = Sha256::digest(&db);
        assert_eq!(format!("{digest:x}"), GOLDEN_SHA256);
    }

    #[test]
    fn header_fields_match_observed_layout() {
        let data = load_fixture();
        let (db, header) = unpack_with_header(&data).expect("unpack");
        assert_eq!(header.platform, Platform::Xbox360);
        assert_eq!(header.payload_offset, 48);
        assert_eq!(header.uncompressed_size as usize, db.len());
        assert_eq!(header.field_0x14, 4);
        assert_eq!(header.field_0x1c, 1);
        assert_eq!(header.field_0x20, 2);
    }
}

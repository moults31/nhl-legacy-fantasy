use crate::error::{Error, Result};

/// Observed magic for NHL Legacy / NHL 14-era roster TDB payloads.
pub const TDB_MAGIC: [u8; 4] = *b"DB\0\x08";

/// Minimum bytes required to read the fixed header.
pub const HEADER_SIZE: usize = 0x14;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Endian {
    Little,
    Big,
}

/// Parsed fixed TDB header (directory and tables follow).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TdbHeader {
    pub endian: Endian,
    /// Big-endian u32 at offset 0x08 (`source_size` in tdb-core terminology).
    pub source_size: u32,
    /// Big-endian u32 at offset 0x0C (reserved / flags; observed zero).
    pub reserved: u32,
    /// Big-endian u32 at offset 0x10 (table count on live Legacy saves).
    pub table_count: u32,
}

impl TdbHeader {
    pub fn parse(data: &[u8]) -> Result<Self> {
        if data.len() < HEADER_SIZE {
            return Err(Error::TooSmall { len: data.len() });
        }

        let magic: [u8; 4] = data[0..4].try_into().expect("slice length");
        if magic != TDB_MAGIC {
            return Err(Error::InvalidMagic { found: magic });
        }

        let endian_marker = u32::from_le_bytes(data[4..8].try_into().expect("slice length"));
        let endian = match endian_marker {
            1 => Endian::Little,
            0 => Endian::Big,
            marker => return Err(Error::UnsupportedEndian { marker }),
        };

        Ok(TdbHeader {
            endian,
            source_size: read_u32_be(data, 0x08),
            reserved: read_u32_be(data, 0x0C),
            table_count: read_u32_be(data, 0x10),
        })
    }
}

fn read_u32_be(data: &[u8], offset: usize) -> u32 {
    u32::from_be_bytes(data[offset..offset + 4].try_into().expect("slice length"))
}

#[cfg(test)]
mod tests {
    use super::*;

    const FIXTURE: &str = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/tests/fixtures/tdb_header.bin"
    );

    #[test]
    fn parses_legacy_roster_tdb_header() {
        let data = std::fs::read(FIXTURE).expect("fixture");
        let header = TdbHeader::parse(&data).expect("parse");
        assert_eq!(header.endian, Endian::Little);
        assert_eq!(header.table_count, 39);
        assert_eq!(header.reserved, 0);
        assert_eq!(header.source_size, 0x0025_7A08);
    }
}

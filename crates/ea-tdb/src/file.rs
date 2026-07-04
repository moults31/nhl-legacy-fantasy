use crate::directory::{Directory, DirectoryEntry};
use crate::error::Result;
use crate::format::{read_u32_be, TdbHeader, HEADER_CRC_OFFSET, HEADER_SIZE};
use crate::table::TableLayout;

/// Top-level parsed TDB file (header + directory; table bodies loaded on demand).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TdbFile {
    pub header: TdbHeader,
    /// u32 BE at offset 0x14 (internal header CRC — reseal logic TBD).
    pub header_crc: u32,
    pub directory: Directory,
}

impl TdbFile {
    pub fn parse(data: &[u8]) -> Result<Self> {
        let header = TdbHeader::parse(data)?;
        if data.len() < HEADER_SIZE {
            return Err(crate::error::Error::TooSmall { len: data.len() });
        }
        let header_crc = read_u32_be(data, HEADER_CRC_OFFSET);
        let directory = Directory::parse(data, &header)?;
        Ok(Self {
            header,
            header_crc,
            directory,
        })
    }

    pub fn table_layout(&self, data: &[u8], entry: &DirectoryEntry) -> Result<TableLayout> {
        let offset = self.directory.table_data_start + entry.data_offset as usize;
        TableLayout::parse(data, offset)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const FIXTURE: &str = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/tests/fixtures/tdb_header.bin"
    );

    #[test]
    fn parses_fixture_file() {
        let data = std::fs::read(FIXTURE).expect("fixture");
        let file = TdbFile::parse(&data).expect("parse");
        assert_eq!(file.header.table_count, 39);
        assert_eq!(file.header_crc, 0x21E3_6BFD);
        assert_eq!(file.directory.table_data_start, 0x150);
    }
}

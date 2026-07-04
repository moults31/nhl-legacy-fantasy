use crate::error::{Error, Result};
use crate::format::{read_u32_be, TdbHeader, DIRECTORY_ENTRY_SIZE, DIRECTORY_OFFSET};

/// Four-character table or field identifier (EA TDB convention).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct TableId(pub [u8; 4]);

impl TableId {
    pub fn parse(bytes: [u8; 4]) -> Result<Self> {
        if bytes.iter().all(|&b| (32..127).contains(&b)) {
            Ok(Self(bytes))
        } else {
            Err(Error::InvalidTableId { found: bytes })
        }
    }

    pub fn as_str(&self) -> &str {
        std::str::from_utf8(&self.0).expect("validated ASCII")
    }
}

/// One row of the TDB directory (8 bytes on NHL Legacy roster DBs).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DirectoryEntry {
    pub table_id: TableId,
    /// Byte offset from `table_data_start` to the table header.
    pub data_offset: u32,
}

impl DirectoryEntry {
    pub fn parse(data: &[u8], offset: usize) -> Result<Self> {
        if offset + DIRECTORY_ENTRY_SIZE > data.len() {
            return Err(Error::TooSmall { len: data.len() });
        }
        let table_id = TableId::parse(data[offset..offset + 4].try_into().expect("slice"))?;
        Ok(Self {
            table_id,
            data_offset: read_u32_be(data, offset + 4),
        })
    }
}

/// Parsed directory block.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Directory {
    pub entries: Vec<DirectoryEntry>,
    /// Absolute offset where table blobs begin (`0x18 + count * 8` on observed saves).
    pub table_data_start: usize,
}

impl Directory {
    pub fn parse(data: &[u8], header: &TdbHeader) -> Result<Self> {
        let count = header.table_count as usize;
        let end = DIRECTORY_OFFSET
            .checked_add(count.checked_mul(DIRECTORY_ENTRY_SIZE).ok_or(Error::TooSmall {
                len: data.len(),
            })?)
            .ok_or(Error::TooSmall { len: data.len() })?;

        if data.len() < end {
            return Err(Error::TooSmall { len: data.len() });
        }

        let mut entries = Vec::with_capacity(count);
        for i in 0..count {
            let offset = DIRECTORY_OFFSET + i * DIRECTORY_ENTRY_SIZE;
            entries.push(DirectoryEntry::parse(data, offset)?);
        }

        Ok(Self {
            entries,
            table_data_start: end,
        })
    }

    pub fn get(&self, id: &str) -> Option<&DirectoryEntry> {
        self.entries.iter().find(|e| e.table_id.as_str() == id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::format::TdbHeader;

    const FIXTURE: &str = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/tests/fixtures/tdb_header.bin"
    );

    #[test]
    fn parses_legacy_directory() {
        let data = std::fs::read(FIXTURE).expect("fixture");
        let header = TdbHeader::parse(&data).expect("header");
        let dir = Directory::parse(&data, &header).expect("directory");
        assert_eq!(dir.entries.len(), 39);
        assert_eq!(dir.table_data_start, 0x150);
        assert_eq!(dir.entries[0].table_id.as_str(), "FxFG");
        assert_eq!(dir.entries[0].data_offset, 0);
        assert_eq!(dir.entries[1].table_id.as_str(), "OEtS");
        assert_eq!(dir.entries[1].data_offset, 0x60);
        assert!(dir.get("vbHh").is_some());
    }
}

use crate::directory::TableId;
use crate::error::{Error, Result};
use crate::format::{read_u32_be, FIELD_DESCRIPTOR_SIZE, TABLE_HEADER_SIZE};

/// Fixed table header immediately before field descriptors.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TableHeader {
    pub table_id: TableId,
    pub num_fields: u32,
    pub data_allocation_type: u32,
    pub max_records: u32,
}

impl TableHeader {
    pub fn parse(data: &[u8], offset: usize) -> Result<Self> {
        if offset + TABLE_HEADER_SIZE > data.len() {
            return Err(Error::TooSmall { len: data.len() });
        }
        Ok(Self {
            table_id: TableId::parse(data[offset..offset + 4].try_into().expect("slice"))?,
            num_fields: read_u32_be(data, offset + 4),
            data_allocation_type: read_u32_be(data, offset + 8),
            max_records: read_u32_be(data, offset + 12),
        })
    }

    pub fn field_descriptors_offset(&self, table_offset: usize) -> usize {
        table_offset + TABLE_HEADER_SIZE
    }

    pub fn records_offset(&self, table_offset: usize) -> usize {
        table_offset
            + TABLE_HEADER_SIZE
            + self.num_fields as usize * FIELD_DESCRIPTOR_SIZE
    }
}

/// One field descriptor (12 bytes on NHL Legacy roster DBs).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FieldDescriptor {
    pub field_id: [u8; 4],
    pub record_bit_offset: u32,
    pub bit_width: u32,
}

impl FieldDescriptor {
    pub fn parse(data: &[u8], offset: usize) -> Result<Self> {
        if offset + FIELD_DESCRIPTOR_SIZE > data.len() {
            return Err(Error::TooSmall { len: data.len() });
        }
        Ok(Self {
            field_id: data[offset..offset + 4].try_into().expect("slice"),
            record_bit_offset: read_u32_be(data, offset + 4),
            bit_width: read_u32_be(data, offset + 8),
        })
    }

    pub fn field_id_str(&self) -> Option<&str> {
        if self.field_id.iter().all(|&b| (32..127).contains(&b)) {
            std::str::from_utf8(&self.field_id).ok()
        } else {
            None
        }
    }
}

/// Directory entry resolved to its on-disk table layout.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TableLayout {
    pub header: TableHeader,
    pub fields: Vec<FieldDescriptor>,
    pub absolute_offset: usize,
}

impl TableLayout {
    pub fn parse(data: &[u8], absolute_offset: usize) -> Result<Self> {
        let header = TableHeader::parse(data, absolute_offset)?;
        let desc_base = header.field_descriptors_offset(absolute_offset);
        let desc_end = desc_base + header.num_fields as usize * FIELD_DESCRIPTOR_SIZE;
        if data.len() < desc_end {
            return Err(Error::TooSmall { len: data.len() });
        }

        let mut fields = Vec::with_capacity(header.num_fields as usize);
        for i in 0..header.num_fields as usize {
            fields.push(FieldDescriptor::parse(
                data,
                desc_base + i * FIELD_DESCRIPTOR_SIZE,
            )?);
        }

        Ok(Self {
            header,
            fields,
            absolute_offset,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::directory::Directory;
    use crate::format::TdbHeader;

    const FIXTURE: &str = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/tests/fixtures/tdb_header.bin"
    );

    #[test]
    fn parses_oets_table_layout() {
        let data = std::fs::read(FIXTURE).expect("fixture");
        let header = TdbHeader::parse(&data).expect("header");
        let dir = Directory::parse(&data, &header).expect("directory");
        let oets = dir.get("OEtS").expect("OEtS");
        let abs = dir.table_data_start + oets.data_offset as usize;
        let layout = TableLayout::parse(&data, abs).expect("table");
        assert_eq!(layout.header.num_fields, 6);
        assert_eq!(layout.header.data_allocation_type, 0x68);
        assert_eq!(layout.header.max_records, 0x33f);
        assert_eq!(layout.fields.len(), 6);
        assert_eq!(layout.header.table_id.as_str(), "B5o0");
        assert_eq!(layout.fields[4].field_id_str(), Some("DQhb"));
    }
}

use crate::directory::TableId;
use crate::error::{Error, Result};
use crate::format::{read_u32_be, Endian, FIELD_DESCRIPTOR_SIZE, TABLE_INFO_SIZE};

/// 40-byte table info block (`DBTable.infosize` in EA DB Editor).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TableInfo {
    /// Chained payload CRC written at info offset 0 (`DBTable.priorcrc` / `calcPcrc`).
    pub prior_crc: u32,
    pub unknown_2: u32,
    pub record_length_bytes: u32,
    pub record_length_bits: u32,
    pub max_records: u16,
    pub current_records: u16,
    pub num_fields: u8,
    pub index_count: u8,
    pub header_crc: u32,
}

impl TableInfo {
    pub fn parse(data: &[u8], offset: usize) -> Result<Self> {
        if offset + TABLE_INFO_SIZE > data.len() {
            return Err(Error::TooSmall { len: data.len() });
        }
        Ok(Self {
            prior_crc: read_u32_be(data, offset),
            unknown_2: read_u32_be(data, offset + 4),
            record_length_bytes: read_u32_be(data, offset + 8),
            record_length_bits: read_u32_be(data, offset + 12),
            max_records: read_u16_be(data, offset + 20),
            current_records: read_u16_be(data, offset + 22),
            num_fields: data[offset + 28],
            index_count: data[offset + 29],
            header_crc: read_u32_be(data, offset + 36),
        })
    }

    pub fn field_descriptors_offset(&self, info_offset: usize) -> usize {
        info_offset + TABLE_INFO_SIZE
    }

    pub fn records_offset(&self, info_offset: usize) -> usize {
        self.field_descriptors_offset(info_offset) + self.num_fields as usize * FIELD_DESCRIPTOR_SIZE
    }
}

/// 16-byte field descriptor (`Field.fieldsize` in EA DB Editor).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FieldDescriptor {
    pub kind_code: u32,
    pub record_bit_offset: u32,
    pub field_id: TableId,
    pub bit_width: u32,
}

impl FieldDescriptor {
    pub fn parse(data: &[u8], offset: usize) -> Result<Self> {
        if offset + FIELD_DESCRIPTOR_SIZE > data.len() {
            return Err(Error::TooSmall { len: data.len() });
        }
        Ok(Self {
            kind_code: read_u32_be(data, offset),
            record_bit_offset: read_u32_be(data, offset + 4),
            field_id: TableId::parse(data[offset + 8..offset + 12].try_into().expect("slice"))?,
            bit_width: read_u32_be(data, offset + 12),
        })
    }
}

/// Resolved table: info block, descriptors, and absolute file offsets.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TableLayout {
    pub info: TableInfo,
    pub fields: Vec<FieldDescriptor>,
    pub info_offset: usize,
}

impl TableLayout {
    pub fn parse(data: &[u8], info_offset: usize) -> Result<Self> {
        let info = TableInfo::parse(data, info_offset)?;
        let desc_base = info.field_descriptors_offset(info_offset);
        let desc_end = desc_base + info.num_fields as usize * FIELD_DESCRIPTOR_SIZE;
        if data.len() < desc_end {
            return Err(Error::TooSmall { len: data.len() });
        }

        let mut fields = Vec::with_capacity(info.num_fields as usize);
        for i in 0..info.num_fields as usize {
            fields.push(FieldDescriptor::parse(
                data,
                desc_base + i * FIELD_DESCRIPTOR_SIZE,
            )?);
        }

        Ok(Self {
            info,
            fields,
            info_offset,
        })
    }

    pub fn records_offset(&self) -> usize {
        self.info.records_offset(self.info_offset)
    }

    pub fn find_field(&self, id: &str) -> Option<&FieldDescriptor> {
        self.fields.iter().find(|f| f.field_id.as_str() == id)
    }

    pub fn read_field(
        &self,
        data: &[u8],
        record_index: usize,
        field: &FieldDescriptor,
        endian: Endian,
    ) -> Result<u64> {
        let rlb = self.info.record_length_bytes as usize;
        if rlb == 0 {
            return Err(Error::InvalidRecordAccess {
                reason: "record_length_bytes is zero",
            });
        }
        let record_byte = self.records_offset() + record_index * rlb;
        let bit_offset = record_byte * 8 + field.record_bit_offset as usize;
        let end_bit = bit_offset + field.bit_width as usize;
        if end_bit > data.len() * 8 {
            return Err(Error::InvalidRecordAccess {
                reason: "field bits extend past file end",
            });
        }
        Ok(crate::bitview::read_bits(
            data,
            bit_offset,
            field.bit_width,
            endian,
        ))
    }
}

fn read_u16_be(data: &[u8], offset: usize) -> u16 {
    u16::from_be_bytes(data[offset..offset + 2].try_into().expect("slice length"))
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
    fn parses_oets_table_info() {
        let data = std::fs::read(FIXTURE).expect("fixture");
        let header = TdbHeader::parse(&data).expect("header");
        let dir = Directory::parse(&data, &header).expect("directory");
        let oets = dir.get("OEtS").expect("OEtS");
        let abs = dir.table_data_start + oets.data_offset as usize;
        let layout = TableLayout::parse(&data, abs).expect("table");
        assert_eq!(layout.info.unknown_2, 6);
        assert_eq!(layout.info.record_length_bytes, 104);
        assert_eq!(layout.info.record_length_bits, 831);
        assert_eq!(layout.info.num_fields, 18);
        assert_eq!(layout.fields.len(), 18);
        assert_eq!(layout.fields[4].field_id.as_str(), "JxRK");
        assert_eq!(layout.fields[4].kind_code, 3);
        let value = layout
            .read_field(&data, 0, &layout.fields[4], Endian::Little)
            .expect("read field");
        let _ = value; // smoke: bit offset in range for record 0
    }

    #[test]
    fn ajmx_references_xfxw_field() {
        let data = std::fs::read(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/tests/fixtures/ajmx_table.bin"
        ))
        .expect("ajmx fixture");
        let layout = TableLayout::parse(&data, 0).expect("table");
        let xfxw = layout.find_field("xFXw").expect("xFXw field ref");
        assert_eq!(xfxw.bit_width, 7);
        assert_eq!(xfxw.record_bit_offset, 45);
        assert_eq!(layout.info.num_fields, 16);
    }
}

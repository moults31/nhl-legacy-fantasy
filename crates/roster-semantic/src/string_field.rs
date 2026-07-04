use ea_tdb::{Error, FieldDescriptor, Result, TableLayout};

/// Read a fixed-width null-terminated string field (`kind_code == 0`).
pub fn read_string_field(
    layout: &TableLayout,
    db: &[u8],
    record_index: usize,
    field: &FieldDescriptor,
) -> Result<String> {
    if field.kind_code != 0 {
        return Err(Error::InvalidRecordAccess {
            reason: "not a string field (kind_code != 0)",
        });
    }
    let rlb = layout.info.record_length_bytes as usize;
    if rlb == 0 {
        return Err(Error::InvalidRecordAccess {
            reason: "record_length_bytes is zero",
        });
    }
    let record_byte = layout.records_offset() + record_index * rlb;
    let start = record_byte + field.record_bit_offset as usize / 8;
    let len = field.bit_width as usize / 8;
    if start + len > db.len() {
        return Err(Error::InvalidRecordAccess {
            reason: "string field extends past file end",
        });
    }
    let slice = &db[start..start + len];
    let end = slice.iter().position(|&b| b == 0).unwrap_or(len);
    Ok(String::from_utf8_lossy(&slice[..end]).into_owned())
}

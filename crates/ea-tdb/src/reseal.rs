//! Reseal EA TDB internal CRCs (`DBFileInfo.CalcChecksums` in EA DB Editor).
//!
//! Uses standard CRC-32 BE (poly 0x04C11DB7, byte-at-a-time), which matches
//! Modding Studio's computation for `prior_crc`, `header_crc`, and EOF CRC.

use crate::crc_standard::crc_stored;
use crate::directory::Directory;
use crate::error::{Error, Result};
use crate::format::{
    write_u32_be, TdbHeader, HEADER_CRC_OFFSET, TABLE_INFO_SIZE,
};

/// Recompute and write file header, table `prior_crc` / `header_crc`, and EOF CRC.
pub fn reseal_checksums(data: &mut [u8]) -> Result<()> {
    if data.len() < 4 {
        return Err(Error::TooSmall { len: data.len() });
    }

    let header = TdbHeader::parse(data)?;
    let directory = Directory::parse(data, &header)?;
    let table_count = directory.entries.len();
    if table_count == 0 {
        return Err(Error::InvalidRecordAccess {
            reason: "TDB has no tables",
        });
    }

    let table_data_start = directory.table_data_start;
    let dir_len = table_count * 8;

    // Header CRC: first 20 bytes
    write_u32_be(data, HEADER_CRC_OFFSET, crc_stored(&data[..20]));

    // Chain: gap from directory end (offset 24) to first table
    let mut prior = crc_stored(&data[24..24 + dir_len]);
    let mut last_end = 0usize;

    for (i, entry) in directory.entries.iter().enumerate() {
        let info_off = table_data_start + entry.data_offset as usize;
        if info_off + TABLE_INFO_SIZE > data.len() {
            return Err(Error::TooSmall { len: data.len() });
        }

        write_u32_be(data, info_off, prior);

        // Table header CRC: 32 bytes starting at info_off + 4
        let hdr_end = info_off + TABLE_INFO_SIZE;
        if hdr_end > data.len() {
            return Err(Error::TooSmall { len: data.len() });
        }
        write_u32_be(
            data,
            info_off + 36,
            crc_stored(&data[info_off + 4..info_off + 36]),
        );

        last_end = hdr_end;
        if i + 1 < table_count {
            let next_start =
                table_data_start + directory.entries[i + 1].data_offset as usize;
            if next_start < last_end {
                return Err(Error::InvalidRecordAccess {
                    reason: "table offsets overlap",
                });
            }
            if next_start > data.len() {
                return Err(Error::TooSmall { len: data.len() });
            }
            prior = crc_stored(&data[last_end..next_start]);
        }
    }

    let eof_offset = data.len() - 4;
    if last_end > eof_offset {
        return Err(Error::InvalidRecordAccess {
            reason: "last table extends past EOF CRC",
        });
    }
    write_u32_be(data, eof_offset, crc_stored(&data[last_end..eof_offset]));

    Ok(())
}

/// Verify on-disk CRC fields match [`reseal_checksums`] without modifying the buffer.
pub fn verify_checksums(data: &[u8]) -> Result<()> {
    let mut copy = data.to_vec();
    reseal_checksums(&mut copy)?;
    if copy != data {
        return Err(Error::ChecksumMismatch);
    }
    Ok(())
}

//! Reseal EA TDB internal CRCs (`DBFileInfo.CalcChecksums` in EA DB Editor).

use crate::crc::Crc32Be;
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

    let crc = Crc32Be::new();
    let table_data_start = directory.table_data_start;
    let dir_len = (table_count * 8) as u32;

    let header_crc = !crc.crc32_be(0, data, 20, 0);
    write_u32_be(data, HEADER_CRC_OFFSET, header_crc);

    let mut prior = !crc.crc32_be(0, data, dir_len, 24);
    let mut last_end = 0usize;

    for (i, entry) in directory.entries.iter().enumerate() {
        let info_off = table_data_start + entry.data_offset as usize;
        if info_off + TABLE_INFO_SIZE > data.len() {
            return Err(Error::TooSmall { len: data.len() });
        }

        write_u32_be(data, info_off, prior);
        let table_header_crc = !crc.crc32_be(0, data, 32, info_off as u32 + 4);
        write_u32_be(data, info_off + 36, table_header_crc);

        last_end = info_off + TABLE_INFO_SIZE;
        if i + 1 < table_count {
            let next_start =
                table_data_start + directory.entries[i + 1].data_offset as usize;
            if next_start < last_end {
                return Err(Error::InvalidRecordAccess {
                    reason: "table offsets overlap",
                });
            }
            let gap = (next_start - last_end) as u32;
            let gap_end = last_end + gap as usize;
            if gap_end > data.len() {
                return Err(Error::TooSmall { len: data.len() });
            }
            prior = !crc.crc32_be(0, data, gap, last_end as u32);
        }
    }

    let eof_offset = data.len() - 4;
    if last_end > eof_offset {
        return Err(Error::InvalidRecordAccess {
            reason: "last table extends past EOF CRC",
        });
    }
    let eof_crc = !crc.crc32_be(0, data, (eof_offset - last_end) as u32, last_end as u32);
    write_u32_be(data, eof_offset, eof_crc);

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

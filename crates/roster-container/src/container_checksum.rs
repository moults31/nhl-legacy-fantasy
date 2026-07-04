//! RosterFile container checksums at header offsets `0x10` and `0x28`.
//!
//! Reverse-engineered from `NHL Modding Studio.exe` (`tdb-savedata` pack path):
//! - `@0x10`: IEEE reflected CRC-32 over `[0x1c .. end)`
//! - `@0x28`: big-endian CRC-32 (poly `0x04C11DB7`) over `[0x2c .. end)`

use crate::error::{Error, Result};

const PRIMARY_OFFSET: usize = 0x10;
const SECONDARY_OFFSET: usize = 0x28;
const PRIMARY_START: usize = 0x1c;
const SECONDARY_START: usize = 0x2c;
const MIN_LEN: usize = 0x30;

/// Checksum at `0x10` (IEEE reflected CRC-32, init `0xFFFFFFFF`, final `!crc`).
pub fn checksum_primary(data: &[u8]) -> Result<u32> {
    let slice = primary_slice(data)?;
    Ok(crc32_ieee(slice))
}

/// Checksum at `0x28` (MSB-first CRC-32, init `0xFFFFFFFF`, final `!crc`).
pub fn checksum_secondary(data: &[u8]) -> Result<u32> {
    let slice = secondary_slice(data)?;
    Ok(crc32_be_shift(slice))
}

/// Write both container checksum fields on a packed roster buffer.
///
/// `@0x28` is computed first (input starts at `0x2c`). `@0x10` is computed second
/// over `[0x1c .. end)`, which includes the sealed `@0x28` value — matching
/// `NHL Modding Studio.exe` write order.
pub fn seal(data: &mut [u8]) -> Result<()> {
    let secondary = checksum_secondary(data)?;
    write_be_u32(data, SECONDARY_OFFSET, secondary);
    let primary = checksum_primary(data)?;
    write_be_u32(data, PRIMARY_OFFSET, primary);
    Ok(())
}

/// Verify on-disk checksum fields match [`seal`].
pub fn verify(data: &[u8]) -> Result<()> {
    let on_disk_primary = read_be_u32(data, PRIMARY_OFFSET);
    let on_disk_secondary = read_be_u32(data, SECONDARY_OFFSET);
    let expect_secondary = checksum_secondary(data)?;
    if on_disk_secondary != expect_secondary {
        return Err(Error::ChecksumMismatch {
            offset_0x10: on_disk_primary,
            expected_0x10: 0,
            offset_0x28: on_disk_secondary,
            expected_0x28: expect_secondary,
        });
    }
    let expect_primary = checksum_primary(data)?;
    if on_disk_primary != expect_primary {
        return Err(Error::ChecksumMismatch {
            offset_0x10: on_disk_primary,
            expected_0x10: expect_primary,
            offset_0x28: on_disk_secondary,
            expected_0x28: expect_secondary,
        });
    }
    Ok(())
}

fn primary_slice(data: &[u8]) -> Result<&[u8]> {
    if data.len() < MIN_LEN {
        return Err(Error::TooSmall { len: data.len() });
    }
    Ok(&data[PRIMARY_START..])
}

fn secondary_slice(data: &[u8]) -> Result<&[u8]> {
    if data.len() < MIN_LEN {
        return Err(Error::TooSmall { len: data.len() });
    }
    Ok(&data[SECONDARY_START..])
}

fn read_be_u32(data: &[u8], offset: usize) -> u32 {
    u32::from_be_bytes(data[offset..offset + 4].try_into().expect("u32 slice"))
}

fn write_be_u32(data: &mut [u8], offset: usize, value: u32) {
    data[offset..offset + 4].copy_from_slice(&value.to_be_bytes());
}

fn crc32_ieee(data: &[u8]) -> u32 {
    static TABLE: [u32; 256] = build_crc32_ieee_table();
    let mut crc = 0xFFFF_FFFFu32;
    for &byte in data {
        let idx = (byte ^ crc as u8) as usize;
        crc = (crc >> 8) ^ TABLE[idx];
    }
    !crc
}

fn crc32_be_shift(data: &[u8]) -> u32 {
    static TABLE: [u32; 256] = build_crc32_be_table();
    let mut crc = 0xFFFF_FFFFu32;
    let mut i = 0;
    while i + 1 < data.len() {
        let idx = ((crc >> 24) ^ u32::from(data[i])) as usize;
        crc = (crc << 8) ^ TABLE[idx];
        let idx = ((crc >> 24) ^ u32::from(data[i + 1])) as usize;
        crc = (crc << 8) ^ TABLE[idx];
        i += 2;
    }
    if i < data.len() {
        let idx = ((crc >> 24) ^ u32::from(data[i])) as usize;
        crc = (crc << 8) ^ TABLE[idx];
    }
    !crc
}

const fn build_crc32_ieee_table() -> [u32; 256] {
    let mut table = [0u32; 256];
    let mut i = 0usize;
    while i < 256 {
        let mut c = i as u32;
        let mut bit = 0;
        while bit < 8 {
            c = if c & 1 != 0 {
                (c >> 1) ^ 0xEDB8_8320
            } else {
                c >> 1
            };
            bit += 1;
        }
        table[i] = c;
        i += 1;
    }
    table
}

const fn build_crc32_be_table() -> [u32; 256] {
    let poly = 0x04C1_1DB7u32;
    let mut table = [0u32; 256];
    let mut i = 0usize;
    while i < 256 {
        let mut c = (i as u32) << 24;
        let mut bit = 0;
        while bit < 8 {
            c = if c & 0x8000_0000 != 0 {
                (c << 1) ^ poly
            } else {
                c << 1
            };
            bit += 1;
        }
        table[i] = c;
        i += 1;
    }
    table
}

#[cfg(test)]
mod tests {
    use super::*;

    const FIXTURE: &str = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../tests/fixtures/xbox/roster.bin"
    );

    #[test]
    fn fixture_checksums_verify() {
        let data = std::fs::read(FIXTURE).expect("fixture");
        verify(&data).expect("fixture checksums");
    }

    #[test]
    fn seal_is_idempotent_on_fixture() {
        let mut data = std::fs::read(FIXTURE).expect("fixture");
        seal(&mut data).expect("seal");
        verify(&data).expect("verify after seal");
    }
}

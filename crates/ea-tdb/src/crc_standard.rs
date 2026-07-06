//! Standard byte-at-a-time CRC-32 BE (poly 0x04C11DB7).
//!
//! This is the algorithm Modding Studio uses for TDB gap chain CRCs
//! (`prior_crc`) and table header CRCs. It differs from [`super::Crc32Be`]
//! which uses a nibble-at-a-time variant that produces different output.

const CRC_POLY_BE: u32 = 0x04C1_1DB7;

fn table() -> &'static [u32; 256] {
    use std::sync::OnceLock;
    static TABLE: OnceLock<[u32; 256]> = OnceLock::new();
    TABLE.get_or_init(|| {
        let mut t = [0u32; 256];
        for (i, entry) in t.iter_mut().enumerate() {
            let mut crc = (i as u32) << 24;
            for _ in 0..8 {
                crc = if crc & 0x8000_0000 != 0 {
                    (crc << 1) ^ CRC_POLY_BE
                } else {
                    crc << 1
                };
            }
            *entry = crc;
        }
        t
    })
}

/// Standard CRC-32 BE hash over `data` (init 0xFFFFFFFF, final XOR).
///
/// The stored TDB CRC value is `!crc32_be(data)`, which strips the final XOR.
pub fn crc32_be(data: &[u8]) -> u32 {
    let table = table();
    let mut crc = 0xFFFF_FFFFu32;
    for &byte in data {
        let idx = ((crc >> 24) ^ byte as u32) as usize;
        crc = (crc << 8) ^ table[idx];
    }
    crc ^ 0xFFFF_FFFF
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_known_vectors() {
        // Standard CRC-32/BZIP2 for "123456789" → 0xFC891918
        // But with final XOR stripped (!0xFC891918 = 0x0376E6E7)
        let hash = crc32_be(b"123456789");
        let stored = !hash; // TDB stores NOT(crc)
        assert_eq!(stored, 0x0376_E6E7, "standard CRC raw value");
    }
}

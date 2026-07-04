//! Big-endian CRC-32 used inside EA TDB files (`DB_CRC.crc32_be` in EA DB Editor).

const CRC_POLY_BE: u32 = 0x04C1_1DB7;

/// CRC-32 with big-endian byte order (EA DB Editor `DB_CRC.crc32_be`).
#[derive(Clone, Debug)]
pub struct Crc32Be {
    table: [u32; 256],
}

impl Default for Crc32Be {
    fn default() -> Self {
        Self::new()
    }
}

impl Crc32Be {
    pub fn new() -> Self {
        Self {
            table: build_table(CRC_POLY_BE),
        }
    }

    /// Hash `data[start..start + len]` continuing from `seed`.
    pub fn crc32_be(&self, seed: u32, data: &[u8], start: u32, len: u32) -> u32 {
        let mut crc = seed ^ 0xFFFF_FFFF;
        let mut i = start as usize;
        let mut remaining = len;
        while remaining > 0 {
            let byte = data[i];
            i += 1;
            remaining -= 1;
            crc ^= u32::from(byte) << 24;
            let idx = ((crc << 4) >> 28) as usize;
            crc ^= self.table[idx];
            let idx = ((crc << 4) >> 28) as usize;
            crc ^= self.table[idx];
        }
        crc ^ 0xFFFF_FFFF
    }

    /// Convenience wrapper over the full slice.
    pub fn hash(&self, data: &[u8]) -> u32 {
        self.crc32_be(0, data, 0, data.len() as u32)
    }
}

fn build_table(poly: u32) -> [u32; 256] {
    let mut table = [0u32; 256];
    let mut carry = 0x8000_0000u32;
    let mut i = 1u32;
    while i < 256 {
        table[i as usize] = carry;
        carry = if carry & 0x8000_0000 != 0 {
            (carry << 1) ^ poly
        } else {
            carry << 1
        };
        let mut j = 1u32;
        while j < i {
            table[(i + j) as usize] = table[i as usize] ^ table[j as usize];
            j += 1;
        }
        i <<= 1;
    }
    table
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_ea_db_editor_reference_vectors() {
        // Golden values from a C# reimplementation of EA DB Editor IL (Mono.Cecil).
        let crc = Crc32Be::new();
        let ascii = b"123456789";
        assert_eq!(crc.hash(ascii), 0x3882_3B6E);

        let db = include_bytes!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/tests/fixtures/tdb_header.bin"
        ));
        assert_eq!(crc.crc32_be(0, db, 0, 64), 0xD547_5005);
    }
}

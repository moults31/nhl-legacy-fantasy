//! Port of feudalnate `EAChecksum.dll` (used by MC02Handler for Xbox MC02 packages).
//!
//! Not yet confirmed for the u32 at `RosterFile` offset 0x10 — see docs/M2-PACK.md.

use crate::ea_checksum_table::EA_CHECKSUM_TABLE;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Rotation {
    Right = 0,
    Left = 1,
}

/// Stateful EAChecksum hasher matching `EAChecksum.EAChecksum` in the reference DLL.
#[derive(Clone, Debug)]
pub struct EaChecksum {
    table: &'static [u32; 1024],
    cached: bool,
    last: u32,
}

impl Default for EaChecksum {
    fn default() -> Self {
        Self::new()
    }
}

impl EaChecksum {
    pub fn new() -> Self {
        Self {
            table: &EA_CHECKSUM_TABLE,
            cached: false,
            last: 0,
        }
    }

    pub fn reset(&mut self) {
        self.cached = false;
        self.last = 0;
    }

    /// One-shot hash over `data` (equivalent to `TransformFinalBlock(data)`).
    pub fn hash(data: &[u8]) -> u32 {
        let mut h = Self::new();
        h.transform_final_block(data)
    }

    /// Hash bytes stored big-endian (matches `get_GetHashBytes` after `TransformBlock`).
    pub fn hash_be_bytes(data: &[u8]) -> [u8; 4] {
        hash_to_be_bytes(Self::hash(data))
    }

    pub fn transform_block(&mut self, data: &[u8]) {
        if data.is_empty() {
            return;
        }
        if !self.cached {
            self.cache_first_block(data);
        }
        if data.len() <= 4 {
            return;
        }
        self.compute(data, data.len() as u64);
    }

    pub fn transform_final_block(&mut self, data: &[u8]) -> u32 {
        self.transform_block(data);
        self.get_hash()
    }

    pub fn get_hash(&self) -> u32 {
        !self.last
    }

    fn cache_first_block(&mut self, data: &[u8]) {
        debug_assert!(data.len() >= 4);
        let x = rotate(data[0] as u32, 8, Rotation::Left)
            | rotate(data[1] as u32, 16, Rotation::Left)
            | rotate(data[2] as u32, 8, Rotation::Right);
        self.last = !(x | data[3] as u32);
        self.cached = true;
    }

    fn compute(&mut self, data: &[u8], length: u64) {
        if length == 0 {
            return;
        }
        let end = length - 1;
        let mut i = 4u64;
        while i <= end {
            let idx = next_index(
                self.table,
                rotate(self.last, 10, Rotation::Right) & 0x3FC,
            );
            self.last = ((self.last << 8) | u32::from(data[i as usize])) ^ idx;
            i += 1;
        }
    }
}

fn rotate(value: u32, shift: u32, direction: Rotation) -> u32 {
    let shift = shift & 31;
    match direction {
        // EAChecksum.Rotation names are reversed vs the bit ops in Rotate().
        Rotation::Left => value.rotate_right(shift),
        Rotation::Right => value.rotate_left(shift),
    }
}

fn next_index(table: &[u32; 1024], index: u32) -> u32 {
    let mut bytes = [0u8; 4];
    for (i, byte) in bytes.iter_mut().enumerate() {
        *byte = table[index as usize + i] as u8;
    }
    bytes.reverse();
    u32::from_le_bytes(bytes)
}

fn hash_to_be_bytes(hash: u32) -> [u8; 4] {
    hash.to_be_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_dll_on_short_vector() {
        // Golden: EAChecksum.dll TransformFinalBlock([1..=10]) via .NET 8 reflection.
        let data: [u8; 10] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
        assert_eq!(EaChecksum::hash(&data), 0xA1_11_25_50);
    }

    #[test]
    fn hash_bytes_are_big_endian() {
        let bytes = EaChecksum::hash_be_bytes(&[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
        assert_eq!(bytes, [0xA1, 0x11, 0x25, 0x50]);
    }
}

use crate::format::Endian;

/// Read a single bit at an absolute bit index (mirrors tdb-core / stick_widen).
pub fn get_bit(buf: &[u8], bit: usize, endian: Endian) -> bool {
    let mask = match endian {
        Endian::Little => 1u8 << (bit % 8),
        Endian::Big => 0x80u8 >> (bit % 8),
    };
    (buf[bit / 8] & mask) != 0
}

/// Write a single bit at an absolute bit index.
pub fn set_bit(buf: &mut [u8], bit: usize, val: bool, endian: Endian) {
    let mask = match endian {
        Endian::Little => 1u8 << (bit % 8),
        Endian::Big => 0x80u8 >> (bit % 8),
    };
    if val {
        buf[bit / 8] |= mask;
    } else {
        buf[bit / 8] &= !mask;
    }
}

/// Read a `width`-bit field at `bit_offset`.
pub fn read_bits(buf: &[u8], bit_offset: usize, width: u32, endian: Endian) -> u64 {
    if width == 0 {
        return 0;
    }
    let mut val = 0u64;
    for k in 0..width as usize {
        let bit = u64::from(get_bit(buf, bit_offset + k, endian));
        match endian {
            Endian::Little => val |= bit << k,
            Endian::Big => val |= bit << (width as usize - 1 - k),
        }
    }
    val
}

/// Write `value` into a `width`-bit field at `bit_offset`. Returns false if out of range.
pub fn write_bits(
    buf: &mut [u8],
    bit_offset: usize,
    width: u32,
    value: u64,
    endian: Endian,
) -> bool {
    if width == 0 {
        return true;
    }
    let max_bit = bit_offset + width as usize;
    if max_bit > buf.len() * 8 {
        return false;
    }
    for k in 0..width as usize {
        let bit = match endian {
            Endian::Little => ((value >> k) & 1) != 0,
            Endian::Big => ((value >> (width as usize - 1 - k)) & 1) != 0,
        };
        set_bit(buf, bit_offset + k, bit, endian);
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_le_three_bits() {
        let mut buf = [0u8; 2];
        assert!(write_bits(&mut buf, 0, 3, 0b101, Endian::Little));
        assert_eq!(read_bits(&buf, 0, 3, Endian::Little), 0b101);
    }

    #[test]
    fn round_trip_be_three_bits() {
        let mut buf = [0u8; 2];
        assert!(write_bits(&mut buf, 0, 3, 0b101, Endian::Big));
        assert_eq!(read_bits(&buf, 0, 3, Endian::Big), 0b101);
    }
}

/// Xbox 360 / Xenia inner roster save magic (`RosterFile` + null padding to 16 bytes).
pub const XBOX360_MAGIC: &[u8; 16] = b"RosterFile\0\0\0\0\0\0";

/// PS3 roster save magic.
pub const PS3_MAGIC: &[u8; 13] = b"PS3RosterFile";

/// Observed Xbox 360 header size before the zlib stream begins.
pub const XBOX360_HEADER_SIZE: usize = 48;

/// Zlib stream signature used to locate compressed payload when header size varies.
pub const ZLIB_MAGIC: [u8; 2] = [0x78, 0x9c];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Platform {
    Xbox360,
    Ps3,
}

/// Parsed Xbox 360 container header fields (offsets from file start).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RosterHeader {
    pub platform: Platform,
    /// Checksum at offset 0x10 (algorithm TBD — see milestone 2).
    pub checksum: u32,
    /// Field at 0x14, observed as 4 on live saves.
    pub field_0x14: u32,
    /// Field at 0x18.
    pub field_0x18: u32,
    /// Field at 0x1C, observed as 1 on live saves.
    pub field_0x1c: u32,
    /// Field at 0x20, observed as 2 on live saves.
    pub field_0x20: u32,
    /// Uncompressed TDB size (big-endian u32 at 0x24 on observed saves).
    pub uncompressed_size: u32,
    /// Field at 0x28.
    pub field_0x28: u32,
    /// Field at 0x2C.
    pub field_0x2c: u32,
    /// Byte offset where the zlib stream starts.
    pub payload_offset: usize,
}

impl RosterHeader {
    pub fn parse(data: &[u8]) -> crate::Result<Self> {
        if data.starts_with(XBOX360_MAGIC) {
            return parse_xbox360(data);
        }
        if data.starts_with(PS3_MAGIC) {
            return Err(crate::Error::UnsupportedPlatform(
                "PS3 (PS3RosterFile) unpack is not implemented yet",
            ));
        }
        Err(crate::Error::UnknownMagic)
    }
}

fn parse_xbox360(data: &[u8]) -> crate::Result<RosterHeader> {
    if data.len() < XBOX360_HEADER_SIZE {
        return Err(crate::Error::TooSmall { len: data.len() });
    }

    let payload_offset = find_zlib_offset(data).ok_or(crate::Error::UnknownMagic)?;

    Ok(RosterHeader {
        platform: Platform::Xbox360,
        checksum: read_u32_be(data, 0x10),
        field_0x14: read_u32_be(data, 0x14),
        field_0x18: read_u32_be(data, 0x18),
        field_0x1c: read_u32_be(data, 0x1c),
        field_0x20: read_u32_be(data, 0x20),
        uncompressed_size: read_u32_be(data, 0x24),
        field_0x28: read_u32_be(data, 0x28),
        field_0x2c: read_u32_be(data, 0x2c),
        payload_offset,
    })
}

fn read_u32_be(data: &[u8], offset: usize) -> u32 {
    u32::from_be_bytes(data[offset..offset + 4].try_into().expect("slice length"))
}

fn find_zlib_offset(data: &[u8]) -> Option<usize> {
    // Prefer the known 48-byte layout when the signature is present there.
    if data.len() >= XBOX360_HEADER_SIZE + 2
        && data[XBOX360_HEADER_SIZE..XBOX360_HEADER_SIZE + 2] == ZLIB_MAGIC
    {
        return Some(XBOX360_HEADER_SIZE);
    }

    data.windows(2)
        .position(|window| window == ZLIB_MAGIC)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn xbox_magic_constant_matches_fixture_prefix() {
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../tests/fixtures/xbox/roster.bin"
        );
        let data = std::fs::read(path).expect("fixture");
        assert!(data.starts_with(XBOX360_MAGIC));
    }
}

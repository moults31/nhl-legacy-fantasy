use thiserror::Error;

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, Error)]
pub enum Error {
    #[error("TDB file is too small ({len} bytes)")]
    TooSmall { len: usize },

    #[error("invalid TDB magic: expected DB\\0\\x08, got {found:#04x?}")]
    InvalidMagic { found: [u8; 4] },

    #[error("unsupported TDB endian marker {marker}")]
    UnsupportedEndian { marker: u32 },

    #[error("invalid TDB table/field id (expected printable ASCII): {found:?}")]
    InvalidTableId { found: [u8; 4] },

    #[error("invalid TDB record access: {reason}")]
    InvalidRecordAccess { reason: &'static str },

    #[error("TDB CRC fields do not match reseal output")]
    ChecksumMismatch,
}

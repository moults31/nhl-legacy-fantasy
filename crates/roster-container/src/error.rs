use thiserror::Error;

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, Error)]
pub enum Error {
    #[error("roster save is too small ({len} bytes)")]
    TooSmall { len: usize },

    #[error("unrecognized roster container magic")]
    UnknownMagic,

    #[error("unsupported platform: {0}")]
    UnsupportedPlatform(&'static str),

    #[error("invalid TDB payload magic: expected DB\\0, got {found:#04x?}")]
    InvalidTdbMagic { found: [u8; 4] },

    #[error("zlib decompression failed: {0}")]
    Decompress(#[from] std::io::Error),

    #[error("zlib compression failed: {0}")]
    Compress(std::io::Error),

    #[error("roster container checksum algorithm for edited saves is not implemented yet")]
    ChecksumUnknown,
}

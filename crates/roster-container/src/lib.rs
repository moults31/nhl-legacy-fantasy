//! NHL Legacy roster save container format.
//!
//! Xbox 360 / Xenia saves use the `RosterFile\0` magic prefix, a fixed header,
//! and a zlib-compressed payload that is a bit-identical `default.db` TDB file.

mod ea_checksum;
mod ea_checksum_table;
mod error;
mod format;
mod pack;
mod unpack;

pub use ea_checksum::EaChecksum;
pub use error::{Error, Result};
pub use format::{Platform, RosterHeader, XBOX360_HEADER_SIZE, XBOX360_MAGIC, PS3_MAGIC};
pub use pack::{pack, pack_unchanged};
pub use unpack::{detect_platform, unpack, unpack_with_header};

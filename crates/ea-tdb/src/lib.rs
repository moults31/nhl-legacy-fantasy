//! EA TDB (`default.db`) helpers for NHL Legacy roster editing.
//!
//! Milestone 3 scope: port `DB_CRC.crc32_be` from EA DB Editor and parse the
//! fixed file header. Full table/directory parsing and CRC reseal come next.

mod crc;
mod error;
mod format;

pub use crc::Crc32Be;
pub use error::{Error, Result};
pub use format::{Endian, TdbHeader, HEADER_SIZE, TDB_MAGIC};

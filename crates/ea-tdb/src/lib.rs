//! EA TDB (`default.db`) helpers for NHL Legacy roster editing.
//!
//! Milestone 3: `DB_CRC.crc32_be`, fixed header, directory, and table layout parse.

mod crc;
mod directory;
mod error;
mod file;
mod format;
mod table;

pub use crc::Crc32Be;
pub use directory::{Directory, DirectoryEntry, TableId};
pub use error::{Error, Result};
pub use file::TdbFile;
pub use format::{
    Endian, TdbHeader, DIRECTORY_ENTRY_SIZE, DIRECTORY_OFFSET, FIELD_DESCRIPTOR_SIZE,
    HEADER_CRC_OFFSET, HEADER_SIZE, TABLE_HEADER_SIZE, TDB_MAGIC,
};
pub use table::{FieldDescriptor, TableHeader, TableLayout};

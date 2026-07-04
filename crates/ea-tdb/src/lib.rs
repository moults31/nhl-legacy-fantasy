//! EA TDB (`default.db`) helpers for NHL Legacy roster editing.
//!
//! Milestone 3: CRC, header/directory parse, table layout, bit-packed field I/O.

mod bitview;
mod crc;
mod directory;
mod error;
mod file;
mod format;
mod reseal;
mod table;

pub use bitview::{get_bit, read_bits, set_bit, write_bits};
pub use crc::Crc32Be;
pub use directory::{Directory, DirectoryEntry, TableId};
pub use error::{Error, Result};
pub use file::TdbFile;
pub use format::{
    Endian, TdbHeader, DIRECTORY_ENTRY_SIZE, DIRECTORY_OFFSET, FIELD_DESCRIPTOR_SIZE,
    HEADER_CRC_OFFSET, HEADER_SIZE, TABLE_HEADER_SIZE, TABLE_INFO_SIZE, TDB_MAGIC,
};
pub use reseal::{reseal_checksums, verify_checksums};
pub use table::{FieldDescriptor, TableInfo, TableLayout};

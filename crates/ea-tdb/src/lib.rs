//! EA TDB (`default.db`) helpers for NHL Legacy roster editing.
//!
//! Milestone 3: CRC, header/directory parse, table layout, bit-packed field I/O.

mod bitview;
mod crc_standard;
mod directory;
mod error;
mod file;
mod format;
mod reseal;
mod reseal_ms;
mod table;

pub use bitview::{get_bit, read_bits, set_bit, write_bits};
pub use crc_standard::{crc32_be as crc32_be_standard, crc_stored};
pub use directory::{Directory, DirectoryEntry, TableId};
pub use error::{Error, Result};
pub use file::TdbFile;
pub use format::{
    Endian, TdbHeader, DIRECTORY_ENTRY_SIZE, DIRECTORY_OFFSET, FIELD_DESCRIPTOR_SIZE,
    HEADER_CRC_OFFSET, HEADER_SIZE, TABLE_HEADER_SIZE, TABLE_INFO_SIZE, TDB_MAGIC,
};
pub use reseal::{reseal_checksums, verify_checksums};
pub use reseal_ms::reseal_ms_crcs;
pub use table::{FieldDescriptor, TableInfo, TableLayout};

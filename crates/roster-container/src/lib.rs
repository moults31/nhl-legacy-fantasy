//! NHL Legacy roster save container format.
//!
//! Xbox 360 / Xenia saves use the `RosterFile\0` magic prefix, a fixed header,
//! and a zlib-compressed payload that is a bit-identical `default.db` TDB file.

mod container_checksum;
mod deflate_inflate;
mod deflate_fdeflate_decode;
mod deflate_fdeflate_huffman;
pub mod deflate_fdeflate_ops;
mod deflate_fdeflate_tables;
mod deflate_fdeflate_trees;
pub mod deflate_template;
mod ea_checksum;
mod ea_checksum_table;
mod error;
mod format;
mod pack;
mod unpack;

pub use container_checksum::{
    checksum_primary, checksum_secondary, seal as seal_checksums, verify as verify_checksums,
};
pub use ea_checksum::EaChecksum;
pub use error::{Error, Result};
pub use format::{Platform, RosterHeader, XBOX360_HEADER_SIZE, XBOX360_MAGIC, PS3_MAGIC};
pub use deflate_template::{compress_zlib_from_template, inspect_deflate_blocks, DeflateBlockMeta};
pub use pack::{compress_zlib_stored_blocks, pack, pack_stored, pack_unchanged, pack_with_field_0x2c, pack_with_fdeflate};
pub use unpack::{detect_platform, unpack, unpack_with_header};

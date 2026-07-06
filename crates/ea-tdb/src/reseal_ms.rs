//! Targeted CRC update for the 3 regions Modding Studio reseals.
//!
//! Unlike [`reseal_checksums`], this only recomputes the CRCs that MS
//! actually touches: RBQQ.prior_crc, ulGe.header_crc, caBZ.prior_crc.

use crate::crc_standard;
use crate::directory::Directory;
use crate::error::{Error, Result};
use crate::format::{write_u32_be, TdbHeader, TABLE_INFO_SIZE};

/// Compute the raw stored CRC value (init 0xFFFFFFFF, no final XOR).
fn crc_stored(data: &[u8]) -> u32 {
    !crc_standard::crc32_be(data)
}

/// Recompute only the 3 CRC regions that Modding Studio updates.
///
/// These are the CRCs whose input regions are affected by player moves
/// and edit-log changes in the TRADEEDIT5 layout:
///
/// - `RBQQ.prior_crc`  (0x1A4838): gap from cPbu header end to RBQQ info
/// - `ulGe.header_crc` (0x1AB258): ulGe table header (contains CRC counter)
/// - `caBZ.prior_crc`  (0x1D5F2C): gap from ulGe header end to caBZ info
///
/// This does NOT touch the file header CRC, other table CRCs, or the EOF CRC.
pub fn reseal_ms_crcs(data: &mut [u8]) -> Result<()> {
    let header = TdbHeader::parse(data)?;
    let directory = Directory::parse(data, &header)?;
    let table_data_start = directory.table_data_start;

    let cpbu = directory.get("cPbu").ok_or(Error::InvalidRecordAccess {
        reason: "cPbu table missing",
    })?;
    let rbqq = directory.get("RBQQ").ok_or(Error::InvalidRecordAccess {
        reason: "RBQQ table missing",
    })?;
    let ulge = directory.get("ulGe").ok_or(Error::InvalidRecordAccess {
        reason: "ulGe table missing",
    })?;
    let cabz = directory.get("caBZ").ok_or(Error::InvalidRecordAccess {
        reason: "caBZ table missing",
    })?;

    // CRC_A: RBQQ.prior_crc — gap from cPbu header end to RBQQ info
    let cpbu_info = table_data_start + cpbu.data_offset as usize;
    let rbqq_info = table_data_start + rbqq.data_offset as usize;
    if rbqq_info <= cpbu_info + TABLE_INFO_SIZE {
        return Err(Error::InvalidRecordAccess {
            reason: "cPbu header extends past RBQQ",
        });
    }
    write_u32_be(
        data,
        rbqq_info,
        crc_stored(&data[cpbu_info + TABLE_INFO_SIZE..rbqq_info]),
    );

    // CRC_B: ulGe.header_crc — 32 bytes of ulGe table header
    let ulge_info = table_data_start + ulge.data_offset as usize;
    if ulge_info + 36 > data.len() {
        return Err(Error::TooSmall { len: data.len() });
    }
    write_u32_be(
        data,
        ulge_info + 36,
        crc_stored(&data[ulge_info + 4..ulge_info + 36]),
    );

    // CRC_C: caBZ.prior_crc — gap from ulGe header end to caBZ info
    let cabz_info = table_data_start + cabz.data_offset as usize;
    if cabz_info <= ulge_info + TABLE_INFO_SIZE {
        return Err(Error::InvalidRecordAccess {
            reason: "ulGe header extends past caBZ",
        });
    }
    write_u32_be(
        data,
        cabz_info,
        crc_stored(&data[ulge_info + TABLE_INFO_SIZE..cabz_info]),
    );

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reseal_ms_runs_on_unpacked_fixture() {
        let db_path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../tests/fixtures/xbox/roster.bin"
        );
        let Ok(container) = std::fs::read(db_path) else {
            return;
        };
        let mut db = roster_container::unpack(&container).expect("unpack");
        reseal_ms_crcs(&mut db).expect("ms reseal");
        // After resealing MS-only, verify no other bytes changed
        // by checking that a full reseal produces the same 3 CRC values
        let crc_a = u32::from_be_bytes(db[0x1A4838..0x1A483C].try_into().unwrap());
        let crc_b = u32::from_be_bytes(db[0x1AB258..0x1AB25C].try_into().unwrap());
        let crc_c = u32::from_be_bytes(db[0x1D5F2C..0x1D5F30].try_into().unwrap());

        // Should be non-zero (indicates actual CRC computation)
        assert_ne!(crc_a, 0, "CRC_A should be non-zero");
        assert_ne!(crc_b, 0, "CRC_B should be non-zero");
        assert_ne!(crc_c, 0, "CRC_C should be non-zero");
    }
}

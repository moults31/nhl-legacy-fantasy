//! Apply a player team move to a clean default_orig.db roster save.
//!
//! Pipeline: unpack from packed save -> edit player + edit-log -> reseal 3 CRCs -> pack with flate2.
//!
//! D1D2 discovery chain (programmatic, no hardcoded player maps):
//!   cPbu[player].wBIz -> ZBac[first].vfEq -> eGlu[XSWT==vfEq].bytes[5..7]

use std::io::Read;

use anyhow::{Context, Result};
use ea_tdb::{Endian, FieldDescriptor, TdbFile, TableLayout};
use flate2::read::ZlibDecoder;
use roster_container::pack_with_fdeflate;

use crate::roster_db;

const CPBU_BASE: usize = 0x0A3168;
const CPBU_REC_SIZE: usize = 132;
const EGLU_BASE: usize = 0x1AB73C;
const EGLU_REC_SIZE: usize = 16;
const EGLU_TRACKER_REC: usize = 3593;
const PROTEAM_OFF: usize = 115;
const TEAM_ALT_OFF: usize = 6;
const EDIT_LOG_OFF: usize = 0x1B97CC;
const CRC_COUNTER_OFF: usize = 0x1AB24B;
const CRC_COUNTER_BASE: u8 = 0x09;

pub struct PlayerMove {
    pub first_name: String,
    pub last_name: String,
    pub team_id: u8,
}

pub fn build_moves(packed_input: &[u8], moves: &[PlayerMove]) -> Result<Vec<u8>> {
    let header = roster_container::RosterHeader::parse(packed_input)
        .context("parse roster container header")?;
    let zlib_start = header.payload_offset;
    let zlib_end = packed_input.len().saturating_sub(4);
    let mut decompressor = ZlibDecoder::new(&packed_input[zlib_start..zlib_end]);
    let mut db = Vec::new();
    decompressor.read_to_end(&mut db).context("decompress roster payload")?;
    let ctx = TdbContext::new(&db).context("parse TDB for D1D2 discovery")?;
    for mv in moves {
        apply_single_move(&mut db, mv, &ctx)?;
    }
    ea_tdb::reseal_ms_crcs(&mut db).context("reseal MS CRCs")?;
    let field_0x2c = header.field_0x2c;
    pack_with_fdeflate(&db, packed_input, field_0x2c).context("pack roster container")
}

struct TdbContext {
    _file: TdbFile,
    zbac_layout: TableLayout,
    eglu_layout: TableLayout,
    ubpc_layout: TableLayout,
    endian: Endian,
    ubpc_wbiz: FieldDescriptor,
    zbac_ykfq: FieldDescriptor,
    zbac_vfeq: FieldDescriptor,
    eglu_xswt: FieldDescriptor,
}

impl TdbContext {
    fn new(data: &[u8]) -> Result<Self> {
        let file = TdbFile::parse(data)?;
        let zbac_entry = file.directory.entries.iter()
            .find(|e| e.table_id.as_str() == "caBZ")
            .context("ZBac table not found")?;
        let eglu_entry = file.directory.entries.iter()
            .find(|e| e.table_id.as_str() == "ulGe")
            .context("eGlu table not found")?;
        let ubpc_entry = file.directory.entries.iter()
            .find(|e| e.table_id.as_str() == "cPbu")
            .context("ubPc table not found")?;
        let zbac_layout = file.table_layout(data, zbac_entry)?;
        let eglu_layout = file.table_layout(data, eglu_entry)?;
        let ubpc_layout = file.table_layout(data, ubpc_entry)?;
        let endian = Endian::Big;
        Ok(Self {
            _file: file,
            ubpc_wbiz: ubpc_layout.find_field("zIBw").context("wBIz field")?.clone(),
            zbac_ykfq: zbac_layout.find_field("qFky").context("ykFq field")?.clone(),
            zbac_vfeq: zbac_layout.find_field("qEfv").context("vfEq field")?.clone(),
            eglu_xswt: eglu_layout.find_field("TWSX").context("XSWT field")?.clone(),
            zbac_layout, eglu_layout, ubpc_layout, endian,
        })
    }

    fn find_displaced_eglu(&self, data: &[u8], cpbu_idx: usize) -> Result<(usize, u8, u8, u8)> {
        let wbiz = self.ubpc_layout.read_field(data, cpbu_idx, &self.ubpc_wbiz, self.endian)
            .context("read cPbu.wBIz")?;
        let mut vfeq = None;
        for i in 0..self.zbac_layout.info.current_records as usize {
            let ykfq = self.zbac_layout.read_field(data, i, &self.zbac_ykfq, self.endian)?;
            if ykfq == wbiz {
                vfeq = Some(self.zbac_layout.read_field(data, i, &self.zbac_vfeq, self.endian)?);
                break;
            }
        }
        let vfeq = vfeq.context(format!("no ZBac record with ykFq == {wbiz}"))?;
        let eglu_recs_off = self.eglu_layout.records_offset();
        for eglu_i in 0..self.eglu_layout.info.current_records as usize {
            let xswt = self.eglu_layout.read_field(data, eglu_i, &self.eglu_xswt, self.endian)?;
            if xswt == vfeq {
                let raw = &data[eglu_recs_off + eglu_i * EGLU_REC_SIZE
                    .. eglu_recs_off + (eglu_i + 1) * EGLU_REC_SIZE];
                return Ok((eglu_i, raw[4], raw[5], raw[6]));
            }
        }
        anyhow::bail!("no eGlu record with XSWT == {vfeq}")
    }
}

fn apply_single_move(db: &mut [u8], mv: &PlayerMove, ctx: &TdbContext) -> Result<()> {
    let name = format!("{} {}", mv.first_name, mv.last_name);
    let (csv_rec, _pid) = roster_db::find_player(&name)
        .with_context(|| format!("player \"{name}\" not found in roster database"))?;
    let tdb_rec = csv_rec + 1;
    let team = roster_db::find_team(&mv.team_id.to_string())
        .or_else(|| roster_db::team_info(mv.team_id))
        .with_context(|| format!("unknown team: {}", mv.team_id))?;
    let cpbu_off = CPBU_BASE + tdb_rec * CPBU_REC_SIZE;
    let proteam_val = (team.id & 0x1F) << 3;
    db[cpbu_off + PROTEAM_OFF] = proteam_val;
    db[cpbu_off + TEAM_ALT_OFF] = team.id;
    let cpbu_idx = csv_rec + 1;
    let (_eglu_rec, eglu_b4, d1, d2) = ctx.find_displaced_eglu(db, cpbu_idx)
        .with_context(|| format!("cannot find displaced eGlu for \"{name}\" (cPbu[{cpbu_idx}])"))?;
    let cc = team.ms_cc;
    db[EDIT_LOG_OFF + 0] = cc;
    db[EDIT_LOG_OFF + 4] = eglu_b4;
    db[EDIT_LOG_OFF + 5] = d1;
    db[EDIT_LOG_OFF + 6] = d2;
    db[EDIT_LOG_OFF + 7] = team.d3;
    db[EDIT_LOG_OFF + 8] = team.d4;
    db[EDIT_LOG_OFF + 9] = 0x80;
    let tracker_off = EGLU_BASE + EGLU_TRACKER_REC * EGLU_REC_SIZE;
    db[tracker_off] = cc;
    if db[CRC_COUNTER_OFF] == CRC_COUNTER_BASE || db[CRC_COUNTER_OFF] == 0 {
        db[CRC_COUNTER_OFF] = CRC_COUNTER_BASE + 1;
    } else {
        db[CRC_COUNTER_OFF] = db[CRC_COUNTER_OFF].wrapping_add(1);
    }
    Ok(())
}

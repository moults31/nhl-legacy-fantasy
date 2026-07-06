//! Apply a player team move to a clean default_orig.db roster save.
//!
//! Pipeline: unpack packed save -> edit player + edit-log -> reseal 3 CRCs -> repack.
//!
//! D1D2 discovery chain (programmatic, no hardcoded player maps):
//!   cPbu[player].wBIz -> ZBac[first].vfEq -> eGlu[XSWT==vfEq].bytes[5..7]

use anyhow::{Context, Result};
use ea_tdb::{Endian, FieldDescriptor, TdbFile, TableLayout};
use roster_container::{pack, unpack};

use crate::roster_db;

const EGLU_TRACKER_REC: usize = 3593;
const EGLU_REC_SIZE: usize = 16;
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
    let mut db = unpack(packed_input).context("unpack roster container")?;

    let ctx = TdbContext::new(&db).context("parse TDB for D1D2 discovery")?;
    for mv in moves {
        apply_single_move(&mut db, mv, &ctx)?;
    }
    ea_tdb::reseal_ms_crcs(&mut db).context("reseal MS CRCs")?;

    pack(&db, packed_input, header.field_0x2c).context("pack roster container")
}

struct TdbContext {
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
    let cpbu_idx = csv_rec + 1;

    let team = roster_db::team_info(mv.team_id)
        .with_context(|| format!("unknown team: {}", mv.team_id))?;

    // Write cPbu proteam + team_alt using layout-computed offsets
    let cpbu_recs_off = ctx.ubpc_layout.records_offset();
    let cpbu_rec_size = ctx.ubpc_layout.info.record_length_bytes as usize;
    let cpbu_off = cpbu_recs_off + cpbu_idx * cpbu_rec_size;
    const PROTEAM_OFF: usize = 115;
    const TEAM_ALT_OFF: usize = 6;
    let proteam_val = (team.id & 0x1F) << 3;
    db[cpbu_off + PROTEAM_OFF] = proteam_val;
    db[cpbu_off + TEAM_ALT_OFF] = team.id;

    // Discover displaced eGlu
    let (eglu_rec, eglu_b4, d1, d2) = ctx.find_displaced_eglu(db, cpbu_idx)
        .with_context(|| format!("cannot find displaced eGlu for \"{name}\" (cPbu[{cpbu_idx}])"))?;

    // Write edit-log
    let cc = team.ms_cc;
    db[EDIT_LOG_OFF] = cc;
    db[EDIT_LOG_OFF + 4] = eglu_b4;
    db[EDIT_LOG_OFF + 5] = d1;
    db[EDIT_LOG_OFF + 6] = d2;
    db[EDIT_LOG_OFF + 7] = team.d3;
    db[EDIT_LOG_OFF + 8] = team.d4;
    db[EDIT_LOG_OFF + 9] = 0x80;

    // eGlu tracker
    let eglu_recs_off = ctx.eglu_layout.records_offset();
    db[eglu_recs_off + EGLU_TRACKER_REC * EGLU_REC_SIZE] = cc;

    // CRC counter
    if db[CRC_COUNTER_OFF] == CRC_COUNTER_BASE || db[CRC_COUNTER_OFF] == 0 {
        db[CRC_COUNTER_OFF] = CRC_COUNTER_BASE + 1;
    } else {
        db[CRC_COUNTER_OFF] = db[CRC_COUNTER_OFF].wrapping_add(1);
    }

    eprintln!(
        "  {name}: eGlu[{eglu_rec}] d1d2={d1:02x}{d2:02x} cc=0x{cc:02x} d3d4=0x{:02x}{:02x}",
        team.d3, team.d4
    );

    Ok(())
}

mod move_player;

use std::fs;
use std::io::Read;
use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use ea_tdb::reseal_checksums;
use roster_container::{pack, pack_stored, pack_with_fdeflate, pack_with_field_0x2c, unpack};
use roster_semantic::{apply_import, export_roster, RosterExport};

#[derive(Parser)]
#[command(name = "roster-cli", about = "NHL Legacy roster save tools")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Extract default.db from a RosterFile save container.
    Unpack {
        input: PathBuf,
        #[arg(short, long)]
        output: PathBuf,
    },
    /// Build a RosterFile save from default.db using a template save for header/compression.
    Pack {
        /// Extracted default.db TDB input.
        input: PathBuf,
        /// Original roster save used as template (header + zlib when unchanged).
        template: PathBuf,
        /// Optional `@0x2c` override for edited payloads (hex u32).
        #[arg(long)]
        field_0x2c: Option<String>,
        #[arg(short, long)]
        output: PathBuf,
    },
    /// Build a RosterFile using simple stored deflate blocks (bypasses template deflate).
    PackStored {
        input: PathBuf,
        template: PathBuf,
        #[arg(short, long)]
        output: PathBuf,
    },
    /// Export players and teams from default.db as JSON.
    Export {
        input: PathBuf,
        #[arg(short, long)]
        output: PathBuf,
    },
    /// Build a RosterFile using standard flate2 zlib compression (ignores template deflate).
    PackFdeflate {
        input: PathBuf,
        template: PathBuf,
        #[arg(long, value_name = "HEX")]
        field_0x2c: Option<String>,
        #[arg(short, long)]
        output: PathBuf,
    },
    /// Apply player proteam patches from JSON onto default.db.
    Import {
        input: PathBuf,
        patches: PathBuf,
        #[arg(short, long)]
        output: PathBuf,
    },
    /// Recompute and write TDB internal CRCs (header, table chain, EOF).
    Reseal {
        input: PathBuf,
        #[arg(short, long)]
        output: PathBuf,
    },
    /// Move a player to a new team (TRADEEDIT5-based, with MS normalization).
    MovePlayer {
        /// Packed roster save input (e.g., TRADEEDIT5).
        input: PathBuf,
        /// Player first name.
        #[arg(long)]
        player_first: String,
        /// Player last name.
        #[arg(long)]
        player_last: String,
        /// Destination team (name or numeric ID).
        #[arg(long)]
        team: String,
        /// Reference save to copy CRCs from (packed .bin or raw .db auto-detected).
        #[arg(long)]
        reference: Option<PathBuf>,
        /// Skip CRC copy. Only use when confident CRCs aren't needed.
        #[arg(long, default_value_t = false)]
        no_crcs: bool,
        #[arg(short, long)]
        output: PathBuf,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Unpack { input, output } => unpack_command(input, output),
        Commands::Pack {
            input,
            template,
            field_0x2c,
            output,
        } => pack_command(input, template, field_0x2c, output),
        Commands::PackFdeflate {
            input,
            template,
            field_0x2c,
            output,
        } => pack_fdeflate_command(input, template, field_0x2c, output),
        Commands::PackStored {
            input,
            template,
            output,
        } => pack_stored_command(input, template, output),
        Commands::Export { input, output } => export_command(input, output),
        Commands::Import {
            input,
            patches,
            output,
        } => import_command(input, patches, output),
        Commands::Reseal { input, output } => reseal_command(input, output),
        Commands::MovePlayer {
            input,
            player_first,
            player_last,
            team,
            reference,
            no_crcs,
            output,
        } => move_player_command(input, player_first, player_last, team, reference, no_crcs, output),
    }
}

fn unpack_command(input: PathBuf, output: PathBuf) -> Result<()> {
    let data = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let db = unpack(&data).context("unpack roster container")?;
    write_output(&output, &db)?;
    eprintln!(
        "wrote {} ({} bytes) from {}",
        output.display(),
        db.len(),
        input.display()
    );
    Ok(())
}

fn pack_stored_command(input: PathBuf, template: PathBuf, output: PathBuf) -> Result<()> {
    let db = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let template_bytes =
        fs::read(&template).with_context(|| format!("read template {}", template.display()))?;

    let packed = pack_stored(&db, &template_bytes).context("pack stored roster container")?;

    write_output(&output, &packed)?;
    eprintln!(
        "wrote {} ({} bytes) from {} (stored, template {})",
        output.display(),
        packed.len(),
        input.display(),
        template.display()
    );
    Ok(())
}

fn pack_fdeflate_command(
    input: PathBuf,
    template: PathBuf,
    field_0x2c: Option<String>,
    output: PathBuf,
) -> Result<()> {
    let db = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let template_bytes =
        fs::read(&template).with_context(|| format!("read template {}", template.display()))?;

    let f2c = match field_0x2c {
        Some(hex) => parse_hex_u32(&hex).with_context(|| format!("parse field_0x2c {hex}"))?,
        None => {
            let hdr = roster_container::RosterHeader::parse(&template_bytes)?;
            hdr.field_0x2c
        }
    };

    let packed = pack_with_fdeflate(&db, &template_bytes, f2c)
        .context("pack fdeflate roster container")?;

    write_output(&output, &packed)?;
    eprintln!(
        "wrote {} ({} bytes) from {} (fdeflate, template {})",
        output.display(),
        packed.len(),
        input.display(),
        template.display()
    );
    Ok(())
}

fn pack_command(
    input: PathBuf,
    template: PathBuf,
    field_0x2c: Option<String>,
    output: PathBuf,
) -> Result<()> {
    let db = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let template_bytes =
        fs::read(&template).with_context(|| format!("read template {}", template.display()))?;

    let packed = match field_0x2c {
        Some(hex) => {
            let value = parse_hex_u32(&hex).with_context(|| format!("parse field_0x2c {hex}"))?;
            pack_with_field_0x2c(&db, &template_bytes, value)
        }
        None => pack(&db, &template_bytes),
    }
    .context("pack roster container")?;

    write_output(&output, &packed)?;
    eprintln!(
        "wrote {} ({} bytes) from {} (template {})",
        output.display(),
        packed.len(),
        input.display(),
        template.display()
    );
    Ok(())
}

fn export_command(input: PathBuf, output: PathBuf) -> Result<()> {
    let db = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let export = export_roster(&db).context("export roster JSON")?;
    let json = serde_json::to_string_pretty(&export).context("serialize JSON")?;
    write_output(&output, json.as_bytes())?;
    eprintln!(
        "exported {} players, {} teams -> {}",
        export.players.len(),
        export.teams.len(),
        output.display()
    );
    Ok(())
}

fn import_command(input: PathBuf, patches: PathBuf, output: PathBuf) -> Result<()> {
    let mut db = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let patch_json =
        fs::read_to_string(&patches).with_context(|| format!("read {}", patches.display()))?;
    let import: RosterExport =
        serde_json::from_str(&patch_json).context("parse roster JSON patches")?;
    let applied = apply_import(&mut db, &import).context("apply roster import")?;
    write_output(&output, &db)?;
    eprintln!(
        "applied {} proteam patch(es) -> {}",
        applied.len(),
        output.display()
    );
    Ok(())
}

fn reseal_command(input: PathBuf, output: PathBuf) -> Result<()> {
    let mut db = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    reseal_checksums(&mut db).context("reseal TDB checksums")?;
    write_output(&output, &db)?;
    eprintln!(
        "resealed TDB CRCs -> {} ({} bytes)",
        output.display(),
        db.len()
    );
    Ok(())
}

fn parse_hex_u32(hex: &str) -> Result<u32> {
    let stripped = hex.strip_prefix("0x").unwrap_or(hex);
    u32::from_str_radix(stripped, 16).context("invalid hex u32")
}

fn move_player_command(
    input: PathBuf,
    player_first: String,
    player_last: String,
    team: String,
    reference: Option<PathBuf>,
    no_crcs: bool,
    output: PathBuf,
) -> Result<()> {
    let packed = fs::read(&input).with_context(|| format!("read {}", input.display()))?;

    let player = move_player::KNOWN_PLAYERS
        .iter()
        .find(|p| {
            p.first_name.eq_ignore_ascii_case(&player_first)
                && p.last_name.eq_ignore_ascii_case(&player_last)
        })
        .with_context(|| {
            format!(
                "player {} {} not found in known players list (available: {})",
                player_first,
                player_last,
                move_player::KNOWN_PLAYERS
                    .iter()
                    .map(|p| format!("{} {}", p.first_name, p.last_name))
                    .collect::<Vec<_>>()
                    .join(", ")
            )
        })?;

    let team_id = move_player::find_team(&team)
        .with_context(|| format!("unknown team: {team}"))?;

    let reference_db = if no_crcs {
        None
    } else {
        match reference {
            Some(ref_path) => {
                let ref_data = fs::read(&ref_path)
                    .with_context(|| format!("read reference {}", ref_path.display()))?;
                // Auto-detect: if starts with RosterFile magic, unpack it
                let ref_db = if ref_data.starts_with(b"RosterFile") {
                    let ref_header = roster_container::RosterHeader::parse(&ref_data)
                        .context("parse reference header")?;
                    let mut dec = flate2::read::ZlibDecoder::new(
                        &ref_data[ref_header.payload_offset..],
                    );
                    let mut db = Vec::new();
                    dec.read_to_end(&mut db)
                        .with_context(|| format!("decompress reference {}", ref_path.display()))?;
                    db
                } else {
                    // Assume raw .db
                    ref_data.to_vec()
                };
                Some(ref_db)
            }
            None => None,
        }
    };

    let result = move_player::build_move(&packed, player, team_id, reference_db.as_deref())
        .context("build player move")?;

    write_output(&output, &result)?;
    eprintln!(
        "moved {} {} to team {} -> {} ({} bytes)",
        player_first,
        player_last,
        team_id,
        output.display(),
        result.len()
    );
    Ok(())
}

fn write_output(output: &PathBuf, bytes: &[u8]) -> Result<()> {
    if let Some(parent) = output.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)
                .with_context(|| format!("create output directory {}", parent.display()))?;
        }
    }
    fs::write(output, bytes).with_context(|| format!("write {}", output.display()))?;
    Ok(())
}

mod move_player;
mod roster_db;

use std::fs;
use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use roster_container::{pack, unpack};
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
    /// Apply player proteam patches from JSON onto default.db.
    Import {
        input: PathBuf,
        patches: PathBuf,
        #[arg(short, long)]
        output: PathBuf,
    },
    /// Move a player to a new team.
    MovePlayer {
        /// Packed roster save input (e.g., TRADEEDIT5).
        input: PathBuf,
        /// Player first name.
        #[arg(long)]
        first: String,
        /// Player last name.
        #[arg(long)]
        last: String,
        /// Destination team: numeric ID, abbreviation (CBJ, BOS), or full name.
        #[arg(long)]
        team: String,
        #[arg(short, long)]
        output: PathBuf,
    },
    /// Recompute TDB internal CRCs on an extracted default.db.
    Reseal {
        input: PathBuf,
        #[arg(short, long)]
        output: PathBuf,
        #[arg(long, default_value_t = false)]
        ms_only: bool,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Unpack { input, output } => unpack_command(input, output),
        Commands::Pack { input, template, output } => pack_command(input, template, output),
        Commands::Export { input, output } => export_command(input, output),
        Commands::Import { input, patches, output } => import_command(input, patches, output),
        Commands::MovePlayer { input, first, last, team, output } => move_player_command(input, first, last, team, output),
        Commands::Reseal { input, output, ms_only } => reseal_command(input, output, ms_only),
    }
}

fn unpack_command(input: PathBuf, output: PathBuf) -> Result<()> {
    let data = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let db = unpack(&data).context("unpack roster container")?;
    write_output(&output, &db)?;
    eprintln!("wrote {} ({} bytes) from {}", output.display(), db.len(), input.display());
    Ok(())
}

fn pack_command(input: PathBuf, template: PathBuf, output: PathBuf) -> Result<()> {
    let db = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let template_bytes = fs::read(&template).with_context(|| format!("read template {}", template.display()))?;
    let header = roster_container::RosterHeader::parse(&template_bytes)?;
    let packed = pack(&db, &template_bytes, header.field_0x2c).context("pack roster container")?;
    write_output(&output, &packed)?;
    eprintln!("wrote {} ({} bytes) from {} (template {})", output.display(), packed.len(), input.display(), template.display());
    Ok(())
}

fn export_command(input: PathBuf, output: PathBuf) -> Result<()> {
    let db = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let export = export_roster(&db).context("export roster JSON")?;
    let json = serde_json::to_string_pretty(&export).context("serialize JSON")?;
    write_output(&output, json.as_bytes())?;
    eprintln!("exported {} players, {} teams -> {}", export.players.len(), export.teams.len(), output.display());
    Ok(())
}

fn import_command(input: PathBuf, patches: PathBuf, output: PathBuf) -> Result<()> {
    let mut db = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let patch_json = fs::read_to_string(&patches).with_context(|| format!("read {}", patches.display()))?;
    let import: RosterExport = serde_json::from_str(&patch_json).context("parse roster JSON patches")?;
    let applied = apply_import(&mut db, &import).context("apply roster import")?;
    write_output(&output, &db)?;
    eprintln!("applied {} proteam patch(es) -> {}", applied.len(), output.display());
    Ok(())
}

fn reseal_command(input: PathBuf, output: PathBuf, ms_only: bool) -> Result<()> {
    let mut db = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    if ms_only {
        ea_tdb::reseal_ms_crcs(&mut db).context("reseal MS CRCs")?;
    } else {
        ea_tdb::reseal_checksums(&mut db).context("reseal TDB checksums")?;
    }
    write_output(&output, &db)?;
    eprintln!("resealed -> {} ({} bytes)", output.display(), db.len());
    Ok(())
}

fn move_player_command(
    input: PathBuf,
    first: String,
    last: String,
    team: String,
    output: PathBuf,
) -> Result<()> {
    let packed = fs::read(&input).with_context(|| format!("read {}", input.display()))?;

    let team_id: u8 = if let Ok(id) = team.parse() {
        id
    } else {
        roster_db::find_team(&team)
            .map(|t| t.id)
            .with_context(|| format!("unknown team: {team}"))?
    };

    let moves = [move_player::PlayerMove { first_name: first, last_name: last, team_id }];
    let result = move_player::build_moves(&packed, &moves).context("build player move")?;

    write_output(&output, &result)?;
    eprintln!("moved to team {team_id} -> {} ({} bytes)", output.display(), result.len());
    Ok(())
}

fn write_output(output: &PathBuf, bytes: &[u8]) -> Result<()> {
    if let Some(parent) = output.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).with_context(|| format!("create output directory {}", parent.display()))?;
        }
    }
    fs::write(output, bytes).with_context(|| format!("write {}", output.display()))?;
    Ok(())
}

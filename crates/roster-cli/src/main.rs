use std::fs;
use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use roster_container::{pack, pack_unchanged, unpack};

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
            output,
        } => pack_command(input, template, output),
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

fn pack_command(input: PathBuf, template: PathBuf, output: PathBuf) -> Result<()> {
    let db = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let template_bytes =
        fs::read(&template).with_context(|| format!("read template {}", template.display()))?;

    let packed = pack(&db, &template_bytes)
        .or_else(|e| {
            if e.to_string().contains("checksum") {
                pack_unchanged(&db, &template_bytes).context(
                    "pack failed: edited DB requires container checksum (not implemented); \
                     template DB must be unchanged",
                )
            } else {
                Err(anyhow::Error::from(e))
            }
        })
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

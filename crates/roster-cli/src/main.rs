use std::fs;
use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use roster_container::unpack;

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
        /// Input roster save (inner RosterFile blob).
        input: PathBuf,
        /// Output path for the extracted default.db TDB file.
        #[arg(short, long)]
        output: PathBuf,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Unpack { input, output } => unpack_command(input, output),
    }
}

fn unpack_command(input: PathBuf, output: PathBuf) -> Result<()> {
    let data = fs::read(&input).with_context(|| format!("read {}", input.display()))?;
    let db = unpack(&data).context("unpack roster container")?;
    if let Some(parent) = output.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)
                .with_context(|| format!("create output directory {}", parent.display()))?;
        }
    }
    fs::write(&output, &db).with_context(|| format!("write {}", output.display()))?;
    eprintln!(
        "wrote {} ({} bytes) from {}",
        output.display(),
        db.len(),
        input.display()
    );
    Ok(())
}

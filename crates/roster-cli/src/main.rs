use std::fs;
use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use roster_container::{pack, pack_with_field_0x2c, unpack};

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

fn parse_hex_u32(hex: &str) -> Result<u32> {
    let stripped = hex.strip_prefix("0x").unwrap_or(hex);
    u32::from_str_radix(stripped, 16).context("invalid hex u32")
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

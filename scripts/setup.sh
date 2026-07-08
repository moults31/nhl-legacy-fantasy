#!/usr/bin/env bash
set -euo pipefail

# CI runners don't have Rust; skip the mule build (not needed for lint/build/test).
if [ -n "${CI:-}" ]; then
  echo "[nlf] CI environment detected, skipping mule binary build"
  exit 0
fi

# Build the mule CLI binary from the pinned git repo into a local directory.
# Skip if the binary already exists (e.g. not a fresh install).

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/.cargo-bin/bin/roster-cli"

if [ -x "$BIN" ]; then
  echo "[nlf] roster-cli already installed at $BIN"
  exit 0
fi

echo "[nlf] building roster-cli from nhl-db-studio-mule (main) ..."
cargo install \
  --git https://github.com/moults31/nhl-db-studio-mule \
  --branch main \
  roster-cli \
  --root "$ROOT/.cargo-bin"

echo "[nlf] roster-cli installed at $BIN"

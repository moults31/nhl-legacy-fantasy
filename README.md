# NHL Legacy Fantasy

A mostly-offline social fantasy-hockey style game built around **NHL Legacy Edition**.

Players manage rosters and compete with friends without depending on live online services. The game uses NHL Legacy as the on-ice presentation layer: custom rosters are authored here and loaded into a local Legacy install so matches and seasons can be played in the real game client.

This repository is the home for that fantasy layer and the tools that connect it to Legacy.

## Development setup

See [docs/PLAN.md](docs/PLAN.md) for scope and milestones. Local reference material lives under `_local/` (symlinks documented in [AGENTS.md](AGENTS.md)); see [docs/MODDING-TOOLS.md](docs/MODDING-TOOLS.md) for what each bundled tool contributes.

### Build and test

1. Copy a roster save fixture per [tests/fixtures/README.md](tests/fixtures/README.md).
2. Run tests:

   ```bash
   cargo test
   ```

3. Unpack a save to `default.db`:

   ```bash
   cargo run -p roster-cli -- unpack tests/fixtures/xbox/roster.bin -o default.db
   ```

### Crates

| Crate | Role |
|-------|------|
| `roster-container` | `RosterFile` pack/unpack (milestone 1) |
| `roster-cli` | Command-line interface |


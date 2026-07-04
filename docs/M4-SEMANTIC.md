# Milestone 4: Semantic JSON export/import

Scope from [PLAN.md](PLAN.md): map TDB tables to players and teams; JSON for fantasy automation.

## Status

| Item | Status |
|------|--------|
| `roster-semantic` crate | **In progress** |
| Export players (`cPbu`) | **Done** — first/last name, `proteam` (`WBbd`), record index |
| Export teams (`ttOk`) | **Done** — city, full name, abbrev, record index |
| Import proteam patches | **Done** — match by record or name, write `WBbd` |
| Ratings / lines / roster slots | **Not started** |
| Pack edited DB to loadable save | **Blocked** — M2/M5 edited repack gate |

## Legacy table ids

NHL 14 EADBEditor uses `ubPc` / `kOtt`; Legacy roster saves use internal ids:

| Semantic | Legacy id | Notes |
|----------|-----------|-------|
| Player bios | `cPbu` | Exhibition player bio |
| Teams | `ttOk` | 252 rows; city in `ITNQ`, abbrev in `RPbr` |
| Pro team assignment | `cPbu.WBbd` | In-game **Player Movement** field (`proteam`) |

Field ids within those tables match the EA dictionary where layouts align (`PedH` first name, `RMbQ` last name, etc.).

## JSON schema (`nhl-legacy-roster/0.1`)

```json
{
  "schema": "nhl-legacy-roster/0.1",
  "teams": [
    { "record": 0, "city": "Anaheim", "abbrev": "ANA", "full_name": "Anaheim Ducks®" }
  ],
  "players": [
    { "record": 1424, "first_name": "Mason", "last_name": "McTavish", "proteam": 1 }
  ]
}
```

`proteam` is the numeric `WBbd` value (not necessarily the `ttOk` record index). Import currently applies **proteam-only** patches; other fields are ignored.

## CLI

```bash
cargo run -p roster-cli -- export -o /tmp/roster.json _local/unpacked/default.db
cargo run -p roster-cli -- import -o /tmp/edited.db _local/unpacked/default.db /tmp/patches.json
```

Import JSON may contain a subset of players (only listed rows are patched).

## Tests

`crates/roster-semantic/tests/mctavish_export.rs` uses `_local/game-saves/xbox/{roster1,testroster}.bin` when present.

## Next steps

1. Map `proteam` ↔ team display names (join table TBD; `ttOk` record index ≠ `proteam`)
2. Export/import ratings (`dSvy` / `mHuy` Legacy ids TBD)
3. Wire export → import → pack once M5 edited repack gate clears

//! Semantic JSON export/import for NHL Legacy roster saves (M4).
//!
//! Legacy roster `default.db` files use internal table ids (`cPbu`, `ttOk`, …)
//! rather than the NHL 14 names in EADBEditor (`ubPc`, `kOtt`). Field ids within
//! those tables match the EA dictionary where the layout is shared.

mod export;
mod import;
mod legacy;
mod string_field;

pub use export::{export_roster, PlayerExport, RosterExport, TeamExport};
pub use import::{apply_import, ImportPatch};
pub use legacy::LegacyRosterTables;
pub use string_field::read_string_field;

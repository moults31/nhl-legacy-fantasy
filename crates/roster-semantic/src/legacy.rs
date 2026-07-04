//! Legacy roster save table and field ids (2026-07 fixtures).

/// Known Legacy roster table ids and player/team field names.
pub struct LegacyRosterTables;

impl LegacyRosterTables {
    pub const PLAYER_BIO: &'static str = "cPbu";
    pub const TEAMS: &'static str = "ttOk";

    /// In-game player movement updates this field (`proteam`), not `BSXd` (`team`).
    pub const PLAYER_PROTEAM: &'static str = "WBbd";
    pub const PLAYER_FIRST_NAME: &'static str = "PedH";
    pub const PLAYER_LAST_NAME: &'static str = "RMbQ";

    pub const TEAM_CITY: &'static str = "ITNQ";
    pub const TEAM_FULL_NAME: &'static str = "JkmY";
    pub const TEAM_ABBREV: &'static str = "RPbr";
}

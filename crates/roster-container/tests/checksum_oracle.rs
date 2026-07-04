//! Verify container checksums against known-good saves.

use roster_container::verify_checksums;

fn oracle_paths() -> Vec<(&'static str, String)> {
    let mut paths = vec![
        (
            "fixture",
            concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../tests/fixtures/xbox/roster.bin"
            )
            .to_string(),
        ),
        (
            "roster1",
            concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../_local/game-saves/xbox/roster1.bin"
            )
            .to_string(),
        ),
        (
            "testroster",
            concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../_local/game-saves/xbox/testroster.bin"
            )
            .to_string(),
        ),
    ];

    let vanilla = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../_local/modding-tools/NHL Modding Studio 0.1.0-beta.3 portable/vanilla-saves/360/ROSTER 20260531190619/ROSTER 20260531190619"
    );
    if std::path::Path::new(vanilla).exists() {
        paths.push(("vanilla_ms_360", vanilla.to_string()));
    }

    paths
}

#[test]
fn oracle_saves_verify() {
    for (name, path) in oracle_paths() {
        let Ok(data) = std::fs::read(&path) else {
            eprintln!("skip {name}: {path}");
            continue;
        };
        verify_checksums(&data).unwrap_or_else(|e| panic!("{name}: {e}"));
    }
}

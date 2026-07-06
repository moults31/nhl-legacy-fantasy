/// Verify that BERGERON-generated TDB passes checksum verification.
/// Run with: cargo test -p roster-cli --test verify_bergeron -- --nocapture
use std::path::Path;

use ea_tdb::{reseal_checksums, verify_checksums};

#[test]
fn bergeron_tdb_self_verifies() {
    let base = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("_local/game-saves/checkpoint");

    // The resealed.db is what we packed into bergeron_col.bin
    let resealed_path = base.join("resealed.db");
    if !resealed_path.exists() {
        eprintln!("SKIP: resealed.db not found");
        return;
    }
    let mut db = std::fs::read(&resealed_path).expect("read resealed.db");
    
    verify_checksums(&db).expect("resealed.db should pass verify_checksums");

    // Re-reseal and verify it's idempotent
    let before = db.clone();
    reseal_checksums(&mut db).expect("re-reseal");
    assert_eq!(db, before, "re-reseal should be idempotent");

    // Now check the packed bin too — unpack it and verify
    let bin_path = base.join("bergeron_col.bin");
    if bin_path.exists() {
        let container = std::fs::read(&bin_path).expect("read bergeron_col.bin");
        let unpacked = roster_container::unpack(&container).expect("unpack bergeron");
        verify_checksums(&unpacked).expect("unpacked bergeron should pass verify_checksums");
    }

    eprintln!("All BERGERON TDB checks passed");
}

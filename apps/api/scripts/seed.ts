import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { getDb } from "../src/db.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

function main() {
  const db = getDb();
  const schemaSql = readFileSync(join(__dirname, "../data/schema.sql"), "utf8");
  const seedSql = readFileSync(join(__dirname, "../data/seed.sql"), "utf8");
  db.exec(schemaSql);
  db.exec(seedSql);
  console.log("Database seeded.");
}

main();

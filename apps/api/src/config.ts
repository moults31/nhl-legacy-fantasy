import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

export const config = {
  port: Number(process.env.PORT ?? 3001),
  databaseUrl: process.env.DATABASE_URL ?? join(__dirname, "../data/dev.db"),
  muleBinary: process.env.MULE_BINARY ?? join(__dirname, "../../../_local/nhl-db-studio-mule/target/release/roster-cli"),
  vanillaRosterBin: process.env.VANILLA_ROSTER_BIN ?? join(__dirname, "../../../_local/vanilla-roster.bin"),
  corsOrigin: process.env.CORS_ORIGIN ?? "http://localhost:5173",
  rosterOutputDir: join(__dirname, "../data/rosters"),
  /** Xenia save root — parent of 00000001/ and Headers/. */
  xeniaSaveRoot: process.env.XENIA_SAVE_ROOT ??
    join(process.env.USERPROFILE ?? "C:/Users/galileo", "Documents/nhllegacy/B13EBABEBABEBABE/454109EC"),
};

export function assertConfig(): void {
  if (!config.vanillaRosterBin) {
    throw new Error(
      "VANILLA_ROSTER_BIN is required. Set it to the path of a vanilla NHL Legacy roster .bin file."
    );
  }
}

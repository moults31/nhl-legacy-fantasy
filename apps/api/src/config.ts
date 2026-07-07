import { dirname, join } from "node:path";
import { homedir, platform } from "node:os";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

function resolveXeniaDefault(): string {
  if (process.env.XENIA_SAVE_ROOT) return process.env.XENIA_SAVE_ROOT;
  if (platform() === "linux") {
    return join(
      homedir(),
      ".steam/steam/steamapps/compatdata/3623314720/pfx/drive_c/users/steamuser/Documents/nhllegacy/B13EBABEBABEBABE/454109EC"
    );
  }
  return join(
    process.env.USERPROFILE ?? "C:/Users/galileo",
    "Documents/nhllegacy/B13EBABEBABEBABE/454109EC"
  );
}

export const config = {
  port: Number(process.env.PORT ?? 3001),
  databaseUrl: process.env.DATABASE_URL ?? join(__dirname, "../data/dev.db"),
  muleBinary: process.env.MULE_BINARY ?? join(__dirname, "../../../.cargo-bin/bin/roster-cli"),
  vanillaRosterBin: process.env.VANILLA_ROSTER_BIN ?? join(__dirname, "../../../tests/fixtures/xbox/roster.bin"),
  corsOrigin: process.env.CORS_ORIGIN ?? "http://localhost:5173",
  rosterOutputDir: join(__dirname, "../data/rosters"),
  xeniaSaveRoot: process.env.XENIA_SAVE_ROOT ?? resolveXeniaDefault(),
};

export function assertConfig(): void {
  if (!config.vanillaRosterBin) {
    throw new Error(
      "VANILLA_ROSTER_BIN is required. Set it to the path of a vanilla NHL Legacy roster .bin file."
    );
  }
}

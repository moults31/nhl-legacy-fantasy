import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { config } from "./config.js";
import type { SrV1Roster } from "@nlf/spec-client";

interface ExecResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

function execMule(args: string[]): Promise<ExecResult> {
  return new Promise((resolve, reject) => {
    const proc = spawn(config.muleBinary, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    proc.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    proc.on("error", reject);
    proc.on("close", (exitCode) => {
      resolve({ stdout, stderr, exitCode: exitCode ?? -1 });
    });
  });
}

/**
 * Apply an SR v1 roster patch to a vanilla roster and pack a game-ready .bin.
 *
 * This is the core producer step: WR -> SR -> mule CLI -> .bin.
 */
export async function packRoster(sr: SrV1Roster): Promise<Buffer> {
  if (!config.vanillaRosterBin) {
    throw new Error("VANILLA_ROSTER_BIN is not configured");
  }

  await mkdir(config.rosterOutputDir, { recursive: true });
  const workDir = await mkdtemp(join(tmpdir(), "nlf-roster-"));

  try {
    const vanillaDbPath = join(workDir, "default.db");
    const editedDbPath = join(workDir, "edited.db");
    const srPath = join(workDir, "roster.json");
    const outputBinPath = join(config.rosterOutputDir, `roster-${Date.now()}.bin`);

    // 1. Unpack the vanilla roster .bin -> default.db
    const unpackResult = await execMule([
      "unpack",
      config.vanillaRosterBin,
      "-o",
      vanillaDbPath,
    ]);
    if (unpackResult.exitCode !== 0) {
      throw new Error(
        `mule unpack failed (${unpackResult.exitCode}): ${unpackResult.stderr || unpackResult.stdout}`
      );
    }

    // 2. Write the SR patch and apply it -> edited.db
    await writeFile(srPath, JSON.stringify(sr, null, 2), "utf8");
    const importResult = await execMule([
      "import",
      "-o",
      editedDbPath,
      vanillaDbPath,
      srPath,
    ]);
    if (importResult.exitCode !== 0) {
      throw new Error(
        `mule import failed (${importResult.exitCode}): ${importResult.stderr || importResult.stdout}`
      );
    }

    // 3. Pack the edited DB -> .bin
    const packResult = await execMule(["pack-fdeflate", editedDbPath, "-o", outputBinPath]);
    if (packResult.exitCode !== 0) {
      throw new Error(
        `mule pack-fdeflate failed (${packResult.exitCode}): ${packResult.stderr || packResult.stdout}`
      );
    }

    return await readFile(outputBinPath);
  } finally {
    // Intentionally leaving workDir for debugging; production should clean it.
    // eslint-disable-next-line no-console
    console.debug("mule work dir:", workDir);
  }
}

export function getMuleVersion(): Promise<ExecResult> {
  return execMule(["--version"]);
}

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
 * The mule's `patch-roster` command applies proteam changes correctly —
 * including the full set of on-disk edits the game requires (team_alt
 * metadata, eGlu slot management, edit-log entries, and checksum reseals)
 * that the old `import` + `pack` pipeline was missing.
 *
 * These implementation details leak into this comment intentionally: they
 * document a hard-won debugging lesson (the specific omission categories
 * that produced in-game corruption) so future maintainers can recognize the
 * pattern.  The webapp itself only depends on the SR v1 contract — the
 * comment is a guardrail, not a coupling.
 */
export async function packRoster(sr: SrV1Roster): Promise<Buffer> {
  if (!config.vanillaRosterBin) {
    throw new Error("VANILLA_ROSTER_BIN is not configured");
  }

  await mkdir(config.rosterOutputDir, { recursive: true });
  const workDir = await mkdtemp(join(tmpdir(), "nlf-roster-"));

  try {
    const srPath = join(workDir, "roster.json");
    const outputBinPath = join(config.rosterOutputDir, `roster-${Date.now()}.bin`);

    // 1. Write the SR patch file.
    await writeFile(srPath, JSON.stringify(sr, null, 2), "utf8");

    // 2. Apply patches with full move logic and pack in one step.
    const result = await execMule([
      "patch-roster",
      config.vanillaRosterBin,
      srPath,
      "-o",
      outputBinPath,
    ]);
    if (result.exitCode !== 0) {
      throw new Error(
        `mule patch-roster failed (${result.exitCode}): ${result.stderr || result.stdout}`
      );
    }

    return await readFile(outputBinPath);
  } finally {
    // eslint-disable-next-line no-console
    console.debug("mule work dir:", workDir);
  }
}

export function getMuleVersion(): Promise<ExecResult> {
  return execMule(["--version"]);
}

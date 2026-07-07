import { readFile, writeFile, mkdir } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync } from "node:fs";
import { config } from "./config.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Xenia / NHL Legacy save naming constraint.
 *
 * The game only recognizes roster saves whose **filesystem folder name**
 * matches the pattern `ROSTER YYYYMMDDHHmmss`.  Saves with any other
 * folder name are silently invisible in the in-game load/save list,
 * regardless of header content or .bin validity.
 *
 * The **display name** in the .header (UTF-16LE at offset 0x09, max 11
 * chars) is independent — it controls the label the user sees in-game and
 * can be any string.  The **folder name** in the .header (ASCII at offset
 * 0x108) must match the filesystem folder name.
 *
 * @see {@link nextSaveName} for the generator that enforces this.
 * @see {@link SAVE_NAME_PATTERN} for the validation regex.
 */
const SAVE_NAME_PATTERN = /^ROSTER \d{14}(?:\d{2})?$/;

/**
 * Validate that a save name conforms to the required filesystem naming.
 * Throws if the name would be invisible to the game.
 */
function assertValidSaveName(name: string): void {
  if (!SAVE_NAME_PATTERN.test(name)) {
    throw new Error(
      `Save name "${name}" does not match required pattern "ROSTER YYYYMMDDHHmmss". ` +
      `Saves with non-conforming folder names are invisible to the game.`
    );
  }
}

/**
 * Build an Xenia STFS .header sidecar from the template, patching in a
 * display name and folder name.
 *
 * Template layout (328 bytes):
 *   offset 0x09–0x21: UTF-16LE display name (24 bytes)
 *   offset 0x108–0x128: ASCII folder name (32 bytes)
 */
async function buildHeader(folderName: string, displayName: string): Promise<Buffer> {
  const templatePath = join(__dirname, "../../../_local/game-saves/xbox/template.header");
  const template = await readFile(templatePath);

  if (template.length < 0x128) {
    throw new Error("header template too small");
  }

  const buf = Buffer.from(template);

  // Write UTF-16LE display name at offset 9 (max 11 chars + null)
  const utf16Buffer = Buffer.from(displayName + "\0", "ucs2");
  const nameLen = Math.min(utf16Buffer.length, 24);
  buf.fill(0, 9, 33);
  utf16Buffer.copy(buf, 9, 0, nameLen);

  // Write ASCII folder name at offset 0x108 (max 31 chars + null)
  const asciiBuffer = Buffer.from(folderName + "\0", "ascii");
  const asciiLen = Math.min(asciiBuffer.length, 32);
  buf.fill(0, 0x108, 0x128);
  asciiBuffer.copy(buf, 0x108, 0, asciiLen);

  return buf;
}

/**
 * Find the next available save name that the game will actually recognize.
 *
 * **Critical constraint**: Xenia/NHL Legacy only detects saves whose
 * filesystem folder name matches `ROSTER YYYYMMDDHHmmss`.  Any other
 * format is invisible to the game, regardless of .header content.
 *
 * This generator always produces conforming names.  It uses the current
 * UTC timestamp and appends a 2-digit collision counter (`00`–`99`) when
 * a save already exists at that timestamp.
 */
function nextSaveName(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const base = [
    now.getUTCFullYear(),
    pad(now.getUTCMonth() + 1),
    pad(now.getUTCDate()),
    pad(now.getUTCHours()),
    pad(now.getUTCMinutes()),
    pad(now.getUTCSeconds()),
  ].join("");

  const saveDir = join(config.xeniaSaveRoot, "00000001");
  const headersDir = join(config.xeniaSaveRoot, "Headers", "00000001");

  let name = `ROSTER ${base}`;
  let counter = 0;
  while (true) {
    const candidate = counter === 0 ? name : `${name}${String(counter).padStart(2, "0")}`;
    const savePath = join(saveDir, candidate);
    const headerPath = join(headersDir, `${candidate}.header`);
    if (!existsSync(savePath) && !existsSync(headerPath)) {
      assertValidSaveName(candidate);
      return candidate;
    }
    counter++;
    if (counter > 99) {
      throw new Error("unable to find unique save name after 100 attempts");
    }
  }
}

/**
 * Scan existing installed saves for WEBAPP display names and return the next
 * available number.  Reads the display name from each .header file at offset
 * 0x09 (UTF-16LE).
 *
 * Unrelated saves (e.g. "ROSTER 2026…") are ignored — only files whose
 * display name starts with "WEBAPP" are counted.
 */
async function nextWebappLabel(): Promise<string> {
  const headersDir = join(config.xeniaSaveRoot, "Headers", "00000001");
  let maxN = 0;

  try {
    const { readdir } = await import("node:fs/promises");
    const entries = await readdir(headersDir);
    for (const entry of entries) {
      if (!entry.endsWith(".header")) continue;
      try {
        const raw = await readFile(join(headersDir, entry));
        if (raw.length < 33) continue;
        // UTF-16LE display name at offset 9, 24 bytes
        const label = raw.subarray(9, 33)
          .toString("utf16le")
          .split("\0")[0];
        const m = /^WEBAPP(\d+)$/.exec(label);
        if (m) {
          const n = parseInt(m[1], 10);
          if (n > maxN) maxN = n;
        }
      } catch {
        // corrupt or unreadable header — skip
      }
    }
  } catch {
    // headers dir missing — start at 1
  }

  return `WEBAPP${maxN + 1}`;
}

export interface InstallResult {
  /** The generated save folder name. */
  saveName: string;
  /** Full path to the .bin file. */
  binPath: string;
  /** Full path to the .header file. */
  headerPath: string;
}

/**
 * Install a roster .bin into the Xenia NHL Legacy save directory.
 *
 * Creates the save folder, copies the .bin (named to match the folder),
 * and writes a companion .header sidecar.
 *
 * @param bin        The packed RosterFile .bin buffer.
 * @param label      Optional in-game display label (max 11 chars, truncated
 *                   if longer). Defaults to the first 11 chars of the save
 *                   folder name (e.g. "ROSTER 2026").
 */
export async function installRoster(
  bin: Buffer,
  label?: string,
): Promise<InstallResult> {
  if (!config.xeniaSaveRoot) {
    throw new Error("XENIA_SAVE_ROOT is not configured");
  }

  const saveName = nextSaveName();
  assertValidSaveName(saveName);

  const displayName = label
    ? label.substring(0, 11)
    : (await nextWebappLabel()).substring(0, 11);

  // Save directory: <root>/00000001/<saveName>/
  const saveDir = join(config.xeniaSaveRoot, "00000001", saveName);
  const binPath = join(saveDir, saveName);

  // Headers directory: <root>/Headers/00000001/<saveName>.header
  const headersDir = join(config.xeniaSaveRoot, "Headers", "00000001");
  const headerPath = join(headersDir, `${saveName}.header`);

  await mkdir(saveDir, { recursive: true });
  await mkdir(headersDir, { recursive: true });

  await writeFile(binPath, bin);

  const header = await buildHeader(saveName, displayName);
  await writeFile(headerPath, header);

  return { saveName, binPath, headerPath };
}

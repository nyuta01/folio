import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from "electron";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { delimiter as PATH_DELIM } from "node:path";
import { fileURLToPath } from "node:url";

import { createServerManager, type ServerManager } from "./server-manager.js";

interface Settings {
  lastSheet?: string;
  recentSheets?: string[];
}

// dist/main/main.js → up 4 levels = repo root (dist/main → dist → desktop → apps → repo).
const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..", "..", "..");
// In dev (source checkout), the renderer assets sit at <repo>/viewer/dist.
// When packaged by electron-builder, they're copied into the app's resources
// dir as `viewer-dist/` (configured via `extraResources` in package.json).
const devStaticDir = join(repoRoot, "viewer", "dist");
const packagedStaticDir = join(process.resourcesPath, "viewer-dist");
const venvBin = join(repoRoot, ".venv", "bin", "folio-viewer");
const settingsFile = join(app.getPath("userData"), "settings.json");
const preloadEntry = join(here, "..", "preload", "preload.cjs");
const RECENT_LIMIT = 8;

let serverManager: ServerManager | null = null;
let mainWindow: BrowserWindow | null = null;
let currentSheet: string | null = null;
const recentLogs: string[] = [];

function logLine(line: string): void {
  const stamped = `${new Date().toLocaleTimeString()} ${line}`;
  console.log(stamped);
  recentLogs.unshift(stamped);
  recentLogs.splice(120);
}

function readSettings(): Settings {
  try {
    return JSON.parse(readFileSync(settingsFile, "utf8")) as Settings;
  } catch {
    return {};
  }
}

function writeSettings(next: Settings): void {
  try {
    mkdirSync(app.getPath("userData"), { recursive: true });
    writeFileSync(settingsFile, JSON.stringify(next, null, 2));
  } catch (err) {
    console.error("failed to persist settings", err);
  }
}

function rememberSheet(sheet: string): string[] {
  const settings = readSettings();
  const existing = settings.recentSheets ?? [];
  const recent = [sheet, ...existing.filter((p) => p !== sheet)].slice(
    0,
    RECENT_LIMIT,
  );
  writeSettings({ ...settings, lastSheet: sheet, recentSheets: recent });
  return recent;
}

function getRecentSheets(): string[] {
  const list = readSettings().recentSheets ?? [];
  return list.filter((p) => existsSync(p));
}

function isValidSheet(dir: string): boolean {
  return existsSync(join(dir, "contract.yaml"));
}

// On macOS, GUI-launched apps inherit a minimal `PATH` that excludes the
// directories where pipx / `uv tool install` / Homebrew put binaries.
// Spawn the user's interactive shell once at startup to read the real PATH
// they see in Terminal, then prepend it to process.env.PATH. No-op on
// Windows (the launcher PATH there already covers user installs).
function augmentPathFromShell(): void {
  if (process.platform === "win32") return;
  if (process.env.FOLIO_SKIP_PATH_FIX === "1") return;
  const shell = process.env.SHELL || "/bin/zsh";
  try {
    const out = execFileSync(shell, ["-ilc", "echo $PATH"], {
      encoding: "utf8",
      timeout: 3000,
      stdio: ["ignore", "pipe", "pipe"],
    });
    const shellPath = out.trim();
    if (shellPath) {
      const current = process.env.PATH ?? "";
      const merged = shellPath + (current ? PATH_DELIM + current : "");
      process.env.PATH = merged;
      logLine(`PATH augmented from ${shell}: ${shellPath}`);
    }
  } catch (err) {
    logLine(
      `PATH augmentation skipped (could not read ${shell} -ilc): ${
        err instanceof Error ? err.message : String(err)
      }`,
    );
  }
}

function pipxOrUvCandidates(): string[] {
  const home = app.getPath("home");
  const exe = process.platform === "win32" ? "folio-viewer.exe" : "folio-viewer";
  const dirs = [
    // pipx and `uv tool install` both default to ~/.local/bin on Unix.
    join(home, ".local", "bin"),
    // Homebrew on Apple Silicon and Intel respectively.
    "/opt/homebrew/bin",
    "/usr/local/bin",
    // Common pyenv shims.
    join(home, ".pyenv", "shims"),
  ];
  if (process.platform === "win32") {
    dirs.push(
      join(process.env.USERPROFILE ?? home, ".local", "bin"),
      join(process.env.APPDATA ?? "", "Python", "Scripts"),
    );
  }
  return dirs.map((d) => join(d, exe));
}

function findFolioBin(): string {
  if (process.env.FOLIO_VIEWER_BIN) return process.env.FOLIO_VIEWER_BIN;
  // Source-checkout shortcut: the developer ran `uv sync` and is launching
  // from `apps/desktop/` via `npm start`. Skip it when the resolved path
  // would point inside a packaged-app bundle.
  if (!app.isPackaged && existsSync(venvBin)) return venvBin;
  for (const candidate of pipxOrUvCandidates()) {
    if (existsSync(candidate)) return candidate;
  }
  return "folio-viewer"; // last resort: rely on PATH lookup
}

function resolveStaticDir(): string | undefined {
  if (process.env.FOLIO_STATIC_DIR) return process.env.FOLIO_STATIC_DIR;
  if (app.isPackaged && existsSync(packagedStaticDir)) return packagedStaticDir;
  if (existsSync(devStaticDir)) return devStaticDir;
  return undefined;
}

async function pickSheet(initial?: string | undefined): Promise<string | null> {
  const opts: Electron.OpenDialogOptions = {
    title: "Open Folio Sheet",
    properties: ["openDirectory"],
    buttonLabel: "Open Sheet",
  };
  if (initial && existsSync(initial)) opts.defaultPath = initial;
  const result = await dialog.showOpenDialog(opts);
  if (result.canceled || result.filePaths.length === 0) return null;
  const dir = result.filePaths[0]!;
  if (!existsSync(join(dir, "contract.yaml"))) {
    const choice = await dialog.showMessageBox({
      type: "warning",
      message: "That folder does not contain a contract.yaml.",
      detail: `Picked: ${dir}\n\nA Folio sheet must contain contract.yaml at its root.`,
      buttons: ["Pick another", "Cancel"],
      defaultId: 0,
      cancelId: 1,
    });
    if (choice.response === 0) return pickSheet(dir);
    return null;
  }
  return dir;
}

async function startWithSheet(sheetPath: string): Promise<void> {
  const staticDir = resolveStaticDir();
  if (!staticDir) {
    logLine(
      app.isPackaged
        ? `WARNING: bundled viewer-dist not found at ${packagedStaticDir} — the packaged app is corrupt; reinstall.`
        : `WARNING: viewer/dist not found — run \`npm --prefix ${join(
            repoRoot,
            "viewer",
          )} run build\` first, or set FOLIO_STATIC_DIR.`,
    );
  }

  if (serverManager) {
    await serverManager.stop();
    serverManager = null;
  }

  const manager = createServerManager({
    bin: findFolioBin(),
    sheetPath,
    staticDir,
    onLog: logLine,
  });

  let url: string;
  try {
    url = await manager.start();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logLine(`failed to start folio-viewer: ${msg}`);
    const enoent =
      msg.includes("ENOENT") ||
      msg.includes("not found") ||
      msg.includes("spawn failed") ||
      msg.includes("exited before ready");
    const probedPaths = pipxOrUvCandidates();
    const lookupLines = [
      "  $FOLIO_VIEWER_BIN (env override)",
      ...(app.isPackaged
        ? []
        : [`  ${venvBin}  (source-checkout .venv)`]),
      ...probedPaths.map((p) => `  ${p}`),
      "  folio-viewer  (PATH lookup)",
    ];
    const detail = enoent
      ? [
          "The Folio Desktop app shells out to the `folio-viewer` Python CLI",
          "and could not find it on this machine.",
          "",
          "Locations checked:",
          ...lookupLines,
          "",
          "To install Folio:",
          "  pipx install folio       # recommended (lands in ~/.local/bin/)",
          "  uv tool install folio    # alternative",
          "",
          "After installing, click \"Try again\" — the app re-augments PATH from",
          "your interactive shell at every launch, so reopening should also work.",
          "",
          `Underlying error: ${msg}`,
        ].join("\n")
      : `${msg}\n\nMake sure the picked directory is a Folio sheet (contains contract.yaml).\n\nRecent logs:\n${recentLogs.slice(0, 8).join("\n")}`;
    const choice = await dialog.showMessageBox({
      type: "error",
      message: enoent
        ? "Folio is not installed on this machine"
        : "Could not start folio-viewer",
      detail,
      buttons: enoent
        ? ["Open install docs", "Try again", "Quit"]
        : ["OK"],
      defaultId: 0,
      cancelId: enoent ? 2 : 0,
    });
    if (enoent && choice.response === 0) {
      void shell.openExternal(
        "https://nyuta01.github.io/folio/get-started/installation/",
      );
    }
    if (enoent && choice.response === 1) {
      void startWithSheet(sheetPath);
    }
    if (enoent && choice.response === 2) {
      app.quit();
    }
    return;
  }

  serverManager = manager;
  currentSheet = sheetPath;
  rememberSheet(sheetPath);
  rebuildMenu();

  if (mainWindow && !mainWindow.isDestroyed()) {
    void mainWindow.loadURL(url);
    mainWindow.setTitle(`Folio · ${basename(sheetPath)}`);
  } else {
    createWindow(url, sheetPath);
  }
}

function createWindow(url: string, sheetPath: string): BrowserWindow {
  const title = `Folio · ${basename(sheetPath)}`;
  const window = new BrowserWindow({
    title,
    width: 1280,
    height: 820,
    minWidth: 880,
    minHeight: 520,
    backgroundColor: "#fafaf7",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: preloadEntry,
    },
  });

  // The renderer's <title> tag (currently "folio-viewer") would otherwise
  // overwrite our descriptive title. Block that so we keep "Folio · <sheet>".
  window.webContents.on("page-title-updated", (event) => event.preventDefault());
  window.setTitle(title);

  // Surface preload + renderer console messages in our terminal — useful
  // for diagnosing bridge / IPC issues without opening DevTools manually.
  window.webContents.on(
    "console-message",
    (_event, level, message, line, sourceId) => {
      const tag = ["log", "warn", "error"][level] ?? "info";
      logLine(`[renderer:${tag}] ${sourceId}:${line} ${message}`);
    },
  );

  void window.loadURL(url);

  window.webContents.setWindowOpenHandler(({ url: target }) => {
    if (/^https?:/.test(target)) {
      void shell.openExternal(target);
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  window.on("closed", () => {
    if (mainWindow === window) mainWindow = null;
  });

  mainWindow = window;
  return window;
}

function rebuildMenu(): void {
  const isMac = process.platform === "darwin";
  const recents = getRecentSheets().filter((p) => p !== currentSheet);
  const template: Electron.MenuItemConstructorOptions[] = [
    ...(isMac
      ? ([
          {
            label: app.name,
            submenu: [
              { role: "about" },
              { type: "separator" },
              { role: "services" },
              { type: "separator" },
              { role: "hide" },
              { role: "hideOthers" },
              { role: "unhide" },
              { type: "separator" },
              { role: "quit" },
            ],
          },
        ] satisfies Electron.MenuItemConstructorOptions[])
      : []),
    {
      label: "Sheet",
      submenu: [
        {
          label: "Open Sheet…",
          accelerator: "CmdOrCtrl+O",
          click: async () => {
            const sheet = await pickSheet(currentSheet ?? undefined);
            if (sheet) await startWithSheet(sheet);
          },
        },
        {
          label: "Open Recent",
          submenu:
            recents.length === 0
              ? [{ label: "No recent sheets", enabled: false }]
              : [
                  ...recents.map((p) => ({
                    label: basename(p),
                    sublabel: p,
                    click: () => {
                      void startWithSheet(p);
                    },
                  })),
                  { type: "separator" as const },
                  {
                    label: "Clear Recent",
                    click: () => {
                      const settings = readSettings();
                      writeSettings({ ...settings, recentSheets: [] });
                      rebuildMenu();
                    },
                  },
                ],
        },
        {
          label: "Reveal in Finder",
          enabled: !!currentSheet,
          click: () => {
            if (currentSheet) shell.showItemInFolder(currentSheet);
          },
        },
        { type: "separator" },
        {
          label: "Restart Server",
          click: async () => {
            if (currentSheet) await startWithSheet(currentSheet);
          },
        },
        { type: "separator" },
        isMac ? { role: "close" } : { role: "quit" },
      ],
    },
    { role: "editMenu" },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "forceReload" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
      ],
    },
    { role: "windowMenu" },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function registerIpcHandlers(): void {
  ipcMain.handle("viewer:current-sheet", () => currentSheet);

  ipcMain.handle("viewer:recent-sheets", () =>
    getRecentSheets()
      .filter((p) => p !== currentSheet)
      .map((p) => ({ path: p, name: basename(p) })),
  );

  ipcMain.handle("viewer:open-sheet", async () => {
    const sheet = await pickSheet(currentSheet ?? undefined);
    if (sheet) {
      await startWithSheet(sheet);
      return { ok: true, path: sheet };
    }
    return { ok: false };
  });

  ipcMain.handle("viewer:switch-sheet", async (_event, target: unknown) => {
    if (typeof target !== "string" || !existsSync(target)) {
      return { ok: false, error: "path does not exist" };
    }
    if (!isValidSheet(target)) {
      return { ok: false, error: "no contract.yaml in target directory" };
    }
    await startWithSheet(target);
    return { ok: true, path: target };
  });
}

app.whenReady().then(async () => {
  augmentPathFromShell();
  registerIpcHandlers();
  rebuildMenu();

  let sheet: string | null = null;
  if (process.env.FOLIO_SHEET && existsSync(process.env.FOLIO_SHEET)) {
    sheet = process.env.FOLIO_SHEET;
  } else {
    const last = readSettings().lastSheet;
    if (last && existsSync(last)) sheet = last;
  }
  if (!sheet) {
    sheet = await pickSheet();
    if (!sheet) {
      app.quit();
      return;
    }
  }

  await startWithSheet(sheet);

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      if (serverManager?.url && currentSheet) {
        createWindow(serverManager.url, currentSheet);
      } else if (currentSheet) {
        await startWithSheet(currentSheet);
      }
    }
  });
});

app.on("before-quit", async (event) => {
  if (serverManager?.running) {
    event.preventDefault();
    await serverManager.stop();
    serverManager = null;
    app.quit();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

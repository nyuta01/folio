import { app, BrowserWindow, dialog, Menu, shell } from "electron";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { createServerManager, type ServerManager } from "./server-manager.js";

interface Settings {
  lastSheet?: string;
}

// dist/main/main.js → up 4 levels = repo root (dist/main → dist → desktop → apps → repo).
const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..", "..", "..");
const defaultStaticDir = join(repoRoot, "viewer", "dist");
const venvBin = join(repoRoot, ".venv", "bin", "folio-viewer");
const settingsFile = join(app.getPath("userData"), "settings.json");

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

function findFolioBin(): string {
  if (process.env.FOLIO_VIEWER_BIN) return process.env.FOLIO_VIEWER_BIN;
  if (existsSync(venvBin)) return venvBin;
  return "folio-viewer";
}

function resolveStaticDir(): string | undefined {
  if (process.env.FOLIO_STATIC_DIR) return process.env.FOLIO_STATIC_DIR;
  if (existsSync(defaultStaticDir)) return defaultStaticDir;
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
      `WARNING: viewer/dist not found — run \`npm --prefix ${join(
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
    await dialog.showMessageBox({
      type: "error",
      message: "Could not start folio-viewer",
      detail: `${msg}\n\nMake sure \`folio-viewer\` is installed (run \`uv sync\` from the repo root) and that the picked directory is a Folio sheet.\n\nRecent logs:\n${recentLogs.slice(0, 8).join("\n")}`,
      buttons: ["OK"],
    });
    return;
  }

  serverManager = manager;
  currentSheet = sheetPath;
  writeSettings({ lastSheet: sheetPath });

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
    },
  });

  // The renderer's <title> tag (currently "folio-viewer") would otherwise
  // overwrite our descriptive title. Block that so we keep "Folio · <sheet>".
  window.webContents.on("page-title-updated", (event) => event.preventDefault());
  window.setTitle(title);

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

function buildMenu(): void {
  const isMac = process.platform === "darwin";
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

app.whenReady().then(async () => {
  buildMenu();

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

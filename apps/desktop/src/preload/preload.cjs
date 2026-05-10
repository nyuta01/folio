// Preload bridge exposed to the viewer renderer as `window.folioBridge`.
// Keep the surface tiny: only what the renderer can't do via plain HTTP.
const { contextBridge, ipcRenderer } = require("electron");

try {
  contextBridge.exposeInMainWorld("folioBridge", {
    platform: process.platform,
    openSheet: () => ipcRenderer.invoke("viewer:open-sheet"),
    currentSheet: () => ipcRenderer.invoke("viewer:current-sheet"),
    recentSheets: () => ipcRenderer.invoke("viewer:recent-sheets"),
    switchSheet: (path) => ipcRenderer.invoke("viewer:switch-sheet", path),
  });
  console.log("[folio-preload] folioBridge attached");
} catch (err) {
  console.error("[folio-preload] failed to attach bridge:", err);
}

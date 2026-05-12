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
    // Coding-agent bridge. Only present inside the Electron shell -
    // the standalone FastAPI viewer (browser) sees `agents: undefined`
    // and degrades gracefully.
    agents: {
      list: () => ipcRenderer.invoke("agents:list"),
      run: (payload) =>
        ipcRenderer.invoke("agents:run", {
          agentId: payload?.agentId,
          prompt: payload?.prompt,
          sessionId: payload?.sessionId,
          isFollowup: payload?.isFollowup,
        }),
      input: (payload) => ipcRenderer.invoke("agents:input", payload),
      stop: (payload) => ipcRenderer.invoke("agents:stop", payload),
      onStart: (handler) => {
        const wrap = (_e, payload) => handler(payload);
        ipcRenderer.on("agents:start", wrap);
        return () => ipcRenderer.off("agents:start", wrap);
      },
      onChunk: (handler) => {
        const wrap = (_e, payload) => handler(payload);
        ipcRenderer.on("agents:chunk", wrap);
        return () => ipcRenderer.off("agents:chunk", wrap);
      },
      onEvent: (handler) => {
        const wrap = (_e, payload) => handler(payload);
        ipcRenderer.on("agents:event", wrap);
        return () => ipcRenderer.off("agents:event", wrap);
      },
      onEnd: (handler) => {
        const wrap = (_e, payload) => handler(payload);
        ipcRenderer.on("agents:end", wrap);
        return () => ipcRenderer.off("agents:end", wrap);
      },
    },
  });
  console.log("[folio-preload] folioBridge attached");
} catch (err) {
  console.error("[folio-preload] failed to attach bridge:", err);
}

// Optional Electron bridge — present only when running inside the Folio
// Desktop app (apps/desktop). The browser build leaves window.folioBridge
// undefined, and the UI degrades gracefully.

export interface FolioRecentSheet {
  path: string;
  name: string;
}

export interface FolioBridge {
  platform: NodeJS.Platform;
  openSheet: () => Promise<{ ok: boolean; path?: string }>;
  currentSheet: () => Promise<string | null>;
  recentSheets: () => Promise<FolioRecentSheet[]>;
  switchSheet: (
    path: string,
  ) => Promise<{ ok: boolean; path?: string; error?: string }>;
}

declare global {
  interface Window {
    folioBridge?: FolioBridge;
  }
}

export {};

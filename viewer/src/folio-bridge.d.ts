// Optional Electron bridge — present only when running inside the Folio
// Desktop app (apps/desktop). The browser build leaves window.folioBridge
// undefined, and the UI degrades gracefully.

export interface FolioRecentSheet {
  path: string;
  name: string;
}

export interface AgentAvailability {
  id: string;
  label: string;
  available: boolean;
  version?: string;
  installHint?: string;
}

export interface AgentsBridge {
  list: () => Promise<AgentAvailability[]>;
  run: (p: {
    agentId: string;
    prompt: string;
    cwd?: string;
    isFollowup?: boolean;
  }) => Promise<{ ok: true; sessionId: string } | { ok: false; error: string }>;
  input: (p: { sessionId: string; text: string }) => Promise<{ ok: boolean }>;
  stop: (p: { sessionId: string }) => Promise<{ ok: boolean }>;
  onStart: (
    cb: (p: { sessionId: string; agentId: string; label: string }) => void,
  ) => () => void;
  onChunk: (
    cb: (p: {
      sessionId: string;
      stream: "stdout" | "stderr";
      data: string;
    }) => void,
  ) => () => void;
  onEnd: (
    cb: (p: {
      sessionId: string;
      exitCode: number | null;
      error: string | null;
    }) => void,
  ) => () => void;
}

export interface FolioBridge {
  platform: NodeJS.Platform;
  openSheet: () => Promise<{ ok: boolean; path?: string }>;
  currentSheet: () => Promise<string | null>;
  recentSheets: () => Promise<FolioRecentSheet[]>;
  switchSheet: (
    path: string,
  ) => Promise<{ ok: boolean; path?: string; error?: string }>;
  // Optional - only attached inside the Electron shell. The Chat tab
  // tests for `bridge.agents` before rendering anything.
  agents?: AgentsBridge;
}

declare global {
  interface Window {
    folioBridge?: FolioBridge;
  }
}

export {};

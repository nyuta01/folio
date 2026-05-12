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

/** Structured event from a chat-agent turn. Mirrors the main-process
 * `AgentEvent` enum. The renderer flattens per-message block indices
 * into a single append-only block list per turn. */
export type AgentEvent =
  | { kind: "message_start" }
  | {
      kind: "block_start";
      index: number;
      blockType: "text" | "thinking" | "tool_use";
      toolName?: string;
      toolUseId?: string;
    }
  | { kind: "block_delta"; index: number; text: string }
  | { kind: "block_stop"; index: number }
  | {
      kind: "tool_result";
      toolUseId: string;
      content: string;
      isError?: boolean;
    }
  | { kind: "status"; status: string };

export interface AgentsBridge {
  list: () => Promise<AgentAvailability[]>;
  run: (p: {
    agentId: string;
    prompt: string;
    /** Renderer-side UUID identifying the chat session. Used by the
     * main process to thread `--session-id` / `--resume` into adapters
     * that support resumable conversations (e.g. Claude Code). */
    sessionId: string;
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
  onEvent: (
    cb: (p: { sessionId: string; event: AgentEvent }) => void,
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

// Coding-agent registry + session manager. Lives in the Electron main
// process so the renderer never spawns child processes directly; the
// FastAPI viewer never sees this surface at all (it would be a remote
// "run arbitrary command" hole if it did).
//
// Add a new agent by appending an `AgentSpec` to the AGENTS map.
// Everything else (IPC routes, the renderer's <ChatTab>, the agent
// picker, the availability probe) is data-driven from the spec.

import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomBytes } from "node:crypto";
import type { WebContents } from "electron";

/** One coding-agent CLI Folio knows how to spawn. */
export interface AgentSpec {
  id: string;
  label: string;
  /** Binary on $PATH. */
  bin: string;
  /** Build argv for one turn. */
  argv: (turn: { prompt: string; isFollowup: boolean }) => string[];
  /** Probe to check if the binary exists. */
  check: { args: string[] };
  /** Whether subsequent turns can reuse the prior session. */
  supportsContinue: boolean;
  /** Human-readable hint shown when the binary is missing. */
  installHint: string;
}

export const AGENTS: Record<string, AgentSpec> = {
  "claude-code": {
    id: "claude-code",
    label: "Claude Code",
    bin: "claude",
    argv: ({ prompt, isFollowup }) => [
      "--print",
      ...(isFollowup ? ["--continue"] : []),
      prompt,
    ],
    check: { args: ["--version"] },
    supportsContinue: true,
    installHint:
      "Install Claude Code: https://docs.anthropic.com/en/docs/claude-code/quickstart",
  },
  // Add codex / aider / etc. here. The renderer needs no change.
};

export interface AgentAvailability {
  id: string;
  label: string;
  available: boolean;
  version?: string;
  installHint?: string;
}

export interface RunSessionOptions {
  agentId: string;
  prompt: string;
  cwd: string;
  isFollowup?: boolean;
}

interface Session {
  id: string;
  agent: AgentSpec;
  cwd: string;
  proc: ChildProcessWithoutNullStreams;
  receivers: Set<WebContents>;
}

const sessions = new Map<string, Session>();

function newId(): string {
  return "s_" + randomBytes(6).toString("hex");
}

/** Best-effort PATH lookup probe — runs the agent's `--version`. */
export async function probeAgent(spec: AgentSpec): Promise<AgentAvailability> {
  return new Promise((resolve) => {
    let proc: ChildProcessWithoutNullStreams;
    try {
      proc = spawn(spec.bin, spec.check.args, { stdio: "pipe" });
    } catch {
      resolve({
        id: spec.id,
        label: spec.label,
        available: false,
        installHint: spec.installHint,
      });
      return;
    }
    let stdout = "";
    proc.stdout.on("data", (b: Buffer) => (stdout += b.toString("utf8")));
    proc.on("error", () =>
      resolve({
        id: spec.id,
        label: spec.label,
        available: false,
        installHint: spec.installHint,
      }),
    );
    proc.on("close", (code) =>
      resolve({
        id: spec.id,
        label: spec.label,
        available: code === 0,
        version: code === 0 ? stdout.trim().split("\n")[0] : undefined,
        installHint: code === 0 ? undefined : spec.installHint,
      }),
    );
  });
}

export async function listAgents(): Promise<AgentAvailability[]> {
  return Promise.all(Object.values(AGENTS).map(probeAgent));
}

/** Spawn an agent turn and stream stdout/stderr to the receiver WebContents. */
export function runAgent(
  opts: RunSessionOptions,
  receiver: WebContents,
): { ok: true; sessionId: string } | { ok: false; error: string } {
  const spec = AGENTS[opts.agentId];
  if (!spec) return { ok: false, error: `unknown agent: ${opts.agentId}` };

  let proc: ChildProcessWithoutNullStreams;
  try {
    proc = spawn(spec.bin, spec.argv({ prompt: opts.prompt, isFollowup: !!opts.isFollowup }), {
      cwd: opts.cwd,
      stdio: "pipe",
      env: process.env,
    });
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }

  const id = newId();
  const session: Session = {
    id,
    agent: spec,
    cwd: opts.cwd,
    proc,
    receivers: new Set([receiver]),
  };
  sessions.set(id, session);

  const send = (channel: string, payload: unknown) => {
    for (const wc of session.receivers) {
      if (!wc.isDestroyed()) wc.send(channel, payload);
    }
  };

  send("agents:start", { sessionId: id, agentId: spec.id, label: spec.label });

  proc.stdout.on("data", (b: Buffer) =>
    send("agents:chunk", { sessionId: id, stream: "stdout", data: b.toString("utf8") }),
  );
  proc.stderr.on("data", (b: Buffer) =>
    send("agents:chunk", { sessionId: id, stream: "stderr", data: b.toString("utf8") }),
  );
  proc.on("error", (err) => {
    send("agents:end", {
      sessionId: id,
      exitCode: null,
      error: err.message,
    });
    sessions.delete(id);
  });
  proc.on("close", (code) => {
    send("agents:end", { sessionId: id, exitCode: code, error: null });
    sessions.delete(id);
  });

  return { ok: true, sessionId: id };
}

export function sendInput(sessionId: string, text: string): boolean {
  const session = sessions.get(sessionId);
  if (!session) return false;
  try {
    session.proc.stdin.write(text);
    return true;
  } catch {
    return false;
  }
}

export function stopSession(sessionId: string): boolean {
  const session = sessions.get(sessionId);
  if (!session) return false;
  try {
    session.proc.kill("SIGTERM");
    return true;
  } catch {
    return false;
  }
}

/** Stop every running session — called on app quit. */
export function shutdownAllAgents(): void {
  for (const s of sessions.values()) {
    try {
      s.proc.kill("SIGTERM");
    } catch {
      /* ignore */
    }
  }
  sessions.clear();
}

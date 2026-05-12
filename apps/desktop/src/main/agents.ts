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
import { accessSync, constants, existsSync } from "node:fs";
import { isAbsolute, join, delimiter as PATH_DELIM } from "node:path";
import type { WebContents } from "electron";

/** Shape passed to AgentSpec.argv for one turn. */
export interface AgentTurnInput {
  prompt: string;
  isFollowup: boolean;
  /** Stable UUID identifying the *renderer-side* conversation. Adapters
   * that support resumable sessions thread it through to their CLI
   * (e.g. claude --session-id / --resume). */
  sessionId: string;
  /** Optional system-prompt addendum the host wants appended (sheet
   * context, skills hints, etc.). Adapters that can't append a system
   * prompt should ignore this. */
  systemHint?: string;
}

/** Structured event the renderer renders into the chat bubble. The
 * `index` field is per-message — adapters reset it whenever the agent
 * starts a new assistant message in the same turn (claude's tool-use
 * roundtrip emits multiple messages). The renderer collapses indices
 * into a flat append-only block list. */
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

/** One coding-agent CLI Folio knows how to spawn. */
export interface AgentSpec {
  id: string;
  label: string;
  /** Binary on $PATH. */
  bin: string;
  /** Build argv for one turn. */
  argv: (turn: AgentTurnInput) => string[];
  /** Probe to check if the binary exists. */
  check: { args: string[] };
  /** Whether subsequent turns can reuse the prior session. */
  supportsContinue: boolean;
  /** Human-readable hint shown when the binary is missing. */
  installHint: string;
  /** Parse one stdout line into zero or more structured events. When
   * absent, stdout is forwarded verbatim as a synthetic text block so
   * unknown adapters still produce visible output. */
  parseLine?: (line: string) => AgentEvent[];
}

function parseClaudeStreamJsonLine(line: string): AgentEvent[] {
  const trimmed = line.trim();
  if (!trimmed) return [];
  let obj: Record<string, unknown>;
  try {
    obj = JSON.parse(trimmed) as Record<string, unknown>;
  } catch {
    return [];
  }
  const events: AgentEvent[] = [];
  const type = obj.type as string | undefined;

  if (type === "stream_event" && obj.event && typeof obj.event === "object") {
    const ev = obj.event as Record<string, unknown>;
    const evType = ev.type as string | undefined;
    if (evType === "message_start") {
      events.push({ kind: "message_start" });
    } else if (evType === "content_block_start") {
      const cb = ev.content_block as Record<string, unknown> | undefined;
      const cbType = cb?.type as string | undefined;
      if (cbType === "text" || cbType === "thinking" || cbType === "tool_use") {
        events.push({
          kind: "block_start",
          index: Number(ev.index ?? 0),
          blockType: cbType,
          toolName: cbType === "tool_use" ? (cb?.name as string) : undefined,
          toolUseId: cbType === "tool_use" ? (cb?.id as string) : undefined,
        });
      }
    } else if (evType === "content_block_delta") {
      const d = ev.delta as Record<string, unknown> | undefined;
      const dt = d?.type as string | undefined;
      let text = "";
      if (dt === "text_delta") text = (d?.text as string) ?? "";
      else if (dt === "thinking_delta") text = (d?.thinking as string) ?? "";
      else if (dt === "input_json_delta")
        text = (d?.partial_json as string) ?? "";
      else return events;
      events.push({ kind: "block_delta", index: Number(ev.index ?? 0), text });
    } else if (evType === "content_block_stop") {
      events.push({ kind: "block_stop", index: Number(ev.index ?? 0) });
    }
  } else if (type === "user" && obj.message && typeof obj.message === "object") {
    const msg = obj.message as Record<string, unknown>;
    const content = msg.content;
    if (Array.isArray(content)) {
      for (const c of content as Array<Record<string, unknown>>) {
        if (c.type === "tool_result") {
          const raw = c.content;
          let text = "";
          if (typeof raw === "string") text = raw;
          else if (Array.isArray(raw)) {
            text = raw
              .map((x: Record<string, unknown>) =>
                typeof x.text === "string" ? x.text : "",
              )
              .join("");
          }
          events.push({
            kind: "tool_result",
            toolUseId: String(c.tool_use_id ?? ""),
            content: text,
            isError: !!c.is_error,
          });
        }
      }
    }
  } else if (type === "system" && obj.subtype === "status") {
    const status = obj.status as string | undefined;
    if (status) events.push({ kind: "status", status });
  }

  return events;
}

export const AGENTS: Record<string, AgentSpec> = {
  "claude-code": {
    id: "claude-code",
    label: "Claude Code",
    bin: "claude",
    argv: ({ prompt, isFollowup, sessionId, systemHint }) => [
      "--print",
      // stream-json + partial messages so the renderer can show thinking
      // blocks, tool calls, and incremental text deltas. `--verbose` is
      // required by claude when using stream-json in print mode.
      "--output-format",
      "stream-json",
      "--verbose",
      "--include-partial-messages",
      // First turn: assign our UUID. Follow-ups: resume that same UUID,
      // so the renderer's chat-session list maps 1-1 to claude's
      // on-disk session store. This lets us run multiple parallel
      // conversations in the same sheet directory — `--continue` only
      // resumes "the most recent" and would collapse them all together.
      ...(isFollowup
        ? ["--resume", sessionId]
        : ["--session-id", sessionId]),
      ...(systemHint ? ["--append-system-prompt", systemHint] : []),
      prompt,
    ],
    check: { args: ["--version"] },
    supportsContinue: true,
    installHint:
      "Install Claude Code: https://docs.anthropic.com/en/docs/claude-code/quickstart",
    parseLine: parseClaudeStreamJsonLine,
  },
  // Add codex / aider / etc. here. The renderer needs no change.
};

/** Build a short system-prompt addendum that orients the agent inside a
 * Folio sheet. Only mentions resources we can confirm exist (the
 * `folio` CLI on PATH, the `skills/` subdir when populated, etc.).
 * Returns `undefined` to skip injection if nothing useful applies. */
function buildSheetHint(cwd: string): string | undefined {
  const hasContract = existsSync(join(cwd, "contract.yaml"));
  if (!hasContract) return undefined;
  const skillsDir = join(cwd, "skills");
  const hasSkills = existsSync(skillsDir);
  const lines: string[] = [
    "You are operating inside a Folio sheet (a contract-driven dataset directory).",
    "- `contract.yaml` at the cwd root defines the schema and derivations. The `name:` field there is metadata — it is NOT the SQL table name.",
    "- The `folio` CLI is on your PATH. All verbs take the sheet directory as the first positional argument; use `.` (the cwd).",
    "- Read verbs (no --actor needed):",
    "    • `folio list .` — JSON envelope of records",
    "    • `folio count .` — `--where '<sql>'` optional",
    "    • `folio query . \"<sql>\"` — DuckDB SQL; the only table is `FROM records` (column names match contract properties; the `name:` in contract.yaml is NOT the table name)",
    "    • `folio status .` — materialization counts per derived field",
    "    • `folio provenance . <id> <field>` — history for one cell",
    "- Write verbs (ALL require `--actor agent:claude-code`):",
    "    • `folio upsert . --actor agent:claude-code --file -` (reads JSONL from stdin; one record per line)",
    "    • `folio delete . --actor agent:claude-code --ids id1,id2`",
    "    • `folio materialize . --actor agent:claude-code [<target>]` — recompute derived fields",
  ];
  if (hasSkills) {
    lines.push(
      "- Per-sheet workflows ship under `./skills/*.md`. Enumerate with `folio skill list .` (JSON). Render one with `folio skill show . <name>`.",
    );
  }
  lines.push(
    "- Prefer read-only verbs first; confirm before destructive writes. Mutations are recorded in `provenance.jsonl`.",
  );
  return lines.join("\n");
}

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
  /** Renderer-side UUID for the conversation. Required: lets the
   * adapter use --session-id / --resume so multiple conversations in
   * the same cwd don't collide. */
  sessionId: string;
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

function executableNames(bin: string): string[] {
  if (process.platform !== "win32") return [bin];
  if (/\.[^\\/]+$/.test(bin)) return [bin];

  const pathExt = process.env.PATHEXT ?? ".COM;.EXE;.BAT;.CMD";
  return pathExt
    .split(";")
    .map((ext) => ext.trim())
    .filter((ext) => ext.length > 0)
    .map((ext) => bin + ext);
}

function canExecute(path: string): boolean {
  try {
    accessSync(
      path,
      process.platform === "win32" ? constants.F_OK : constants.X_OK,
    );
    return true;
  } catch {
    return false;
  }
}

function resolveExecutableOnHostPath(bin: string): string | undefined {
  if (bin.includes("/") || bin.includes("\\")) {
    return isAbsolute(bin) && canExecute(bin) ? bin : undefined;
  }

  const pathEntries = (process.env.PATH ?? "")
    .split(PATH_DELIM)
    .filter((entry) => entry.length > 0 && entry !== ".");

  for (const dir of pathEntries) {
    for (const name of executableNames(bin)) {
      const candidate = join(dir, name);
      if (canExecute(candidate)) return candidate;
    }
  }
  return undefined;
}

/** Best-effort PATH lookup probe — runs the agent's `--version`. */
export async function probeAgent(spec: AgentSpec): Promise<AgentAvailability> {
  return new Promise((resolve) => {
    const executable = resolveExecutableOnHostPath(spec.bin);
    if (!executable) {
      resolve({
        id: spec.id,
        label: spec.label,
        available: false,
        installHint: spec.installHint,
      });
      return;
    }

    let proc: ChildProcessWithoutNullStreams;
    try {
      proc = spawn(executable, spec.check.args, { stdio: "pipe" });
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
  if (!opts.sessionId) return { ok: false, error: "sessionId is required" };

  const systemHint = buildSheetHint(opts.cwd);

  // Desktop chat agents are trusted host tools. Resolve the executable from
  // the app's host PATH before changing cwd to the opened sheet, and never
  // prepend sheet-controlled directories such as `.venv/bin`.
  const executable = resolveExecutableOnHostPath(spec.bin);
  if (!executable) {
    return { ok: false, error: `${spec.label} executable not found on PATH` };
  }
  const env = { ...process.env };

  let proc: ChildProcessWithoutNullStreams;
  try {
    proc = spawn(
      executable,
      spec.argv({
        prompt: opts.prompt,
        isFollowup: !!opts.isFollowup,
        sessionId: opts.sessionId,
        systemHint,
      }),
      {
        cwd: opts.cwd,
        stdio: "pipe",
        env,
      },
    );
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }

  // Close stdin immediately. The CLIs we target (`claude --print`, etc.)
  // read the prompt from argv and otherwise wait up to 3 seconds for stdin
  // before emitting a noisy "no stdin data received" warning to stderr.
  // We never feed them stdin from the renderer, so make it explicit.
  try {
    proc.stdin.end();
  } catch {
    /* stdin already closed */
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

  if (spec.parseLine) {
    // Line-buffered: stream-json adapters emit one JSON event per line.
    // Forward parsed `AgentEvent`s on agents:event; raw stdout never
    // reaches the renderer (it would just be machine-readable JSON the
    // chat bubble can't display anyway).
    let buf = "";
    const onLine = (line: string) => {
      const events = spec.parseLine!(line);
      for (const ev of events) {
        send("agents:event", { sessionId: id, event: ev });
      }
    };
    proc.stdout.on("data", (b: Buffer) => {
      buf += b.toString("utf8");
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl);
        buf = buf.slice(nl + 1);
        onLine(line);
      }
    });
    proc.stdout.on("end", () => {
      if (buf.length) onLine(buf);
      buf = "";
    });
  } else {
    // Plain-text adapter: forward stdout verbatim as a synthetic text
    // block so the chat bubble can still render it.
    proc.stdout.on("data", (b: Buffer) => {
      send("agents:event", {
        sessionId: id,
        event: {
          kind: "block_delta",
          index: 0,
          text: b.toString("utf8"),
        },
      });
    });
  }
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

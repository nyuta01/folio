import { spawn, type ChildProcess } from "node:child_process";
import { createServer } from "node:net";

export interface ServerManagerConfig {
  bin: string;
  sheetPath: string;
  staticDir?: string | undefined;
  onLog?: (line: string) => void;
}

export interface ServerManager {
  readonly url: string | null;
  readonly running: boolean;
  start(): Promise<string>;
  stop(): Promise<void>;
}

export function createServerManager(config: ServerManagerConfig): ServerManager {
  let child: ChildProcess | null = null;
  let url: string | null = null;
  const log = config.onLog ?? ((line: string) => console.log(`[folio] ${line}`));

  async function start(): Promise<string> {
    if (child) await stop();

    const port = await findFreePort();
    const args: string[] = [
      config.sheetPath,
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
    ];
    if (config.staticDir) {
      args.push("--static-dir", config.staticDir);
    }

    log(`spawn ${config.bin} ${args.join(" ")}`);
    const proc = spawn(config.bin, args, {
      stdio: ["ignore", "pipe", "pipe"],
      env: process.env,
    });
    child = proc;

    proc.stdout?.setEncoding("utf8");
    proc.stdout?.on("data", (chunk: string) => {
      for (const line of chunk.trim().split(/\r?\n/)) {
        if (line) log(line);
      }
    });
    proc.stderr?.setEncoding("utf8");
    proc.stderr?.on("data", (chunk: string) => {
      for (const line of chunk.trim().split(/\r?\n/)) {
        if (line) log(line);
      }
    });

    const exitPromise = new Promise<{ code: number | null; signal: NodeJS.Signals | null }>(
      (resolve) => {
        proc.once("exit", (code, signal) => {
          if (child === proc) {
            child = null;
            url = null;
          }
          resolve({ code, signal });
        });
      },
    );

    const startedUrl = `http://127.0.0.1:${port}`;
    try {
      await Promise.race([
        waitForReady(startedUrl),
        exitPromise.then(({ code, signal }) => {
          throw new Error(
            `folio-viewer exited before ready (code=${code}, signal=${signal ?? "none"})`,
          );
        }),
      ]);
    } catch (err) {
      try {
        proc.kill();
      } catch {
        // already gone
      }
      child = null;
      url = null;
      throw err;
    }

    url = startedUrl;
    log(`ready at ${startedUrl}`);
    return startedUrl;
  }

  async function stop(): Promise<void> {
    const proc = child;
    if (!proc) return;
    child = null;
    url = null;
    await new Promise<void>((resolve) => {
      let settled = false;
      const done = () => {
        if (!settled) {
          settled = true;
          resolve();
        }
      };
      proc.once("exit", done);
      try {
        proc.kill();
      } catch {
        done();
      }
      setTimeout(() => {
        try {
          proc.kill("SIGKILL");
        } catch {
          // ignore
        }
        done();
      }, 3000);
    });
  }

  return {
    get url() {
      return url;
    },
    get running() {
      return child !== null && !child.killed;
    },
    start,
    stop,
  };
}

async function waitForReady(baseUrl: string, timeoutMs = 30_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastErr: unknown = null;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${baseUrl}/api/contract`, {
        signal: AbortSignal.timeout(2000),
      });
      if (res.ok) return;
      lastErr = new Error(`HTTP ${res.status}`);
    } catch (e) {
      lastErr = e;
    }
    await sleep(250);
  }
  throw new Error(
    `folio-viewer did not become ready at ${baseUrl} within ${timeoutMs}ms${lastErr ? ` — last: ${(lastErr as Error).message ?? lastErr}` : ""}`,
  );
}

function findFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.unref();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address();
      if (addr && typeof addr === "object") {
        const port = addr.port;
        server.close(() => resolve(port));
      } else {
        reject(new Error("failed to allocate port"));
      }
    });
  });
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

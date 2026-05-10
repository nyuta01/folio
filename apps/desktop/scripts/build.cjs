#!/usr/bin/env node
// Cross-platform build for the Electron main + preload.
// Replaces the shell-only `rm -rf … && tsc … && cp src/preload/*.cjs …`
// pipeline so it runs identically on macOS, Linux, and Windows.
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const ROOT = path.resolve(__dirname, "..");
const DIST = path.join(ROOT, "dist");
const PRELOAD_SRC = path.join(ROOT, "src", "preload");
const PRELOAD_DST = path.join(DIST, "preload");

console.log("[build] cleaning dist/");
fs.rmSync(DIST, { recursive: true, force: true });
fs.rmSync(path.join(ROOT, "tsconfig.tsbuildinfo"), { force: true });

console.log("[build] tsc -p tsconfig.json");
// Resolve the TypeScript compiler entry point and invoke `node` on it
// directly. This avoids spawning a .cmd shim on Windows (which trips
// EINVAL under strict spawn rules) and matches Unix behavior 1:1.
const tscEntry = require.resolve("typescript/bin/tsc");
execFileSync(process.execPath, [tscEntry, "-p", "tsconfig.json"], {
  cwd: ROOT,
  stdio: "inherit",
});

console.log("[build] copying preload/*.cjs → dist/preload/");
fs.mkdirSync(PRELOAD_DST, { recursive: true });
for (const entry of fs.readdirSync(PRELOAD_SRC)) {
  if (entry.endsWith(".cjs")) {
    fs.copyFileSync(
      path.join(PRELOAD_SRC, entry),
      path.join(PRELOAD_DST, entry),
    );
  }
}

console.log("[build] ok");

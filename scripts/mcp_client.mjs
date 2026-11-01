#!/usr/bin/env node
// Minimal stdio MCP client — drive any MCP server from a shell.
//
//   MCP_SERVER=/abs/path/to/server.js node scripts/mcp_client.mjs list
//   node scripts/mcp_client.mjs describe <tool>
//   node scripts/mcp_client.mjs call <tool> '<json-args>'
//
// Point MCP_SERVER at the server entry file (defaults to iwork-mcp if installed).
import { spawn } from "node:child_process";

const SERVER = process.env.MCP_SERVER;
if (!SERVER) {
  console.error("set MCP_SERVER to the MCP server entry file");
  process.exit(2);
}

const [, , cmd, ...rest] = process.argv;
const proc = spawn(process.execPath, [SERVER], { stdio: ["pipe", "pipe", "pipe"] });
let buf = "";
const pending = new Map();
let nextId = 1;
const stderrChunks = [];

proc.stderr.on("data", (d) => stderrChunks.push(d.toString()));
proc.stdout.on("data", (d) => {
  buf += d.toString();
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!line) continue;
    let msg;
    try { msg = JSON.parse(line); } catch { continue; }
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  }
});

function request(method, params, timeoutMs = 180000) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`timeout: ${method}`)); }, timeoutMs);
    pending.set(id, (m) => { clearTimeout(timer); resolve(m); });
    proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  });
}

const init = await request("initialize", {
  protocolVersion: "2024-11-05", capabilities: {},
  clientInfo: { name: "shell-driver", version: "1.0.0" },
});
proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} }) + "\n");
console.error(`# server: ${init.result?.serverInfo?.name} v${init.result?.serverInfo?.version}`);

try {
  if (cmd === "list") {
    const r = await request("tools/list", {});
    for (const t of r.result.tools) console.log(`${t.name}\t${(t.description || "").slice(0, 90)}`);
  } else if (cmd === "describe") {
    const r = await request("tools/list", {});
    console.log(JSON.stringify(r.result.tools.find((x) => x.name === rest[0]), null, 2));
  } else if (cmd === "call") {
    const args = rest[1] ? JSON.parse(rest[1]) : {};
    const t0 = Date.now();
    const r = await request("tools/call", { name: rest[0], arguments: args });
    const text = (r.result?.content || []).filter((c) => c.type === "text").map((c) => c.text).join("\n");
    console.log(`# ${Date.now() - t0}ms isError=${!!r.result?.isError}`);
    console.log(r.error ? JSON.stringify(r.error) : text);
  } else {
    console.error("usage: list | describe <tool> | call <tool> '<json>'");
  }
} catch (e) {
  console.error("FAILED:", e.message);
  process.exitCode = 1;
} finally {
  const err = stderrChunks.join("").trim();
  if (err) console.error("# stderr:", err.split("\n").slice(-3).join(" | "));
  proc.kill();
  setTimeout(() => process.exit(process.exitCode || 0), 100);
}

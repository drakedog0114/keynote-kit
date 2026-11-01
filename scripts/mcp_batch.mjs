#!/usr/bin/env node
// Batch driver: run many MCP tool calls in ONE server process.
// usage: node batch.mjs plan.json
// plan.json: [ {tool, args, label?}, ... ]
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";

// 指向任意 MCP server 入口
const SERVER = process.env.MCP_SERVER;
if (!SERVER) { console.error("set MCP_SERVER to the MCP server entry file"); process.exit(2); }
const plan = JSON.parse(readFileSync(process.argv[2], "utf8"));

const proc = spawn(process.execPath, [SERVER], { stdio: ["pipe", "pipe", "pipe"] });
let buf = "";
const pending = new Map();
let nextId = 1;
const stderr = [];
proc.stderr.on("data", (d) => stderr.push(d.toString()));
proc.stdout.on("data", (d) => {
  buf += d.toString();
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!line) continue;
    let m;
    try { m = JSON.parse(line); } catch { continue; }
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  }
});

function call(method, params, timeoutMs = 180000) {
  const id = nextId++;
  return new Promise((res, rej) => {
    const t = setTimeout(() => { pending.delete(id); rej(new Error("timeout " + method)); }, timeoutMs);
    pending.set(id, (m) => { clearTimeout(t); res(m); });
    proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  });
}

await call("initialize", { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "batch", version: "1" } });
proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} }) + "\n");

let ok = 0, fail = 0;
for (const step of plan) {
  const t0 = Date.now();
  try {
    const r = await call("tools/call", { name: step.tool, arguments: step.args || {} });
    const ms = Date.now() - t0;
    const text = (r.result?.content || []).filter((c) => c.type === "text").map((c) => c.text).join("\n");
    if (r.error || r.result?.isError) {
      fail++;
      console.log(`✗ ${step.label || step.tool} (${ms}ms): ${r.error ? JSON.stringify(r.error) : text.slice(0, 300)}`);
    } else {
      ok++;
      const flat = text.replace(/\s+/g, " ");
      console.log(`✓ ${step.label || step.tool} (${ms}ms): ${flat.slice(0, 220)}`);
    }
  } catch (e) {
    fail++;
    console.log(`✗ ${step.label || step.tool}: ${e.message}`);
  }
}
console.log(`\n== ${ok} ok, ${fail} failed ==`);
if (stderr.join("").trim()) console.log("# last stderr:", stderr.join("").trim().split("\n").slice(-3).join(" | "));
proc.kill();
setTimeout(() => process.exit(fail ? 1 : 0), 100);

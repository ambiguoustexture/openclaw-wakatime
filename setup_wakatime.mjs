#!/usr/bin/env node

import { existsSync } from "node:fs";
import { copyFile, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const PLUGIN_ID = "openclaw-wakatime";

function parseArgs(argv) {
  const parsed = {
    pluginPath: "",
    project: "",
    category: "",
    noRestart: false,
  };

  for (let idx = 0; idx < argv.length; idx += 1) {
    const arg = argv[idx];
    if (arg === "--plugin-path") {
      parsed.pluginPath = argv[idx + 1] ?? "";
      idx += 1;
      continue;
    }
    if (arg === "--project") {
      parsed.project = argv[idx + 1] ?? "";
      idx += 1;
      continue;
    }
    if (arg === "--category") {
      parsed.category = argv[idx + 1] ?? "";
      idx += 1;
      continue;
    }
    if (arg === "--no-restart") {
      parsed.noRestart = true;
      continue;
    }
    if (arg === "-h" || arg === "--help") {
      printHelp();
      process.exit(0);
    }
  }

  return parsed;
}

function printHelp() {
  console.log("OpenClaw WakaTime Setup (TS plugin)");
  console.log("");
  console.log("Usage:");
  console.log("  node setup_wakatime.mjs [--plugin-path <path>] [--project <name>] [--category <name>] [--no-restart]");
  console.log("");
  console.log("Flags:");
  console.log("  --plugin-path   Plugin root path containing openclaw.plugin.json (default: current repo)");
  console.log("  --project       Set default WakaTime project in plugin config");
  console.log("  --category      Set default WakaTime category in plugin config");
  console.log("  --no-restart    Do not restart OpenClaw gateway automatically");
}

function ensureObject(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value;
  }
  return {};
}

function runOpenClaw(args) {
  return spawnSync("openclaw", args, {
    stdio: "inherit",
    env: process.env,
  });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  const repoRoot = path.dirname(fileURLToPath(import.meta.url));
  const pluginRoot = path.resolve(args.pluginPath || repoRoot);
  const manifestPath = path.join(pluginRoot, "openclaw.plugin.json");

  if (!existsSync(manifestPath)) {
    console.error(`✗ openclaw.plugin.json not found: ${manifestPath}`);
    process.exit(1);
  }

  const openclawConfigPath = path.join(os.homedir(), ".openclaw", "openclaw.json");
  if (!existsSync(openclawConfigPath)) {
    console.error(`✗ OpenClaw config not found: ${openclawConfigPath}`);
    process.exit(1);
  }

  const raw = await readFile(openclawConfigPath, "utf8");
  let config;
  try {
    config = JSON.parse(raw);
  } catch (error) {
    console.error(`✗ Failed to parse ${openclawConfigPath}: ${String(error)}`);
    process.exit(1);
  }

  const next = ensureObject(config);
  next.plugins = ensureObject(next.plugins);
  next.plugins.enabled = true;

  next.plugins.load = ensureObject(next.plugins.load);
  const pathsValue = Array.isArray(next.plugins.load.paths) ? next.plugins.load.paths : [];
  const normalized = path.resolve(pluginRoot);
  if (!pathsValue.includes(normalized)) {
    pathsValue.push(normalized);
  }
  next.plugins.load.paths = pathsValue;

  next.plugins.entries = ensureObject(next.plugins.entries);
  const entry = ensureObject(next.plugins.entries[PLUGIN_ID]);
  entry.enabled = true;
  entry.config = ensureObject(entry.config);

  if (args.project.trim()) {
    entry.config.project = args.project.trim();
  }
  if (args.category.trim()) {
    entry.config.category = args.category.trim();
  }

  next.plugins.entries[PLUGIN_ID] = entry;

  if (Array.isArray(next.plugins.allow) && !next.plugins.allow.includes(PLUGIN_ID)) {
    next.plugins.allow.push(PLUGIN_ID);
  }
  if (Array.isArray(next.plugins.deny)) {
    next.plugins.deny = next.plugins.deny.filter((item) => item !== PLUGIN_ID);
  }

  // Migration cleanup for legacy hook-based implementation.
  const hooks = ensureObject(next.hooks);
  const internal = ensureObject(hooks.internal);
  const entries = ensureObject(internal.entries);
  if (Object.prototype.hasOwnProperty.call(entries, "wakatime-im")) {
    delete entries["wakatime-im"];
  }
  internal.entries = entries;

  const load = ensureObject(internal.load);
  const extraDirs = Array.isArray(load.extraDirs) ? load.extraDirs : [];
  const legacyHooksDir = path.join(normalized, "hooks");
  load.extraDirs = extraDirs.filter((item) => item !== legacyHooksDir);
  internal.load = load;
  hooks.internal = internal;
  next.hooks = hooks;

  const backupPath = `${openclawConfigPath}.bak-${Date.now()}`;
  await copyFile(openclawConfigPath, backupPath);
  await writeFile(openclawConfigPath, `${JSON.stringify(next, null, 2)}\n`, "utf8");

  console.log("✓ Updated OpenClaw plugin config");
  console.log(`  Config: ${openclawConfigPath}`);
  console.log(`  Backup: ${backupPath}`);
  console.log(`  Plugin path: ${normalized}`);

  if (!args.noRestart) {
    console.log("\nRestarting gateway...");
    runOpenClaw(["gateway", "restart"]);
  } else {
    console.log("\nSkipping gateway restart (--no-restart)");
  }

  console.log("\nVerifying plugin...");
  runOpenClaw(["plugins", "info", PLUGIN_ID]);

  console.log("\nSetup complete.");
  console.log("Next steps:");
  console.log("1. Send a message or command through your channel integration.");
  console.log("2. Inspect plugin runtime log: ~/.openclaw/wakatime/plugin.log");
  console.log("3. Open WakaTime dashboard: https://wakatime.com/dashboard");
}

main().catch((error) => {
  console.error(`✗ setup failed: ${String(error)}`);
  process.exit(1);
});

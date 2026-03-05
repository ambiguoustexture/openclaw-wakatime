import assert from "node:assert/strict";
import test from "node:test";
import { buildWakatimeCommand } from "../src/wakatime-command.ts";

function baseHeartbeat(overrides = {}) {
  return {
    entity: "/tmp/sample.ts",
    language: "TypeScript",
    project: "agent-vibe-coding",
    category: "ai coding",
    timestamp: 1_700_000_000,
    entityType: "file",
    lines: 0,
    lineAdditions: 0,
    lineDeletions: 0,
    isWrite: false,
    ...overrides,
  };
}

test("file entities omit --language and --entity-type", () => {
  const argv = buildWakatimeCommand({
    wakaBin: "/usr/bin/wakatime",
    heartbeat: baseHeartbeat(),
    pluginSignature: "OpenClaw/2026.3.2 openclaw-wakatime/0.9.10",
  });

  assert.equal(argv.includes("--language"), false);
  assert.equal(argv.includes("--entity-type"), false);
});

test("app entities include --language and --entity-type", () => {
  const argv = buildWakatimeCommand({
    wakaBin: "/usr/bin/wakatime",
    heartbeat: baseHeartbeat({
      entity: "openclaw://command/start/abc",
      language: "Markdown",
      entityType: "app",
    }),
    pluginSignature: "OpenClaw/2026.3.2 openclaw-wakatime/0.9.10",
  });

  const languageIndex = argv.indexOf("--language");
  const entityTypeIndex = argv.indexOf("--entity-type");
  assert.ok(languageIndex >= 0);
  assert.equal(argv[languageIndex + 1], "Markdown");
  assert.ok(entityTypeIndex >= 0);
  assert.equal(argv[entityTypeIndex + 1], "app");
});

test("write and line stats flags are emitted", () => {
  const argv = buildWakatimeCommand({
    wakaBin: "/usr/bin/wakatime",
    heartbeat: baseHeartbeat({
      isWrite: true,
      lines: 120,
      lineAdditions: 10,
      lineDeletions: 3,
    }),
    pluginSignature: "OpenClaw/2026.3.2 openclaw-wakatime/0.9.10",
  });

  assert.ok(argv.includes("--write"));
  assert.ok(argv.includes("--lines"));
  assert.ok(argv.includes("--line-additions"));
  assert.ok(argv.includes("--line-deletions"));
});

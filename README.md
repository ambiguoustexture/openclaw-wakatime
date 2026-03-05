# openclaw-wakatime

TypeScript-native WakaTime plugin for OpenClaw.

Published npm package: `@re/openclaw-wakatime`

This plugin tracks OpenClaw runtime activity and sends heartbeats through the official `wakatime` CLI:

- `message_received` / `message_sent`
- `command:*` (via internal hook registration)
- `after_tool_call` (`read/edit/write` use file entities from tool params such as `path`/`file_path`, with language inferred from extension)
- `session_start` / `session_end`

Runtime files are written under `~/.openclaw/wakatime/`:

- `plugin.log`
- `queue.jsonl`
- `sessions.jsonl`

## Requirements

- OpenClaw `>= 2026.3.x`
- WakaTime CLI installed and authenticated (`~/.wakatime.cfg` or `WAKATIME_API_KEY`)
- Command examples use POSIX shell syntax; on Windows use equivalent PowerShell/CMD commands.

## Authentication

The plugin does not store or manage your WakaTime API key directly.
It only invokes the official `wakatime` CLI.

Key resolution is handled by WakaTime CLI:

- Recommended: `~/.wakatime.cfg` with `api_key = waka_...`
- Alternative: environment variable `WAKATIME_API_KEY`

Prefer `~/.wakatime.cfg` for reliability, because shell environment variables are not always inherited by the OpenClaw gateway process.

## Fresh Start (new machine)

1. Install and authenticate WakaTime CLI.
2. Confirm key is available (for example with `~/.wakatime.cfg`).
3. Install/enable this plugin.
4. Restart gateway (`openclaw gateway restart`).
5. Trigger one real message/tool call and verify heartbeats.

## Missing/invalid key behavior

- Plugin still loads in OpenClaw.
- Heartbeat sending fails until credentials are fixed.
- Failed heartbeats are queued in `~/.openclaw/wakatime/queue.jsonl`.
- After fixing credentials, queued heartbeats are retried automatically.

## Install (local path)

```bash
cd ~/.openclaw/plugins/openclaw-wakatime
node setup_wakatime.mjs
```

The setup script updates `~/.openclaw/openclaw.json`:

- `plugins.load.paths` includes this directory
- `plugins.entries.openclaw-wakatime.enabled = true`

Then it restarts gateway by default and prints plugin status.

## Install (npm)

```bash
openclaw plugins install @re/openclaw-wakatime --pin
openclaw plugins info openclaw-wakatime
```

## Configure

Plugin config lives at:

`plugins.entries.openclaw-wakatime.config`

Example:

```json
{
  "plugins": {
    "entries": {
      "openclaw-wakatime": {
        "enabled": true,
        "config": {
          "enabled": true,
          "project": "agent-vibe-coding",
          "category": "ai coding",
          "useContextProject": false,
          "heartbeatIntervalSeconds": 120,
          "queueRetryBatchSize": 50,
          "queueFlushIntervalSeconds": 60,
          "trackMessages": true,
          "trackCommands": true,
          "trackTools": true,
          "trackSessions": true
        }
      }
    }
  }
}
```

After config edits, restart gateway.

## Verify

```bash
openclaw plugins info openclaw-wakatime
openclaw plugins list
```

Then send a real channel message or command and check:

```bash
tail -f ~/.openclaw/wakatime/plugin.log
```

## Packaging Notes

This repository follows the OpenClaw plugin spec:

- `openclaw.plugin.json` manifest (required)
- TypeScript plugin entrypoint (`index.ts`)
- package metadata with `openclaw.extensions`

Release and community submission runbook:

- `RELEASE.md`

## Migration From Legacy Version

`0.9.9` is a full TS rewrite.

Removed runtime paths:

- Python tracker modules (`wakatime_openclaw.py`, `wakatime_hooks.py`, `wakatime_wrapper.py`)
- legacy `hooks/wakatime-im` bridge
- legacy zsh preexec hook integration

If you previously used those paths, switch to plugin config under `plugins.entries.openclaw-wakatime`.

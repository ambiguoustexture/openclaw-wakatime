# WakaTime for OpenClaw

Repository name: `openclaw-wakatime`.
Python module name (kept for compatibility): `wakatime_openclaw`.

## Why this project

OpenClaw sessions include more than file edits (tools, shell, web calls, token usage). This plugin tracks those events while keeping WakaTime-compatible heartbeat semantics.

## Official-doc aligned behavior

Based on WakaTime plugin guidance:

- Sends heartbeats through WakaTime CLI (no custom API client).
- Includes `--plugin` for plugin identification.
- Uses `--entity-type app` for non-file entities such as `openclaw://session/...`.
- Sends absolute file paths for file entities.
- Applies non-write heartbeat throttling (default 120 seconds per entity).
- Queues failed heartbeats and retries from `~/.openclaw/wakatime/queue.jsonl`.
- Defaults all activity to:
  - `project=agent-vibe-coding`
  - `category=ai coding`
  Override with env vars:
  - `OPENCLAW_WAKATIME_PROJECT`
  - `OPENCLAW_WAKATIME_CATEGORY`
  Set `OPENCLAW_WAKATIME_USE_CONTEXT_PROJECT=1` to restore context/path-based project splitting.

References:
- https://wakatime.com/help/creating-plugin
- https://wakatime.com/developers

## Repository layout

- `wakatime_openclaw.py`: core heartbeat model, queue/retry, status CLI.
- `wakatime_hooks.py`: OpenClaw hook handlers.
- `wakatime_wrapper.py`: tracked wrappers for read/write/exec/session.
- `setup_wakatime.py`: one-command installer (config patch + gateway restart + verification).
- `zsh-wakatime-hook.sh`: optional shell command tracking hook.
- `hooks/wakatime-im/`: OpenClaw internal hook to track chat/command interactions.

## Quick start

```bash
pip install --user wakatime
python3 setup_wakatime.py
# fresh start (no ~/.wakatime.cfg yet):
python3 setup_wakatime.py --waka-key waka_xxx_your_key
python3 ~/.openclaw/plugins/wakatime_openclaw.py --status
# optional console scripts after install:
# openclaw-wakatime --status
```

`setup_wakatime.py` now automatically:
- patches `~/.openclaw/openclaw.json` to enable `hooks/wakatime-im`
- restarts OpenClaw gateway
- verifies hook readiness (`openclaw hooks info wakatime-im`)
- sends a test heartbeat

Useful setup flags:

```bash
python3 setup_wakatime.py --waka-key waka_xxx_your_key
python3 setup_wakatime.py --non-interactive --waka-key waka_xxx_your_key --no-save-key
python3 setup_wakatime.py --no-restart
python3 setup_wakatime.py --no-zsh --no-test
```

Manual OpenClaw config (only if you skip auto-setup):

```json
{
  "hooks": {
    "internal": {
      "load": {
        "extraDirs": ["/home/re/.openclaw/plugins/openclaw-wakatime/hooks"]
      },
      "entries": {
        "wakatime-im": { "enabled": true }
      }
    }
  }
}
```

## Runtime files

Runtime state is stored under `~/.openclaw/wakatime/`:

- `plugin.log`
- `queue.jsonl`
- `sessions.jsonl`

## Python usage

```python
from wakatime_wrapper import tracked_session, tracked_read, tracked_write, tracked_exec

with tracked_session("feature-x", "Working on bugfix"):
    content = tracked_read("main.py")
    tracked_write("main.py", content + "\n# updated")
    print(tracked_exec("git status"))
```

## Troubleshooting

- Check CLI: `~/.local/bin/wakatime --version`
- Check key: `grep api_key ~/.wakatime.cfg`
- For first-time setup in CI/headless environments:
  `python3 setup_wakatime.py --non-interactive --waka-key <WAKA_KEY>`
- Check plugin status: `python3 ~/.openclaw/plugins/wakatime_openclaw.py --status`
- Retry queue: `python3 ~/.openclaw/plugins/wakatime_openclaw.py --process-queue`
- Send one synthetic hook heartbeat:
  `python3 ~/.openclaw/plugins/wakatime_openclaw.py --track-hook --event-type message --event-action received --channel-id telegram --conversation-id local-test`
- For `file` heartbeats, make sure the file actually exists. WakaTime CLI will skip non-existing file paths.
- Dashboard/status endpoints can lag by a few minutes. If a test heartbeat is not visible immediately, wait and refresh.

## Development

```bash
python3 -m py_compile *.py
python3 -m venv .venv-local
./.venv-local/bin/python -m pip install pytest
./.venv-local/bin/python -m pytest -q
```

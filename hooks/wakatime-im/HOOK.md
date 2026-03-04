---
name: wakatime-im
description: "Track OpenClaw message and command interactions in WakaTime"
homepage: https://wakatime.com/help/creating-plugin
metadata:
  {
    "openclaw":
      {
        "events": ["message:received", "message:sent", "command"],
        "hookKey": "wakatime-im",
      },
  }
---

# WakaTime IM Hook

Records OpenClaw interactions from chat channels (for example Telegram and Discord) and command actions as WakaTime heartbeats.

## What It Tracks

- `message:received` events for inbound channel messages.
- `message:sent` events for outbound OpenClaw replies.
- `command` events such as `/new`, `/reset`, and `/stop`.

## Runtime Behavior

- Executes `wakatime_openclaw.py --track-hook ...` in the background.
- Uses the same project/category/plugin metadata as the core plugin.
- Writes diagnostics to `~/.openclaw/wakatime/plugin.log`.

## Enable

Add this repository `hooks` directory to `hooks.internal.load.extraDirs`, then enable the hook key:

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

# Repository Guidelines

## Project Structure & Module Organization
This repository ships an OpenClaw plugin implemented in TypeScript.

- `openclaw.plugin.json`: required OpenClaw plugin manifest + config schema.
- `index.ts`: plugin entrypoint (`register(api)`).
- `src/wakatime-tracker.ts`: heartbeat model, queue/retry, throttling, and event mapping.
- `setup_wakatime.mjs`: local installer that patches `~/.openclaw/openclaw.json` for plugin loading.

Runtime state is written under `~/.openclaw/wakatime/` (`queue.jsonl`, `plugin.log`, `sessions.jsonl`).

## Build, Test, and Development Commands
- `node setup_wakatime.mjs`: configure plugin load path and enable plugin entry.
- `openclaw plugins info openclaw-wakatime`: verify plugin discovery and status.
- `node --check setup_wakatime.mjs`: quick syntax validation for setup script.
- `openclaw plugins list | rg openclaw-wakatime`: verify plugin is discoverable.

## Coding Style & Naming Conventions
- Use TypeScript modules (ESM) with clear type aliases and small focused helpers.
- Use `camelCase` for variables/functions and `PascalCase` for classes/types.
- Keep plugin API wiring in `index.ts`; keep heartbeat logic in `src/wakatime-tracker.ts`.
- Prefer explicit config parsing and safe fallbacks for env/config values.

## Testing Guidelines
There is currently no formal test suite in this directory.

Before submitting changes:
- Run `node --check setup_wakatime.mjs`.
- Run `openclaw plugins info openclaw-wakatime` after setup.
- Trigger one real message/command and inspect `~/.openclaw/wakatime/plugin.log`.

For non-trivial changes, add Node tests under `tests/*.test.mjs`.

## Commit & Pull Request Guidelines
Use Conventional Commit style.

Examples:
- `feat: add tool heartbeat throttling`
- `fix: guard queue flush reentrancy`
- `chore: update plugin manifest ui hints`

PRs should include:
- summary and rationale
- verification commands run
- config/runtime impact (`plugins.entries.openclaw-wakatime.config`)

## Security & Configuration Tips
- Never commit API keys or local secret config.
- Read WakaTime secrets from `~/.wakatime.cfg` or `WAKATIME_API_KEY`.
- Keep plugin path trust explicit via `plugins.allow` in hardened environments.

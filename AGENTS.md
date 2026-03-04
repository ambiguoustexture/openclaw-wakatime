# Repository Guidelines

## Project Structure & Module Organization
This repository is a small Python plugin set for WakaTime integration in OpenClaw.
Public project name is `openclaw-wakatime`; Python module names remain `wakatime_*` for compatibility.
- `wakatime_openclaw.py`: core heartbeat model, project/language detection, queue/retry, and session stats.
- `wakatime_hooks.py`: event-hook layer that maps OpenClaw lifecycle/tool events to tracking calls.
- `wakatime_wrapper.py`: helper wrappers/context managers for tracked exec/read/write flows.
- `setup_wakatime.py`: local setup and environment checks.
- `zsh-wakatime-hook.sh`: optional shell command tracking hook.

Runtime state is written outside this repo under `~/.openclaw/wakatime/` (for example `queue.jsonl`, `plugin.log`, `sessions.jsonl`).

## Build, Test, and Development Commands
Use Python 3.12+.
- `python3 setup_wakatime.py`: validate prerequisites and install shell integration.
- `python3 wakatime_openclaw.py`: send a test heartbeat and verify core plugin wiring.
- `python3 wakatime_hooks.py`: smoke-test hook imports/entrypoints.
- `python3 wakatime_wrapper.py`: end-to-end wrapper smoke test (writes `/tmp/wakatime_test.txt`).
- `python3 -m py_compile *.py`: fast syntax check across all modules.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation.
- Use `snake_case` for functions/variables and `PascalCase` for classes.
- Keep modules focused: core tracking in `wakatime_openclaw.py`, adapters in hooks/wrappers.
- Add type hints on new public functions and keep docstrings short/actionable.
- Guard script-only logic with `if __name__ == "__main__":`.

## Testing Guidelines
There is currently no formal automated test suite in this directory.
- Run `python3 -m py_compile *.py` before submitting changes.
- Run at least one relevant smoke script above for behavioral changes.
- For queue/retry changes, inspect `~/.openclaw/wakatime/queue.jsonl` and `plugin.log`.
- For non-trivial new logic, add `pytest` tests as `tests/test_<module>.py` (happy path + failure path).

## Commit & Pull Request Guidelines
Git history is not available in this checkout, so use Conventional Commit style.
- Examples: `feat: add session idle heartbeat guard`, `fix: handle missing wakatime binary`.
- Keep commits focused and atomic.
- PRs should include: summary, why the change is needed, verification commands run, and any config/runtime impact.

## Security & Configuration Tips
- Never commit API keys or local config values.
- Read secrets from `~/.wakatime.cfg` or environment variables.
- Redact sensitive command arguments and paths when sharing logs.

# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Fresh-start API key flow in setup:
  - `--waka-key` for explicit key input
  - interactive key prompt when key is missing
  - optional `--no-save-key` mode for non-persistent runs
  - `--non-interactive` mode for CI/headless installs
- WakaTime config helpers to upsert `api_key` into `~/.wakatime.cfg`.
- Tests covering key upsert/persistence behavior in `tests/test_setup.py`.

## [1.2.0] - 2026-03-04

### Added
- One-command setup flow in `setup_wakatime.py` with OpenClaw hook auto-configuration.
- Automatic OpenClaw gateway restart and `wakatime-im` hook readiness verification in setup.
- Tests for setup config patching behavior in `tests/test_setup.py`.
- `LICENSE` file (MIT).

### Changed
- Updated plugin version to `1.2.0` across Python core, zsh hook, and package metadata.
- README quick start and setup documentation to match the new auto-setup behavior.

## [1.1.0] - 2026-03-04

### Added
- Baseline `openclaw-wakatime` plugin structure and WakaTime heartbeat core.
- OpenClaw internal `wakatime-im` hook for `message:received`, `message:sent`, and `command`.
- Hook-to-WakaTime event mapping for IM entities (`openclaw://im/...`) and command entities.

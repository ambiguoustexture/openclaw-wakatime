# Changelog

All notable changes to this project are documented in this file.

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

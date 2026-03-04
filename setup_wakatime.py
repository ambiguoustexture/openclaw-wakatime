#!/usr/bin/env python3
"""
Setup script for WakaTime OpenClaw plugin.

Features:
- validates WakaTime prerequisites
- installs compatibility symlinks under ~/.openclaw/plugins
- configures OpenClaw internal hook loading for hooks/wakatime-im
- optionally restarts OpenClaw gateway and verifies hook readiness
"""

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

REPO_DIR = Path(__file__).resolve().parent
OPENCLAW_STATE_DIR = Path.home() / ".openclaw"
OPENCLAW_PLUGIN_DIR = OPENCLAW_STATE_DIR / "plugins"
OPENCLAW_CONFIG_FILE = OPENCLAW_STATE_DIR / "openclaw.json"
CONFIG_DIR = OPENCLAW_STATE_DIR / "wakatime"
WAKATIME_CONFIG_FILE = Path.home() / ".wakatime.cfg"
ZSHRC = Path.home() / ".zshrc"

PLUGIN_FILES = [
    "wakatime_openclaw.py",
    "wakatime_hooks.py",
    "wakatime_wrapper.py",
]
HOOKS_DIR = REPO_DIR / "hooks"
HOOK_KEY = "wakatime-im"
HOOK_FILE = "zsh-wakatime-hook.sh"


def check_wakatime() -> tuple[bool, str]:
    wakatime_bin = Path.home() / ".local" / "bin" / "wakatime"
    if wakatime_bin.exists():
        result = subprocess.run([str(wakatime_bin), "--version"], capture_output=True, text=True, check=False)
        return True, result.stdout.strip()

    path_bin = shutil.which("wakatime")
    if path_bin:
        result = subprocess.run([path_bin, "--version"], capture_output=True, text=True, check=False)
        return True, result.stdout.strip()
    return False, ""


def _mask_api_key(value: str) -> str:
    token = (value or "").strip()
    if len(token) > 14:
        return f"{token[:10]}...{token[-4:]}"
    if token:
        return "***"
    return ""


def read_api_key(config_file: Path = WAKATIME_CONFIG_FILE) -> str:
    if not config_file.exists():
        return ""

    for line in config_file.read_text().splitlines():
        clean = line.strip()
        if clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        if key.strip() == "api_key":
            return value.strip()
    return ""


def upsert_wakatime_config(content: str, api_key: str) -> str:
    normalized_key = api_key.strip()
    lines = content.splitlines()
    if not lines:
        return f"[settings]\napi_key = {normalized_key}\n"

    in_settings = False
    found = False
    settings_seen = False
    insert_at = None

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_settings and insert_at is None:
                insert_at = idx
            in_settings = stripped.lower() == "[settings]"
            settings_seen = settings_seen or in_settings
            continue
        if in_settings and stripped and not stripped.startswith("#") and "=" in stripped:
            key, _value = stripped.split("=", 1)
            if key.strip() == "api_key":
                lines[idx] = f"api_key = {normalized_key}"
                found = True

    if not found:
        if settings_seen:
            if insert_at is None:
                insert_at = len(lines)
            lines.insert(insert_at, f"api_key = {normalized_key}")
        else:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend(["[settings]", f"api_key = {normalized_key}"])

    return "\n".join(lines).rstrip() + "\n"


def write_api_key(api_key: str, config_file: Path = WAKATIME_CONFIG_FILE) -> tuple[bool, str]:
    try:
        current = config_file.read_text(encoding="utf-8") if config_file.exists() else ""
        updated = upsert_wakatime_config(current, api_key)
        config_file.write_text(updated, encoding="utf-8")
        config_file.chmod(0o600)
        return True, str(config_file)
    except Exception as exc:
        return False, str(exc)


def ensure_api_key(
    cli_key: str = "",
    non_interactive: bool = False,
    save_key: bool = True,
    config_file: Path = WAKATIME_CONFIG_FILE,
) -> tuple[bool, str, str]:
    provided = (cli_key or "").strip()
    if provided:
        os.environ["WAKATIME_API_KEY"] = provided
        if save_key:
            ok, _ = write_api_key(provided, config_file=config_file)
            if not ok:
                return False, "", "write-failed"
        return True, _mask_api_key(provided), "arg"

    file_key = read_api_key(config_file=config_file)
    if file_key:
        os.environ["WAKATIME_API_KEY"] = file_key
        return True, _mask_api_key(file_key), "config"

    env_key = os.environ.get("WAKATIME_API_KEY", "").strip()
    if env_key:
        return True, _mask_api_key(env_key), "env"

    if non_interactive or not sys.stdin.isatty():
        return False, "", "missing"

    prompt_key = input("   Enter your WakaTime API key (starts with waka_): ").strip()
    if not prompt_key:
        return False, "", "missing"

    os.environ["WAKATIME_API_KEY"] = prompt_key
    if save_key:
        ok, _ = write_api_key(prompt_key, config_file=config_file)
        if not ok:
            return False, "", "write-failed"
    return True, _mask_api_key(prompt_key), "prompt"


def install_plugin_files() -> bool:
    OPENCLAW_PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    ok = True

    for file_name in PLUGIN_FILES:
        src = REPO_DIR / file_name
        dst = OPENCLAW_PLUGIN_DIR / file_name
        if not src.exists():
            print(f"   ✗ Missing source file: {src}")
            ok = False
            continue

        if dst.exists() or dst.is_symlink():
            same_link = dst.is_symlink() and dst.resolve() == src.resolve()
            if same_link:
                print(f"   ✓ Linked: {dst} -> {src}")
                continue
            backup = Path(f"{dst}.bak-{int(time.time())}")
            dst.rename(backup)
            print(f"   ↺ Backed up existing file: {backup}")

        try:
            dst.symlink_to(src)
            print(f"   ✓ Symlinked: {dst} -> {src}")
        except OSError:
            shutil.copy2(src, dst)
            print(f"   ✓ Copied: {dst}")

    return ok


def install_zsh_integration() -> None:
    hook_path = REPO_DIR / HOOK_FILE
    if not hook_path.exists():
        print(f"   ! Skip zsh hook: not found ({hook_path})")
        return

    marker = "# WakaTime OpenClaw Integration"
    existing = ZSHRC.read_text() if ZSHRC.exists() else ""
    if marker in existing:
        print("   ✓ Zsh integration already installed")
        return

    integration = f"""
{marker}
source {hook_path}
alias waka-status='python3 {OPENCLAW_PLUGIN_DIR}/wakatime_openclaw.py --status'
alias waka-stats='python3 -c "import json,sys;sys.path.insert(0, \\"{OPENCLAW_PLUGIN_DIR}\\");from wakatime_openclaw import get_wakatime_stats;print(json.dumps(get_wakatime_stats(), indent=2))"'
"""
    with open(ZSHRC, "a", encoding="utf-8") as file_obj:
        file_obj.write(integration)
    print(f"   ✓ Zsh integration added to {ZSHRC}")


def _ensure_dict(parent: Dict[str, Any], key: str) -> Tuple[Dict[str, Any], bool]:
    current = parent.get(key)
    if isinstance(current, dict):
        return current, False
    parent[key] = {}
    return parent[key], True


def apply_hook_config(config: Dict[str, Any], hook_dir: str, hook_key: str = HOOK_KEY) -> tuple[Dict[str, Any], bool]:
    next_cfg = copy.deepcopy(config)
    changed = False

    hooks, ch = _ensure_dict(next_cfg, "hooks")
    changed = changed or ch
    internal, ch = _ensure_dict(hooks, "internal")
    changed = changed or ch

    if internal.get("enabled") is not True:
        internal["enabled"] = True
        changed = True

    load, ch = _ensure_dict(internal, "load")
    changed = changed or ch
    extra_dirs_raw = load.get("extraDirs", [])
    if not isinstance(extra_dirs_raw, list):
        extra_dirs = [str(extra_dirs_raw)]
        changed = True
    else:
        extra_dirs = [str(item) for item in extra_dirs_raw]
    normalized = str(Path(hook_dir).expanduser().resolve())
    if normalized not in extra_dirs:
        extra_dirs.append(normalized)
        changed = True
    load["extraDirs"] = extra_dirs

    entries, ch = _ensure_dict(internal, "entries")
    changed = changed or ch
    entry_raw = entries.get(hook_key)
    entry = copy.deepcopy(entry_raw) if isinstance(entry_raw, dict) else {}
    if entry_raw is None:
        changed = True
    if entry.get("enabled") is not True:
        entry["enabled"] = True
        changed = True
    entries[hook_key] = entry

    return next_cfg, changed


def configure_openclaw_hooks() -> bool:
    if not OPENCLAW_CONFIG_FILE.exists():
        print(f"   ✗ OpenClaw config not found: {OPENCLAW_CONFIG_FILE}")
        return False
    if not HOOKS_DIR.exists():
        print(f"   ✗ Hooks directory not found: {HOOKS_DIR}")
        return False

    try:
        current = json.loads(OPENCLAW_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"   ✗ Failed to parse OpenClaw config: {exc}")
        return False

    updated, changed = apply_hook_config(current, str(HOOKS_DIR), HOOK_KEY)
    if not changed:
        print("   ✓ OpenClaw hook config already up to date")
        return True

    backup = Path(f"{OPENCLAW_CONFIG_FILE}.bak-{int(time.time())}")
    shutil.copy2(OPENCLAW_CONFIG_FILE, backup)
    OPENCLAW_CONFIG_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"   ✓ Updated OpenClaw config: {OPENCLAW_CONFIG_FILE}")
    print(f"   ✓ Backup created: {backup}")
    return True


def _run_openclaw(args: list[str], timeout: int = 30) -> tuple[bool, str]:
    openclaw_bin = shutil.which("openclaw")
    if not openclaw_bin:
        return False, "openclaw CLI not found in PATH"

    result = subprocess.run(
        [openclaw_bin, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    text = output or error
    if result.returncode != 0:
        return False, text or f"openclaw {' '.join(args)} failed with exit {result.returncode}"
    return True, text


def restart_gateway() -> bool:
    ok, message = _run_openclaw(["gateway", "restart"], timeout=45)
    if ok:
        print("   ✓ OpenClaw gateway restarted")
        return True
    print(f"   ! Gateway restart failed: {message}")
    return False


def verify_hook() -> bool:
    ok, message = _run_openclaw(["hooks", "info", HOOK_KEY], timeout=30)
    if not ok:
        print(f"   ! Hook verification failed: {message}")
        return False
    if "Ready" in message or "ready" in message:
        print(f"   ✓ Hook verified: {HOOK_KEY} is ready")
        return True
    print(f"   ! Hook found but not marked ready: {HOOK_KEY}")
    return False


def test_integration() -> bool:
    cmd = ["python3", str(OPENCLAW_PLUGIN_DIR / "wakatime_openclaw.py"), "--test"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print("   ✗ Test heartbeat failed")
        if result.stderr.strip():
            print(f"     {result.stderr.strip().splitlines()[-1]}")
        return False
    print("   ✓ Test heartbeat sent")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup WakaTime for OpenClaw")
    parser.add_argument(
        "--waka-key",
        default="",
        help="Provide WakaTime API key for fresh setup (recommended in CI/non-interactive runs)",
    )
    parser.add_argument(
        "--no-save-key",
        action="store_true",
        help="Do not write API key to ~/.wakatime.cfg (use env/process only)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt for missing API key; fail instead",
    )
    parser.add_argument(
        "--no-zsh",
        action="store_true",
        help="Skip zsh shell integration",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Do not restart OpenClaw gateway after config changes",
    )
    parser.add_argument(
        "--no-test",
        action="store_true",
        help="Skip sending WakaTime test heartbeat",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("WakaTime for OpenClaw - Setup")
    print("=" * 50)

    print("\n1. Checking prerequisites...")
    has_wakatime, version = check_wakatime()
    if not has_wakatime:
        print("   ✗ WakaTime CLI not found")
        print("   Run: pip install --user wakatime")
        return 1
    print(f"   ✓ WakaTime CLI: {version}")

    save_key = not args.no_save_key
    has_key, key_preview, key_source = ensure_api_key(
        cli_key=args.waka_key,
        non_interactive=args.non_interactive,
        save_key=save_key,
    )
    if not has_key:
        if key_source == "write-failed":
            print("   ✗ Failed to write API key to ~/.wakatime.cfg")
            print("   Try using --no-save-key or ensure write permissions for ~/.wakatime.cfg")
            return 1
        print("   ✗ API key not found")
        print("   Provide one using --waka-key <WAKA_KEY>, or set WAKATIME_API_KEY env.")
        if not args.non_interactive:
            print("   For interactive setup, run this in a terminal and enter key when prompted.")
        return 1
    source_label = {
        "arg": "--waka-key",
        "config": "~/.wakatime.cfg",
        "env": "WAKATIME_API_KEY",
        "prompt": "prompt",
    }.get(key_source, key_source)
    print(f"   ✓ API key: {key_preview} (source: {source_label})")
    if key_source in {"arg", "prompt"} and save_key:
        print("   ✓ Saved API key to ~/.wakatime.cfg")
    if key_source in {"arg", "prompt"} and not save_key:
        print("   ! API key is not persisted (--no-save-key); it will be required again next run")

    print("\n2. Installing compatibility plugin files...")
    if not install_plugin_files():
        return 1

    print("\n3. Configuring OpenClaw internal hooks...")
    if not configure_openclaw_hooks():
        return 1

    print("\n4. Verifying hook registration...")
    hook_ok = verify_hook()

    if not args.no_restart:
        print("\n5. Restarting OpenClaw gateway...")
        restart_gateway()
        print("\n6. Re-checking hook status after restart...")
        hook_ok = verify_hook() or hook_ok
    else:
        print("\n5. Skipping gateway restart (--no-restart)")

    if not args.no_zsh:
        print("\n7. Installing zsh integration...")
        install_zsh_integration()
    else:
        print("\n7. Skipping zsh integration (--no-zsh)")

    if not args.no_test:
        print("\n8. Sending test heartbeat...")
        if not test_integration():
            return 1
    else:
        print("\n8. Skipping test heartbeat (--no-test)")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    print("\nSetup complete.")
    print("Next steps:")
    print("1. If shell aliases were installed, run: source ~/.zshrc")
    print("2. Check plugin status: waka-status")
    print("3. Open dashboard: https://wakatime.com/dashboard")
    if not hook_ok:
        print("4. Run `openclaw hooks list` and `openclaw hooks info wakatime-im` to troubleshoot hook status.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

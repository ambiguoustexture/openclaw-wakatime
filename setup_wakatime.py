#!/usr/bin/env python3
"""
Setup script for WakaTime OpenClaw plugin.
Installs plugin files into ~/.openclaw/plugins and optional zsh integration.
"""

import shutil
import subprocess
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
OPENCLAW_PLUGIN_DIR = Path.home() / ".openclaw" / "plugins"
CONFIG_DIR = Path.home() / ".openclaw" / "wakatime"
ZSHRC = Path.home() / ".zshrc"

PLUGIN_FILES = [
    "wakatime_openclaw.py",
    "wakatime_hooks.py",
    "wakatime_wrapper.py",
]
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


def check_api_key() -> tuple[bool, str]:
    config_file = Path.home() / ".wakatime.cfg"
    if not config_file.exists():
        return False, ""

    for line in config_file.read_text().splitlines():
        clean = line.strip()
        if clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        if key.strip() == "api_key":
            token = value.strip()
            if len(token) > 14:
                return True, f"{token[:10]}...{token[-4:]}"
            return True, "***"
    return False, ""


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


def install_zsh_integration():
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

    has_key, key_preview = check_api_key()
    if not has_key:
        print("   ✗ API key not found in ~/.wakatime.cfg")
        return 1
    print(f"   ✓ API key: {key_preview}")

    print("\n2. Installing plugin files...")
    if not install_plugin_files():
        return 1

    print("\n3. Installing zsh integration...")
    install_zsh_integration()

    print("\n4. Sending test heartbeat...")
    if not test_integration():
        return 1

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    print("\nSetup complete.")
    print("Next steps:")
    print("1. Reload shell: source ~/.zshrc")
    print("2. Check status: waka-status")
    print("3. Open dashboard: https://wakatime.com/dashboard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

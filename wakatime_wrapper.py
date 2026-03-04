#!/usr/bin/env python3
"""
WakaTime OpenClaw - Wrapper Integration.
Wrap OpenClaw-style tool/file operations with tracking hooks.
"""

import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from wakatime_hooks import get_hooks  # noqa: E402


def _abs_path(filepath: str) -> str:
    path = Path(filepath).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        return str(path.resolve())
    except Exception:
        return str(path)


class TrackedTool:
    """Base class for tracked tools."""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.hooks = get_hooks()

    @contextmanager
    def track(self, args: Optional[Dict[str, Any]] = None):
        self.hooks.on_tool_call_start(self.tool_name, args or {})
        try:
            yield
            success = True
        except Exception:
            success = False
            raise
        finally:
            self.hooks.on_tool_call_end(self.tool_name, success)


class TrackedExec:
    """Tracked shell command runner."""

    def __init__(self):
        self.hooks = get_hooks()

    def run(self, command: str, **kwargs) -> subprocess.CompletedProcess:
        self.hooks.on_exec_start(command)
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                **kwargs,
            )
            self.hooks.on_exec_end(result.returncode)
            return result
        except Exception:
            self.hooks.on_exec_end(-1)
            raise


class TrackedRead:
    """Tracked file read helper."""

    def __init__(self):
        self.hooks = get_hooks()

    def read_file(self, filepath: str, **kwargs) -> str:
        path = Path(_abs_path(filepath))
        content = path.read_text(**kwargs)
        self.hooks.on_file_open(str(path), len(content.splitlines()))
        return content

    def read_lines(self, filepath: str, limit: Optional[int] = None, offset: int = 0) -> List[str]:
        path = Path(_abs_path(filepath))
        content = path.read_text()
        lines = content.splitlines()
        if offset > 0:
            lines = lines[offset:]
        if limit is not None:
            lines = lines[:limit]
        self.hooks.on_file_open(str(path), len(lines))
        return lines


class TrackedWrite:
    """Tracked file write helper."""

    def __init__(self):
        self.hooks = get_hooks()

    def write_file(self, filepath: str, content: str, mode: str = "w") -> int:
        path = Path(_abs_path(filepath))
        old_lines = 0
        if path.exists():
            old_lines = len(path.read_text().splitlines())

        with open(path, mode, encoding="utf-8") as file_obj:
            written = file_obj.write(content)

        if "a" in mode and old_lines > 0:
            new_lines = len(path.read_text().splitlines())
        else:
            new_lines = len(content.splitlines())
        additions = max(0, new_lines - old_lines)
        deletions = max(0, old_lines - new_lines)
        self.hooks.on_file_edit(str(path), new_lines, additions, deletions)
        return written

    def edit_file(self, filepath: str, old_text: str, new_text: str) -> bool:
        path = Path(_abs_path(filepath))
        content = path.read_text()
        if old_text not in content:
            return False

        old_lines = len(content.splitlines())
        new_content = content.replace(old_text, new_text)
        new_lines = len(new_content.splitlines())
        path.write_text(new_content, encoding="utf-8")
        additions = max(0, new_lines - old_lines)
        deletions = max(0, old_lines - new_lines)
        self.hooks.on_file_edit(str(path), new_lines, additions, deletions)
        return True


def tracked_exec(command: str, timeout: Optional[int] = None) -> str:
    tracker = TrackedExec()
    result = tracker.run(command, timeout=timeout)
    return result.stdout


def tracked_read(filepath: str, limit: Optional[int] = None, offset: int = 0) -> str:
    tracker = TrackedRead()
    if limit is not None or offset > 0:
        lines = tracker.read_lines(filepath, limit, offset)
        return "\n".join(lines)
    return tracker.read_file(filepath)


def tracked_write(filepath: str, content: str, mode: str = "w") -> None:
    tracker = TrackedWrite()
    tracker.write_file(filepath, content, mode=mode)


def tracked_edit(filepath: str, old_text: str, new_text: str) -> bool:
    tracker = TrackedWrite()
    return tracker.edit_file(filepath, old_text, new_text)


@contextmanager
def tracked_session(session_id: str, context: str = ""):
    from wakatime_hooks import end_tracking, start_tracking

    start_tracking(session_id, context)
    try:
        yield
    finally:
        end_tracking(session_id)


if __name__ == "__main__":
    print("WakaTime OpenClaw Wrapper")
    print("=" * 40)
    with tracked_session("test-session", "Testing wrapper integration"):
        print("Session started...")
        test_file = "/tmp/wakatime_test.txt"
        tracked_write(test_file, "Line 1\nLine 2\nLine 3")
        print(f"Wrote: {test_file}")
        content = tracked_read(test_file)
        print(f"Read: {len(content)} chars")
        tracked_edit(test_file, "Line 2", "Line 2 Modified")
        print("Edited file")
        print("Session ending...")
    print("=" * 40)
    print("Check https://wakatime.com/dashboard for activity")

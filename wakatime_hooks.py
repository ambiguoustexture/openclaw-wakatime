#!/usr/bin/env python3
"""
WakaTime OpenClaw Hook Integration.
Maps OpenClaw lifecycle events to WakaTime heartbeats.
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict

# Add plugin directory to import path.
plugin_dir = Path(__file__).parent
sys.path.insert(0, str(plugin_dir))

from wakatime_openclaw import (  # noqa: E402
    get_wakatime_stats,
    track_file_read,
    track_file_write,
    track_session_end,
    track_session_start,
    track_tool,
)


class OpenClawWakaTimeHooks:
    """
    Hook handlers for OpenClaw events.
    """

    def __init__(self):
        self.session_id = ""
        self.session_start_time = 0.0
        self.session_tokens_in = 0
        self.session_tokens_out = 0
        self.files_accessed: set[str] = set()
        self._tool_start_time = 0.0
        self._current_tool = ""
        self._current_tool_args: Dict[str, Any] = {}
        self._exec_start_time = 0.0
        self._exec_command = ""

    def on_conversation_start(self, conversation_id: str, context: str = ""):
        self.session_id = conversation_id
        self.session_start_time = time.time()
        self.session_tokens_in = 0
        self.session_tokens_out = 0
        self.files_accessed.clear()
        track_session_start(conversation_id, context)
        print(f"[wakatime] Session tracked: {conversation_id}")

    def on_conversation_end(self, conversation_id: str):
        if self.session_start_time:
            duration = time.time() - self.session_start_time
            track_session_end(
                conversation_id,
                duration,
                self.session_tokens_in,
                self.session_tokens_out,
            )
            print(f"[wakatime] Session ended: {duration:.1f}s")

        self.session_id = ""
        self.session_start_time = 0.0

    def on_token_usage(self, tokens_in: int, tokens_out: int):
        self.session_tokens_in += tokens_in
        self.session_tokens_out += tokens_out

    def on_file_open(self, filepath: str, line_count: int = 0):
        if filepath not in self.files_accessed:
            track_file_read(filepath, line_count)
            self.files_accessed.add(filepath)
            print(f"[wakatime] File read: {filepath}")

    def on_file_edit(self, filepath: str, line_count: int, additions: int = 0, deletions: int = 0):
        track_file_write(filepath, line_count, additions, deletions)
        print(f"[wakatime] File edited: {filepath}")

    def on_file_save(self, filepath: str):
        # A save event is represented as a write heartbeat without line deltas.
        track_file_write(filepath, 0, 0, 0)
        print(f"[wakatime] File saved: {filepath}")

    def on_tool_call_start(self, tool_name: str, args: Dict[str, Any]):
        self._tool_start_time = time.time()
        self._current_tool = tool_name
        self._current_tool_args = args

    def on_tool_call_end(self, tool_name: str, success: bool):
        if self._tool_start_time and self._current_tool == tool_name:
            duration = time.time() - self._tool_start_time
            track_tool(tool_name, duration, self._current_tool_args)
            status = "success" if success else "failed"
            print(f"[wakatime] Tool {tool_name}: {status} ({duration:.2f}s)")
            self._tool_start_time = 0.0
            self._current_tool = ""
            self._current_tool_args = {}

    def on_exec_start(self, command: str):
        self._exec_start_time = time.time()
        self._exec_command = command[:100]

    def on_exec_end(self, exit_code: int):
        if self._exec_start_time:
            duration = time.time() - self._exec_start_time
            track_tool("exec", duration, {"command_preview": self._exec_command, "exit_code": exit_code})
            print(f"[wakatime] Exec completed: exit={exit_code}, time={duration:.2f}s")
            self._exec_start_time = 0.0
            self._exec_command = ""

    def on_web_search(self, query: str, result_count: int):
        track_tool("web_search", 2.0, {"query": query[:50], "results": result_count})

    def on_sessions_spawn(self, agent_id: str, mode: str, runtime: str):
        track_tool(
            f"sessions_spawn.{runtime}",
            5.0,
            {"agent": agent_id, "mode": mode},
        )

    def on_browser_use(self, url: str, action: str):
        track_tool("browser", 3.0, {"url": url[:50], "action": action})


_hooks: OpenClawWakaTimeHooks | None = None


def get_hooks() -> OpenClawWakaTimeHooks:
    global _hooks
    if _hooks is None:
        _hooks = OpenClawWakaTimeHooks()
    return _hooks


def start_tracking(conversation_id: str, context: str = ""):
    get_hooks().on_conversation_start(conversation_id, context)


def end_tracking(conversation_id: str):
    get_hooks().on_conversation_end(conversation_id)


def track_read_file(filepath: str, lines: int = 0):
    get_hooks().on_file_open(filepath, lines)


def track_edit_file(filepath: str, lines: int = 0, additions: int = 0, deletions: int = 0):
    get_hooks().on_file_edit(filepath, lines, additions, deletions)


def track_exec(command: str, exit_code: int = 0):
    hooks = get_hooks()
    hooks.on_exec_start(command)
    hooks.on_exec_end(exit_code)


def get_stats():
    return get_wakatime_stats()


if __name__ == "__main__":
    print("WakaTime OpenClaw Hooks")
    print("Import this module to integrate with OpenClaw")

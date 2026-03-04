#!/usr/bin/env python3
"""
WakaTime for OpenClaw - Core Plugin.
Tracks session/file/tool activity and reports it using WakaTime CLI.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

PLUGIN_VERSION = "1.1.0"
OPENCLAW_CONFIG_FILE = Path.home() / ".openclaw" / "openclaw.json"


def _extract_version(text: str) -> str:
    """
    Extract version-like token from text.
    Examples: 2026.3.2, 1.1.0, 1.2.3-beta.1
    """
    match = re.search(r"([0-9]+(?:\.[0-9]+)+(?:[-+._][A-Za-z0-9._-]+)?)", text or "")
    return match.group(1) if match else ""


def detect_openclaw_version() -> str:
    env_version = os.environ.get("OPENCLAW_VERSION", "").strip()
    if env_version:
        return env_version

    openclaw_bin = shutil.which("openclaw")
    if openclaw_bin:
        try:
            result = subprocess.run(
                [openclaw_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            output = (result.stdout or "").strip() or (result.stderr or "").strip()
            parsed = _extract_version(output)
            if parsed:
                return parsed
        except Exception:
            pass

    if OPENCLAW_CONFIG_FILE.exists():
        try:
            payload = json.loads(OPENCLAW_CONFIG_FILE.read_text())
            raw_version = str(payload.get("meta", {}).get("lastTouchedVersion", "")).strip()
            parsed = _extract_version(raw_version)
            if parsed:
                return parsed
        except Exception:
            pass

    return "unknown"


OPENCLAW_VERSION = detect_openclaw_version()
PLUGIN_ID = f"OpenClaw/{OPENCLAW_VERSION} openclaw-wakatime/{PLUGIN_VERSION}"
DEFAULT_PROJECT = os.environ.get("OPENCLAW_WAKATIME_PROJECT", "agent-vibe-coding").strip() or "agent-vibe-coding"
DEFAULT_CATEGORY = os.environ.get("OPENCLAW_WAKATIME_CATEGORY", "ai coding").strip() or "ai coding"
USE_CONTEXT_PROJECT = (
    os.environ.get("OPENCLAW_WAKATIME_USE_CONTEXT_PROJECT", "0").strip().lower()
    in {"1", "true", "yes", "on"}
)

WAKATIME_DEFAULT_BIN = Path.home() / ".local" / "bin" / "wakatime"
CONFIG_DIR = Path.home() / ".openclaw" / "wakatime"
QUEUE_FILE = CONFIG_DIR / "queue.jsonl"
LOG_FILE = CONFIG_DIR / "plugin.log"
SESSIONS_FILE = CONFIG_DIR / "sessions.jsonl"


@dataclass
class Heartbeat:
    """WakaTime heartbeat structure."""

    entity: str
    timestamp: float
    project: str = DEFAULT_PROJECT
    category: str = DEFAULT_CATEGORY
    language: str = "Markdown"
    entity_type: str = "file"
    lines: int = 0
    line_additions: int = 0
    line_deletions: int = 0
    is_write: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WakaTimeOpenClaw:
    """
    Main plugin class.
    Tracks session lifecycle, file operations, and tool usage.
    """

    def __init__(self):
        self.api_key = self._load_api_key()
        self.wakatime_bin = self._resolve_wakatime_bin()
        self.default_project = DEFAULT_PROJECT
        self.default_category = DEFAULT_CATEGORY
        self.use_context_project = USE_CONTEXT_PROJECT
        self.current_project = self.default_project
        self.heartbeat_interval = 120.0
        self._last_heartbeat_by_entity: Dict[str, float] = {}
        self._ensure_dirs()

    def _ensure_dirs(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _resolve_wakatime_bin(self) -> Optional[str]:
        if WAKATIME_DEFAULT_BIN.exists():
            return str(WAKATIME_DEFAULT_BIN)
        found = shutil.which("wakatime")
        return found

    def _load_api_key(self) -> str:
        config_file = Path.home() / ".wakatime.cfg"
        if config_file.exists():
            for line in config_file.read_text().splitlines():
                clean = line.strip()
                if clean.startswith("#") or "=" not in clean:
                    continue
                key, value = clean.split("=", 1)
                if key.strip() == "api_key":
                    return value.strip()
        return os.environ.get("WAKATIME_API_KEY", "").strip()

    def log(self, message: str):
        timestamp = datetime.now().isoformat()
        with open(LOG_FILE, "a", encoding="utf-8") as file_obj:
            file_obj.write(f"[{timestamp}] {message}\n")

    def _queue_size(self) -> int:
        if not QUEUE_FILE.exists():
            return 0
        return len([line for line in QUEUE_FILE.read_text().splitlines() if line.strip()])

    def _should_send_heartbeat(self, heartbeat: Heartbeat) -> bool:
        if heartbeat.is_write:
            return True
        last = self._last_heartbeat_by_entity.get(heartbeat.entity)
        if last is None:
            return True
        return heartbeat.timestamp - last >= self.heartbeat_interval

    def _build_command(self, heartbeat: Heartbeat) -> list[str]:
        cmd = [
            self.wakatime_bin,
            "--entity",
            heartbeat.entity,
            "--language",
            heartbeat.language,
            "--project",
            heartbeat.project,
            "--category",
            heartbeat.category,
            "--time",
            str(heartbeat.timestamp),
            "--plugin",
            PLUGIN_ID,
        ]

        if heartbeat.entity_type and heartbeat.entity_type != "file":
            cmd.extend(["--entity-type", heartbeat.entity_type])

        if heartbeat.is_write:
            cmd.append("--write")
        if heartbeat.lines > 0:
            cmd.extend(["--lines", str(heartbeat.lines)])
        if heartbeat.line_additions > 0:
            cmd.extend(["--line-additions", str(heartbeat.line_additions)])
        if heartbeat.line_deletions > 0:
            cmd.extend(["--line-deletions", str(heartbeat.line_deletions)])

        return cmd

    def _execute_heartbeat(self, heartbeat: Heartbeat) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                self._build_command(heartbeat),
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except Exception as exc:  # pragma: no cover - defensive
            return False, str(exc)

        if result.returncode != 0:
            error_text = result.stderr.strip() or result.stdout.strip() or "unknown error"
            return False, error_text
        return True, ""

    def send_heartbeat(self, heartbeat: Heartbeat, from_queue: bool = False) -> bool:
        if not self.wakatime_bin:
            self.log("ERROR: wakatime binary not found (tried ~/.local/bin/wakatime and PATH)")
            if not from_queue:
                self._queue_heartbeat(heartbeat)
            return False

        if not from_queue and not self._should_send_heartbeat(heartbeat):
            return True

        ok, error = self._execute_heartbeat(heartbeat)
        if ok:
            self._last_heartbeat_by_entity[heartbeat.entity] = heartbeat.timestamp
            self.log(
                f"Heartbeat sent: entity={heartbeat.entity} project={heartbeat.project} "
                f"entity_type={heartbeat.entity_type}"
            )
            if not from_queue:
                self.process_queue(max_items=10)
            return True

        self.log(f"ERROR sending heartbeat ({heartbeat.entity}): {error}")
        if not from_queue:
            self._queue_heartbeat(heartbeat)
        return False

    def _queue_heartbeat(self, heartbeat: Heartbeat):
        with open(QUEUE_FILE, "a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(heartbeat.to_dict()) + "\n")

    def process_queue(self, max_items: int = 50) -> int:
        """
        Retry queued heartbeats.
        Returns the number of items attempted.
        """
        if not QUEUE_FILE.exists():
            return 0

        raw_lines = [line for line in QUEUE_FILE.read_text().splitlines() if line.strip()]
        attempted = 0
        keep_lines: list[str] = []

        for line in raw_lines:
            if attempted >= max_items:
                keep_lines.append(line)
                continue

            attempted += 1
            try:
                data = json.loads(line)
                if "project" not in data:
                    data["project"] = self.default_project
                if "category" not in data:
                    data["category"] = self.default_category
                if "entity_type" not in data:
                    data["entity_type"] = "file"
                heartbeat = Heartbeat(**data)
            except Exception as exc:
                self.log(f"ERROR parsing queued heartbeat: {exc}")
                continue

            if not self.send_heartbeat(heartbeat, from_queue=True):
                keep_lines.append(line)

        if keep_lines:
            QUEUE_FILE.write_text("\n".join(keep_lines) + "\n", encoding="utf-8")
        else:
            QUEUE_FILE.unlink(missing_ok=True)
        return attempted

    def _normalize_path(self, filepath: str) -> str:
        path = Path(filepath).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        try:
            return str(path.resolve())
        except Exception:
            return str(path)

    def _detect_project(self, context: str) -> str:
        context_lower = context.lower()
        if "research" in context_lower or "factor" in context_lower or "quant" in context_lower:
            return "research"
        if "coding" in context_lower or "codex" in context_lower or "acpx" in context_lower:
            return "coding-agent"
        if "config" in context_lower or "system" in context_lower or "setup" in context_lower:
            return "system-admin"
        if "openclaw" in context_lower:
            return "openclaw"
        return "openclaw-chat"

    def _detect_project_from_path(self, filepath: str) -> str:
        path_lower = filepath.lower()
        if "/research/" in path_lower:
            return "research"
        if "/openclaw/" in path_lower or "/.openclaw/" in path_lower:
            return "openclaw"
        if "/clawspace/" in path_lower or "/workspace/" in path_lower:
            return "clawspace"
        return self.current_project

    def _detect_language(self, filepath: str) -> str:
        ext = Path(filepath).suffix.lower()
        lang_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".json": "JSON",
            ".md": "Markdown",
            ".sh": "Shell",
            ".bash": "Shell",
            ".zsh": "Shell",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".toml": "TOML",
            ".rs": "Rust",
            ".go": "Go",
            ".cpp": "C++",
            ".c": "C",
            ".h": "C++",
            ".hpp": "C++",
            ".java": "Java",
            ".scala": "Scala",
            ".sql": "SQL",
            ".rb": "Ruby",
            ".php": "PHP",
            ".html": "HTML",
            ".css": "CSS",
        }
        return lang_map.get(ext, "Text")

    def _sanitize_fragment(self, value: str, fallback: str = "unknown") -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._:-]+", "_", (value or "").strip())
        return cleaned or fallback

    def on_session_start(self, session_id: str, context: str = ""):
        self.current_project = (
            self._detect_project(context) if self.use_context_project else self.default_project
        )
        heartbeat = Heartbeat(
            entity=f"openclaw://session/{session_id}",
            timestamp=time.time(),
            project=self.current_project,
            category=self.default_category,
            language="Markdown",
            entity_type="app",
            is_write=True,
        )
        self.send_heartbeat(heartbeat)
        self.log(f"Session started: {session_id}")

    def on_session_end(
        self,
        session_id: str,
        duration: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ):
        heartbeat = Heartbeat(
            entity=f"openclaw://session/{session_id}",
            timestamp=time.time(),
            project=self.current_project,
            category=self.default_category,
            language="Markdown",
            entity_type="app",
            is_write=True,
        )
        self.send_heartbeat(heartbeat)
        self.log(
            f"Session ended: {session_id}, duration={duration:.2f}s, "
            f"tokens={tokens_in}+{tokens_out}"
        )

        with open(SESSIONS_FILE, "a", encoding="utf-8") as file_obj:
            file_obj.write(
                json.dumps(
                    {
                        "session_id": session_id,
                        "end_time": datetime.now().isoformat(),
                        "duration": duration,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "project": self.current_project,
                    }
                )
                + "\n"
            )

    def on_file_read(self, filepath: str, lines: int = 0):
        normalized = self._normalize_path(filepath)
        heartbeat = Heartbeat(
            entity=normalized,
            timestamp=time.time(),
            project=(
                self._detect_project_from_path(normalized)
                if self.use_context_project
                else self.default_project
            ),
            category=self.default_category,
            language=self._detect_language(normalized),
            entity_type="file",
            lines=lines,
            is_write=False,
        )
        self.send_heartbeat(heartbeat)

    def on_file_write(self, filepath: str, lines: int, additions: int = 0, deletions: int = 0):
        normalized = self._normalize_path(filepath)
        heartbeat = Heartbeat(
            entity=normalized,
            timestamp=time.time(),
            project=(
                self._detect_project_from_path(normalized)
                if self.use_context_project
                else self.default_project
            ),
            category=self.default_category,
            language=self._detect_language(normalized),
            entity_type="file",
            lines=lines,
            line_additions=additions,
            line_deletions=deletions,
            is_write=True,
        )
        self.send_heartbeat(heartbeat)

    def on_tool_use(self, tool_name: str, duration: float, args: Optional[Dict[str, Any]] = None):
        heartbeat = Heartbeat(
            entity=f"openclaw://tool/{tool_name}",
            timestamp=time.time(),
            project=self.current_project,
            category=self.default_category,
            language="Shell" if tool_name == "exec" else "Markdown",
            entity_type="app",
            is_write=False,
        )
        self.send_heartbeat(heartbeat)
        self.log(f"Tool used: {tool_name}, duration={duration:.2f}s, args={args or {}}")

    def on_internal_hook_event(
        self,
        event_type: str,
        action: str,
        session_key: str = "",
        context: Optional[Dict[str, Any]] = None,
    ):
        context = context or {}
        safe_type = self._sanitize_fragment(event_type, "event")
        safe_action = self._sanitize_fragment(action, "unknown")
        safe_session = self._sanitize_fragment(session_key, "unknown")

        if event_type == "message":
            channel = self._sanitize_fragment(str(context.get("channelId", "")), "unknown")
            conversation = self._sanitize_fragment(
                str(context.get("conversationId", "")) or session_key,
                safe_session,
            )
            entity = f"openclaw://im/{channel}/{safe_action}/{conversation}"
            language = "Markdown"
            is_write = True
        elif event_type == "command":
            entity = f"openclaw://command/{safe_action}/{safe_session}"
            language = "Markdown"
            is_write = False
        else:
            entity = f"openclaw://event/{safe_type}/{safe_action}/{safe_session}"
            language = "Markdown"
            is_write = False

        heartbeat = Heartbeat(
            entity=entity,
            timestamp=time.time(),
            project=self.default_project,
            category=self.default_category,
            language=language,
            entity_type="app",
            is_write=is_write,
        )
        self.send_heartbeat(heartbeat)
        self.log(
            "Internal hook tracked: "
            f"type={event_type}, action={action}, session_key={session_key}, entity={entity}"
        )

    def get_stats(self) -> Dict[str, Any]:
        stats = {
            "total_sessions": 0,
            "total_time": 0.0,
            "total_tokens": 0,
            "projects": set(),
        }
        if SESSIONS_FILE.exists():
            with open(SESSIONS_FILE, encoding="utf-8") as file_obj:
                for line in file_obj:
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue
                    stats["total_sessions"] += 1
                    stats["total_time"] += float(data.get("duration", 0) or 0)
                    stats["total_tokens"] += int(data.get("tokens_in", 0) or 0) + int(
                        data.get("tokens_out", 0) or 0
                    )
                    stats["projects"].add(data.get("project", "unknown"))

        stats["projects"] = sorted(stats["projects"])
        return stats

    def get_status(self) -> Dict[str, Any]:
        return {
            "plugin_version": PLUGIN_VERSION,
            "openclaw_version": OPENCLAW_VERSION,
            "plugin_id": PLUGIN_ID,
            "wakatime_bin": self.wakatime_bin or "",
            "api_key_loaded": bool(self.api_key),
            "default_project": self.default_project,
            "default_category": self.default_category,
            "use_context_project": self.use_context_project,
            "queue_size": self._queue_size(),
            "heartbeat_interval_seconds": self.heartbeat_interval,
            "config_dir": str(CONFIG_DIR),
            "log_file": str(LOG_FILE),
        }


_plugin: Optional[WakaTimeOpenClaw] = None


def get_plugin() -> WakaTimeOpenClaw:
    global _plugin
    if _plugin is None:
        _plugin = WakaTimeOpenClaw()
    return _plugin


def track_session_start(session_id: str, context: str = ""):
    get_plugin().on_session_start(session_id, context)


def track_session_end(session_id: str, duration: float, tokens_in: int = 0, tokens_out: int = 0):
    get_plugin().on_session_end(session_id, duration, tokens_in, tokens_out)


def track_file_read(filepath: str, lines: int = 0):
    get_plugin().on_file_read(filepath, lines)


def track_file_write(filepath: str, lines: int, additions: int = 0, deletions: int = 0):
    get_plugin().on_file_write(filepath, lines, additions, deletions)


def track_tool(tool_name: str, duration: float, args: Optional[Dict[str, Any]] = None):
    get_plugin().on_tool_use(tool_name, duration, args)


def track_internal_hook_event(
    event_type: str,
    action: str,
    session_key: str = "",
    context: Optional[Dict[str, Any]] = None,
):
    get_plugin().on_internal_hook_event(event_type, action, session_key, context)


def get_wakatime_stats() -> Dict[str, Any]:
    return get_plugin().get_stats()


def process_pending_heartbeats(max_items: int = 50) -> int:
    return get_plugin().process_queue(max_items=max_items)


def _main() -> int:
    parser = argparse.ArgumentParser(description="WakaTime plugin for OpenClaw")
    parser.add_argument("--status", action="store_true", help="Print plugin runtime status JSON")
    parser.add_argument(
        "--process-queue",
        action="store_true",
        help="Retry queued heartbeats and print attempted count",
    )
    parser.add_argument("--test", action="store_true", help="Send one test session heartbeat")
    parser.add_argument(
        "--track-hook",
        action="store_true",
        help="Track one OpenClaw internal hook event as a WakaTime heartbeat",
    )
    parser.add_argument("--event-type", default="", help="Hook event type, for example: message")
    parser.add_argument("--event-action", default="", help="Hook event action, for example: received")
    parser.add_argument("--session-key", default="", help="Hook event session key")
    parser.add_argument("--channel-id", default="", help="Hook message channel id")
    parser.add_argument("--conversation-id", default="", help="Hook message conversation id")
    parser.add_argument("--message-id", default="", help="Hook message id")
    args = parser.parse_args()

    plugin = get_plugin()

    if args.status:
        print(json.dumps(plugin.get_status(), indent=2))
        return 0

    if args.process_queue:
        attempted = plugin.process_queue(max_items=100)
        print(f"Processed queued heartbeats: {attempted}")
        return 0

    if args.track_hook:
        if not args.event_type.strip() or not args.event_action.strip():
            parser.error("--track-hook requires --event-type and --event-action")
        context: Dict[str, Any] = {}
        if args.channel_id:
            context["channelId"] = args.channel_id
        if args.conversation_id:
            context["conversationId"] = args.conversation_id
        if args.message_id:
            context["messageId"] = args.message_id
        track_internal_hook_event(
            event_type=args.event_type.strip(),
            action=args.event_action.strip(),
            session_key=args.session_key.strip(),
            context=context,
        )
        print("Hook heartbeat sent")
        return 0

    if args.test or (not args.status and not args.process_queue):
        test_id = f"test-{int(time.time())}"
        track_session_start(test_id, "Testing WakaTime integration")
        print("Test heartbeat sent - check https://wakatime.com/dashboard")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

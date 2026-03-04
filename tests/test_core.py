import time

import wakatime_openclaw as core


def test_build_command_includes_plugin_and_entity_type():
    plugin = core.WakaTimeOpenClaw()
    heartbeat = core.Heartbeat(
        entity="openclaw://session/test-1",
        timestamp=1700000000.0,
        project="openclaw-test",
        language="Markdown",
        entity_type="app",
        is_write=True,
    )
    cmd = plugin._build_command(heartbeat)

    assert "--plugin" in cmd
    assert core.PLUGIN_ID in cmd
    assert "--entity-type" in cmd
    assert "app" in cmd
    assert "--category" in cmd
    assert "ai coding" in cmd
    assert "--time" in cmd


def test_non_write_heartbeat_is_throttled_per_entity():
    plugin = core.WakaTimeOpenClaw()
    hb = core.Heartbeat(
        entity="/tmp/a.py",
        timestamp=time.time(),
        project="p",
        language="Python",
        entity_type="file",
        is_write=False,
    )
    assert plugin._should_send_heartbeat(hb) is True
    plugin._last_heartbeat_by_entity[hb.entity] = hb.timestamp
    hb2 = core.Heartbeat(
        entity=hb.entity,
        timestamp=hb.timestamp + 10.0,
        project="p",
        language="Python",
        entity_type="file",
        is_write=False,
    )
    assert plugin._should_send_heartbeat(hb2) is False


def test_normalize_path_returns_absolute_path():
    plugin = core.WakaTimeOpenClaw()
    normalized = plugin._normalize_path("README.md")
    assert normalized.startswith("/")


def test_default_project_and_category_for_agent_vibe_coding():
    plugin = core.WakaTimeOpenClaw()
    assert plugin.default_project == "agent-vibe-coding"
    assert plugin.default_category == "ai coding"


def test_internal_message_event_tracks_im_entity(monkeypatch):
    plugin = core.WakaTimeOpenClaw()
    sent = []

    def fake_send(heartbeat, from_queue=False):
        sent.append((heartbeat, from_queue))
        return True

    monkeypatch.setattr(plugin, "send_heartbeat", fake_send)
    monkeypatch.setattr(plugin, "log", lambda message: None)
    plugin.on_internal_hook_event(
        event_type="message",
        action="received",
        session_key="agent:main:main",
        context={"channelId": "telegram", "conversationId": "-100123"},
    )

    assert len(sent) == 1
    heartbeat = sent[0][0]
    assert heartbeat.entity.startswith("openclaw://im/telegram/received/")
    assert heartbeat.entity_type == "app"
    assert heartbeat.is_write is True


def test_internal_command_event_tracks_command_entity(monkeypatch):
    plugin = core.WakaTimeOpenClaw()
    sent = []

    def fake_send(heartbeat, from_queue=False):
        sent.append((heartbeat, from_queue))
        return True

    monkeypatch.setattr(plugin, "send_heartbeat", fake_send)
    monkeypatch.setattr(plugin, "log", lambda message: None)
    plugin.on_internal_hook_event(event_type="command", action="new", session_key="agent:main:main")

    assert len(sent) == 1
    heartbeat = sent[0][0]
    assert heartbeat.entity == "openclaw://command/new/agent:main:main"
    assert heartbeat.entity_type == "app"
    assert heartbeat.is_write is False

import setup_wakatime as setup


def test_apply_hook_config_initializes_missing_sections():
    cfg = {}
    hook_dir = "/tmp/openclaw-wakatime-hooks"

    updated, changed = setup.apply_hook_config(cfg, hook_dir, "wakatime-im")

    assert changed is True
    assert updated["hooks"]["internal"]["enabled"] is True
    assert hook_dir in updated["hooks"]["internal"]["load"]["extraDirs"]
    assert updated["hooks"]["internal"]["entries"]["wakatime-im"]["enabled"] is True


def test_apply_hook_config_is_idempotent():
    hook_dir = "/tmp/openclaw-wakatime-hooks"
    cfg = {
        "hooks": {
            "internal": {
                "enabled": True,
                "load": {"extraDirs": [hook_dir]},
                "entries": {"wakatime-im": {"enabled": True}},
            }
        }
    }

    updated, changed = setup.apply_hook_config(cfg, hook_dir, "wakatime-im")

    assert changed is False
    assert updated["hooks"]["internal"]["load"]["extraDirs"].count(hook_dir) == 1


def test_upsert_wakatime_config_creates_settings_block():
    updated = setup.upsert_wakatime_config("", "waka_test_key")
    assert "[settings]" in updated
    assert "api_key = waka_test_key" in updated


def test_upsert_wakatime_config_replaces_existing_key():
    original = "[settings]\napi_key = old_key\n"
    updated = setup.upsert_wakatime_config(original, "waka_new_key")
    assert "api_key = waka_new_key" in updated
    assert "old_key" not in updated


def test_ensure_api_key_from_cli_persists_to_file(tmp_path, monkeypatch):
    cfg = tmp_path / ".wakatime.cfg"
    monkeypatch.delenv("WAKATIME_API_KEY", raising=False)

    ok, preview, source = setup.ensure_api_key(
        cli_key="waka_example_123456",
        non_interactive=True,
        save_key=True,
        config_file=cfg,
    )

    assert ok is True
    assert source == "arg"
    assert preview.startswith("waka_examp")
    assert cfg.exists()
    assert "api_key = waka_example_123456" in cfg.read_text()


def test_ensure_api_key_no_save_keeps_file_absent(tmp_path, monkeypatch):
    cfg = tmp_path / ".wakatime.cfg"
    monkeypatch.delenv("WAKATIME_API_KEY", raising=False)

    ok, preview, source = setup.ensure_api_key(
        cli_key="waka_example_123456",
        non_interactive=True,
        save_key=False,
        config_file=cfg,
    )

    assert ok is True
    assert source == "arg"
    assert preview.startswith("waka_examp")
    assert not cfg.exists()


def test_ensure_api_key_uses_env_when_file_missing(tmp_path, monkeypatch):
    cfg = tmp_path / ".wakatime.cfg"
    monkeypatch.setenv("WAKATIME_API_KEY", "waka_from_env_123456")

    ok, preview, source = setup.ensure_api_key(
        cli_key="",
        non_interactive=True,
        save_key=True,
        config_file=cfg,
    )

    assert ok is True
    assert source == "env"
    assert preview.startswith("waka_from_")

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

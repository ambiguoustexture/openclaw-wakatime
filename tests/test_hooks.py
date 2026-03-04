import wakatime_hooks as hooks


def test_on_file_save_calls_track_file_write(monkeypatch):
    calls = []

    def fake_track_file_write(filepath, lines, additions, deletions):
        calls.append((filepath, lines, additions, deletions))

    monkeypatch.setattr(hooks, "track_file_write", fake_track_file_write)
    instance = hooks.OpenClawWakaTimeHooks()
    instance.on_file_save("/tmp/example.py")

    assert calls == [("/tmp/example.py", 0, 0, 0)]

from zhihu_archive.state import SyncState


def test_complete_scan_marks_missing_deleted():
    state = SyncState()
    state.items["answers:1"] = {"updated": 100, "deleted": False}
    state.items["answers:2"] = {"updated": 100, "deleted": False}
    deleted = state.apply_scan("answers", {"1"}, complete=True)
    assert deleted == {"2"}
    assert state.items["answers:2"]["deleted"] is True


def test_incomplete_scan_changes_nothing():
    state = SyncState()
    state.items["answers:1"] = {"updated": 100, "deleted": False}
    deleted = state.apply_scan("answers", set(), complete=False)
    assert deleted == set()
    assert state.items["answers:1"]["deleted"] is False


def test_reappearing_item_clears_deleted():
    state = SyncState()
    state.items["answers:1"] = {"updated": 100, "deleted": True}
    state.apply_scan("answers", {"1"}, complete=True)
    assert state.items["answers:1"]["deleted"] is False


def test_roundtrip(tmp_path):
    state = SyncState()
    state.items["pins:9"] = {"updated": 1, "deleted": False}
    path = tmp_path / "state.json"
    state.save(path)
    assert SyncState.load(path).items == state.items


def test_needs_update_for_new_or_changed():
    state = SyncState()
    item = type("Item", (), {"kind": "answers", "id": "1", "updated": 100})()
    assert state.needs_update("answers", item) is True
    state.record("answers", item)
    assert state.needs_update("answers", item) is False
    item.updated = 200
    assert state.needs_update("answers", item) is True

import subprocess

import pytest

import sync
from zhihu_archive.client import AuthError
from zhihu_archive.privacy import Finding, ScanReport
from zhihu_archive.sync import SyncReport


def test_scan_hard_finding_blocks_git(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        sync,
        "scan_paths",
        lambda *args, **kwargs: ScanReport(
            hard=[Finding("content/a.md", 1, "zhihu_cookie", "hard", "z_c0=x")]
        ),
    )
    monkeypatch.setattr(sync, "run_git", lambda *args, **kwargs: calls.append(args))
    ok = sync.publish_if_clean(
        tmp_path, tmp_path / "content", tmp_path / ".local", SyncReport(), push=False
    )
    assert ok is False
    assert calls == []


def test_scan_review_finding_blocks_git(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        sync,
        "scan_paths",
        lambda *args, **kwargs: ScanReport(
            review=[Finding("content/a.md", 1, "local_address", "review", "127.0.0.1")]
        ),
    )
    monkeypatch.setattr(sync, "run_git", lambda *args, **kwargs: calls.append(args))
    ok = sync.publish_if_clean(
        tmp_path, tmp_path / "content", tmp_path / ".local", SyncReport(), push=False
    )
    assert ok is False
    assert calls == []


def test_new_images_block_without_approval(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        sync, "scan_paths", lambda *args, **kwargs: ScanReport(images=["content/a.png"])
    )
    monkeypatch.setattr(
        sync, "staged_image_paths", lambda *args, **kwargs: ["content/a.png"]
    )
    monkeypatch.setattr(sync, "run_git", lambda *args, **kwargs: calls.append(args))
    ok = sync.publish_if_clean(
        tmp_path,
        tmp_path / "content",
        tmp_path / ".local",
        SyncReport(),
        push=False,
        images_approved=False,
    )
    assert ok is False
    assert not any("commit" in call or "push" in call for call in calls)


def test_new_images_allowed_with_approval(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        sync, "scan_paths", lambda *args, **kwargs: ScanReport(images=["content/a.png"])
    )
    monkeypatch.setattr(
        sync, "staged_image_paths", lambda *args, **kwargs: ["content/a.png"]
    )
    monkeypatch.setattr(sync, "run_git", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(sync, "staged_changes", lambda *args, **kwargs: True)
    ok = sync.publish_if_clean(
        tmp_path,
        tmp_path / "content",
        tmp_path / ".local",
        SyncReport(added=1),
        push=False,
        images_approved=True,
    )
    assert ok is True
    assert any("commit" in call for call in calls)


def test_publish_scans_and_stages_data_directory(tmp_path, monkeypatch):
    scanned = []
    calls = []
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "zhihu_stats.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sync,
        "scan_paths",
        lambda root, paths, allow: scanned.append(list(paths)) or ScanReport(),
    )
    monkeypatch.setattr(sync, "run_git", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(sync, "staged_changes", lambda *args, **kwargs: True)

    ok = sync.publish_if_clean(
        tmp_path, tmp_path / "content", tmp_path / ".local", SyncReport(), push=False
    )

    assert ok is True
    assert "data" in scanned[0]
    assert any("data" in call for call in calls)


def test_clean_scan_commits_and_pushes(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        sync, "scan_paths", lambda *args, **kwargs: ScanReport()
    )
    monkeypatch.setattr(sync, "run_git", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(sync, "staged_changes", lambda *args, **kwargs: True)
    ok = sync.publish_if_clean(
        tmp_path,
        tmp_path / "content",
        tmp_path / ".local",
        SyncReport(added=2),
        push=True,
    )
    assert ok is True
    assert any("commit" in call for call in calls)
    assert any("push" in call for call in calls)


@pytest.mark.filterwarnings("error::pytest.PytestUnhandledThreadExceptionWarning")
def test_run_git_decodes_utf8_output(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "中文提交信息"], cwd=tmp_path, check=True, capture_output=True
    )
    sync.run_git(tmp_path, "log", "-1", "--oneline")


def test_auth_failure_writes_nothing(tmp_path, monkeypatch):
    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def check_auth(self):
            raise AuthError("expired")

    monkeypatch.setattr(sync, "ZhihuClient", FailingClient)
    monkeypatch.setattr(sync, "load_cookie", lambda *args: "z_c0=x")
    monkeypatch.setattr(
        sync,
        "load_config",
        lambda: {
            "content_root": str(tmp_path / "content"),
            "state_dir": str(tmp_path / ".local"),
        },
    )
    assert sync.main([]) == 2
    assert not (tmp_path / "content").exists()
    assert not (tmp_path / ".local").exists()

import pytest

from zhihu_archive.purge import (
    build_filter_branch_command,
    build_filter_repo_command,
    build_force_push_command,
    content_path,
    ensure_archive_repo,
)


def test_content_path_rejects_unknown_kind():
    with pytest.raises(ValueError):
        content_path("comments", "1")


@pytest.mark.parametrize("bad_id", ["../1", "1/2", "1\\2", "1\n2", "abc"])
def test_content_path_rejects_unsafe_id(bad_id):
    with pytest.raises(ValueError):
        content_path("answers", bad_id)


def test_force_push_command_pins_old_sha():
    command = build_force_push_command("abc123")
    assert command == [
        "git",
        "push",
        "--force-with-lease=main:abc123",
        "origin",
        "main",
    ]


def test_purge_rejects_non_archive_repo(tmp_path):
    (tmp_path / "hugo.yml").write_text('baseURL: "https://example.com/"', encoding="utf-8")
    with pytest.raises(RuntimeError):
        ensure_archive_repo(tmp_path)


def test_archive_repo_is_accepted(tmp_path):
    (tmp_path / "hugo.yml").write_text(
        'baseURL: "https://visionjam.github.io/zhihu-archive/"', encoding="utf-8"
    )
    ensure_archive_repo(tmp_path)


def test_filter_repo_command_contains_path():
    cmd = build_filter_repo_command(["content/answers/456"])
    assert cmd[:2] == ["git", "filter-repo"]
    assert "--invert-paths" in cmd
    assert "content/answers/456" in cmd


def test_filter_branch_command_contains_path():
    cmd = build_filter_branch_command(["content/answers/456"])
    assert cmd[0:2] == ["git", "filter-branch"]
    assert "content/answers/456" in " ".join(cmd)

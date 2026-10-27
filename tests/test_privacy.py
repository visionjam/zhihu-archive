from pathlib import Path

from zhihu_archive.privacy import load_allowlist, scan_paths

ROOT = Path(__file__).resolve().parents[1]


def test_cookie_value_is_hard_finding(tmp_path):
    (tmp_path / "a.md").write_text("z_c0=SECRET", encoding="utf-8")
    report = scan_paths(tmp_path, ["a.md"], set())
    assert not report.ok
    assert report.hard[0].kind == "zhihu_cookie"


def test_localhost_is_review_not_hard(tmp_path):
    (tmp_path / "a.md").write_text("curl http://127.0.0.1:8080", encoding="utf-8")
    report = scan_paths(tmp_path, ["a.md"], set())
    assert report.hard == []
    assert report.review and not report.ok


def test_allowlist_suppresses_review_only(tmp_path):
    (tmp_path / "a.md").write_text("curl http://127.0.0.1:8080", encoding="utf-8")
    allow = {"local_address\ta.md\t127.0.0.1"}
    report = scan_paths(tmp_path, ["a.md"], allow)
    assert report.ok


def test_allowlist_cannot_suppress_hard(tmp_path):
    (tmp_path / "a.md").write_text("z_c0=SECRET", encoding="utf-8")
    allow = {"zhihu_cookie\ta.md\tz_c0=SECRET"}
    report = scan_paths(tmp_path, ["a.md"], allow)
    assert not report.ok


def test_windows_path_is_review_not_hard(tmp_path):
    (tmp_path / "a.md").write_text(r"示例 C:\Windows\System32", encoding="utf-8")
    report = scan_paths(tmp_path, ["a.md"], set())
    assert report.hard == []
    assert report.review and not report.ok


def test_allowlist_checks_every_match_on_a_line(tmp_path):
    (tmp_path / "a.md").write_text(
        "a@example.com and secret@example.com", encoding="utf-8"
    )
    allow = {"email\ta.md\ta@example.com"}
    report = scan_paths(tmp_path, ["a.md"], allow)
    assert not report.ok
    assert any("secret@example.com" in finding.text for finding in report.review)


def test_images_are_listed(tmp_path):
    (tmp_path / "a.png").write_bytes(b"png")
    report = scan_paths(tmp_path, ["a.png"], set())
    assert report.images == ["a.png"]


def test_load_allowlist_ignores_comments(tmp_path):
    path = tmp_path / "allow.txt"
    path.write_text("# comment\nphone_cn\ta.md\t13800138000\n", encoding="utf-8")
    assert load_allowlist(path) == {"phone_cn\ta.md\t13800138000"}


def test_repo_allowlist_covers_public_about_emails():
    allow = load_allowlist(ROOT / "tools" / "privacy_allowlist.txt")
    report = scan_paths(ROOT, ["content/about.md"], allow)
    assert report.review == []

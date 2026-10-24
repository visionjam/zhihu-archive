import pytest

import sync
from zhihu_archive.cookie import CookieFormatError


def test_parse_types():
    assert sync.parse_types("answers,pins") == ("answers", "pins")


def test_parse_types_rejects_unknown():
    with pytest.raises(ValueError):
        sync.parse_types("comments")


def test_check_returns_2_on_cookie_error(monkeypatch):
    def fail():
        raise CookieFormatError("bad cookie")

    monkeypatch.setattr(sync, "load_cookie", fail)
    assert sync.main(["--check"]) == 2


def test_parser_defaults():
    args = sync.build_parser().parse_args([])
    assert args.types == "answers,articles,pins"
    assert args.dry_run is False
    assert args.limit is None
    assert args.refresh_stats is False


def test_refresh_stats_builds_file_without_cookie(tmp_path, monkeypatch):
    import json

    bundle = tmp_path / "content" / "answers" / "a1"
    bundle.mkdir(parents=True)
    (bundle / "index.md").write_text(
        "---\n"
        'title: "回答一"\n'
        "date: 2026-01-02\n"
        "type: answers\n"
        'zhihu_id: "a1"\n'
        "deleted: false\n"
        "---\n"
        "\n"
        "正文\n"
        "\n"
        "---\n"
        "\n"
        "原文链接：[查看知乎原文](https://example.com)\n",
        encoding="utf-8",
    )
    config = {
        "content_root": str(tmp_path / "content"),
        "state_dir": str(tmp_path / ".local"),
        "stats_file": str(tmp_path / "data" / "zhihu_stats.json"),
    }
    monkeypatch.setattr(sync, "load_config", lambda: config)
    monkeypatch.setattr(
        sync,
        "load_cookie",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应读取 Cookie")),
    )

    assert sync.main(["--refresh-stats"]) == 0

    data = json.loads((tmp_path / "data" / "zhihu_stats.json").read_text(encoding="utf-8"))
    assert data["totals"]["items"] == 1
    assert data["items"]["answers:a1"]["word_count"] == 2

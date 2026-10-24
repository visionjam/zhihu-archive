import json
from pathlib import Path

from zhihu_archive.stats import (
    build_stats,
    count_text,
    extract_body,
    load_stats,
    reading_minutes,
    write_stats,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_count_text_ignores_markdown_syntax_and_images():
    markdown = (
        "# 标题\n\n"
        "这是**正文**，[链接](https://example.com)，![image](./a.png)。\n"
    )
    assert count_text(markdown) == 11


def test_count_text_counts_code_content_but_not_fence_language():
    assert count_text("```python\nprint(1)\n```") == 8


def test_reading_minutes_rounds_up_with_a_floor_of_one():
    assert reading_minutes(0) == 0
    assert reading_minutes(1) == 1
    assert reading_minutes(400) == 1
    assert reading_minutes(401) == 2


def test_extract_body_strips_front_matter_and_original_link():
    page = (
        "---\n"
        'title: "标题"\n'
        "deleted: false\n"
        "---\n"
        "\n"
        "正文第一段\n"
        "\n"
        "---\n"
        "\n"
        "原文链接：[查看知乎原文](https://example.com)\n"
    )
    assert extract_body(page) == "正文第一段"


def test_extract_body_removes_deleted_notice_and_keeps_inner_rules():
    page = (
        "---\n"
        'title: "标题"\n'
        "---\n"
        "\n"
        "> 该内容已从知乎删除，本页为归档副本。\n"
        "\n"
        "正文\n"
        "\n"
        "---\n"
        "\n"
        "续文\n"
        "\n"
        "---\n"
        "\n"
        "原文链接：[查看知乎原文](https://example.com)\n"
    )
    assert extract_body(page) == "正文\n\n---\n\n续文"


def make_content(root: Path) -> Path:
    write(
        root / "answers/a1/index.md",
        "---\n"
        'title: "回答一"\n'
        "date: 2026-01-02\n"
        "type: answers\n"
        'zhihu_id: "a1"\n'
        'zhihu_url: "https://www.zhihu.com/question/1/answer/a1"\n'
        "deleted: false\n"
        "---\n"
        "\n"
        "## 标题\n"
        "\n"
        "这是**正文**，[链接](https://example.com)，![image](./a.png)。\n"
        "\n"
        "---\n"
        "\n"
        "原文链接：[查看知乎原文](https://www.zhihu.com/question/1/answer/a1)\n",
    )
    write(
        root / "articles/a2/index.md",
        "---\n"
        'title: "文章二"\n'
        "date: 2026-01-03\n"
        "type: articles\n"
        'zhihu_id: "a2"\n'
        'zhihu_url: "https://zhuanlan.zhihu.com/p/a2"\n'
        "deleted: true\n"
        "---\n"
        "\n"
        "文章正文\n",
    )
    return root


def make_raw(raw_root: Path) -> None:
    write(
        raw_root / "answers/a1.json",
        json.dumps(
            {
                "id": "a1",
                "question": {"id": 1, "title": "回答一"},
                "created_time": 1767312000,
                "content": "<p>正文</p>",
                "reaction": {"statistics": {"like_count": 7}},
                "comment_count": 2,
            },
            ensure_ascii=False,
        ),
    )
    write(
        raw_root / "articles/a2.json",
        json.dumps(
            {
                "id": "a2",
                "title": "文章二",
                "created_time": 1767398400,
                "voteup_count": 4,
                "comment_count": 1,
            },
            ensure_ascii=False,
        ),
    )


def test_build_stats_scans_content_and_uses_fresh_counts(tmp_path):
    content = make_content(tmp_path / "content")
    make_raw(tmp_path / "raw")

    stats = build_stats(
        content,
        tmp_path / "raw",
        fresh={"answers:a1": {"voteup_count": 10, "comment_count": 3}},
    )

    first = stats["items"]["answers:a1"]
    assert first["title"] == "回答一"
    assert first["rel_path"] == "/answers/a1/"
    assert first["created"] == "2026-01-02"
    assert first["deleted"] is False
    assert first["voteup_count"] == 10
    assert first["comment_count"] == 3
    assert first["word_count"] == 11
    assert first["reading_minutes"] == 1

    second = stats["items"]["articles:a2"]
    assert second["voteup_count"] == 4
    assert second["comment_count"] == 1
    assert second["deleted"] is True
    assert second["word_count"] == 4

    assert stats["totals"] == {
        "items": 2,
        "words": 15,
        "votes": 14,
        "comments": 4,
        "by_kind": {"answers": 1, "articles": 1, "pins": 0},
    }


def test_build_stats_prefers_previous_counts_over_cached_raw(tmp_path):
    content = make_content(tmp_path / "content")
    make_raw(tmp_path / "raw")
    previous = {
        "items": {
            "answers:a1": {
                "kind": "answers",
                "id": "a1",
                "voteup_count": 99,
                "comment_count": 9,
            }
        }
    }

    stats = build_stats(content, tmp_path / "raw", previous=previous)

    assert stats["items"]["answers:a1"]["voteup_count"] == 99
    assert stats["items"]["answers:a1"]["comment_count"] == 9
    assert stats["items"]["articles:a2"]["voteup_count"] == 4


def test_write_stats_keeps_timestamp_when_only_timestamp_changes(tmp_path):
    path = tmp_path / "data/zhihu_stats.json"
    write_stats(path, {"generated_at": "2026-01-01T00:00:00+00:00", "items": {}})
    before = path.read_text(encoding="utf-8")

    write_stats(path, {"generated_at": "2026-02-02T00:00:00+00:00", "items": {}})

    assert path.read_text(encoding="utf-8") == before
    assert load_stats(path)["generated_at"] == "2026-01-01T00:00:00+00:00"


def test_write_stats_updates_timestamp_when_data_changes(tmp_path):
    path = tmp_path / "data/zhihu_stats.json"
    write_stats(path, {"generated_at": "2026-01-01T00:00:00+00:00", "items": {}})
    write_stats(
        path,
        {
            "generated_at": "2026-02-02T00:00:00+00:00",
            "items": {"answers:a1": {"voteup_count": 1}},
        },
    )

    assert load_stats(path)["generated_at"] == "2026-02-02T00:00:00+00:00"

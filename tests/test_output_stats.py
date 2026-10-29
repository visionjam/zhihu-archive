import json
from pathlib import Path

import refresh_output_stats


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_archive(root: Path, *, blog_item: dict | None = None) -> None:
    (root / "hugo.yml").write_text(
        'baseURL: "https://example.com/zhihu-archive/"\n', encoding="utf-8"
    )
    data = root / "data"
    data.mkdir(parents=True)
    write_json(
        data / "zhihu_stats.json",
        {
            "version": 1,
            "generated_at": "2026-01-01T00:00:00+08:00",
            "totals": {
                "items": 2,
                "words": 600,
                "votes": 7,
                "comments": 2,
                "by_kind": {"answers": 2},
            },
            "items": {
                "answers:z1": {
                    "kind": "answers",
                    "id": "z1",
                    "title": "知乎一",
                    "url": "https://www.zhihu.com/x",
                    "rel_path": "/answers/z1/",
                    "created": "2026-01-02",
                    "deleted": False,
                    "voteup_count": 7,
                    "comment_count": 2,
                    "word_count": 400,
                    "reading_minutes": 1,
                },
                "answers:z2": {
                    "kind": "answers",
                    "id": "z2",
                    "title": "知乎二",
                    "url": "https://www.zhihu.com/y",
                    "rel_path": "/answers/z2/",
                    "created": "2026-01-03",
                    "deleted": False,
                    "voteup_count": 0,
                    "comment_count": 0,
                    "word_count": 200,
                    "reading_minutes": 1,
                },
            },
        },
    )
    write_json(
        data / "crossposts.json",
        {
            "z1": {
                "url": "https://example.com/posts/a/",
                "title": "知乎一",
                "blog_title": "示例文章",
            }
        },
    )
    write_json(data / "likes.json", {"items": {"/answers/z1/": {"likes": 4}}})
    for slug, lastmod in (("z1", "2026-01-05"), ("z2", None)):
        bundle = root / "content" / "answers" / slug
        bundle.mkdir(parents=True)
        front = f'---\ntitle: "知乎{slug}"\ndate: 2026-01-02\n'
        if lastmod:
            front += f"lastmod: {lastmod}\n"
        front += "---\n\n正文\n"
        (bundle / "index.md").write_text(front, encoding="utf-8")
    if blog_item is not None:
        write_json(
            data / "output_stats.json",
            {
                "version": 1,
                "generated_at": "2026-01-01T00:00:00+08:00",
                "items": [blog_item],
            },
        )


def read_items(root: Path) -> dict[str, dict]:
    data = json.loads((root / "data" / "output_stats.json").read_text("utf-8"))
    return {item["id"]: item for item in data["items"]}


def test_refresh_builds_zhihu_and_preserves_blog(tmp_path):
    make_archive(
        tmp_path,
        blog_item={
            "source": "blog",
            "id": "posts/a",
            "url": "https://example.com/posts/a/",
            "date": "2026-01-01",
        },
    )

    counts = refresh_output_stats.refresh(tmp_path)
    items = read_items(tmp_path)

    assert counts["zhihu"] == 2
    assert items["posts/a"]["source"] == "blog"
    assert {key for key, item in items.items() if item["source"] == "zhihu"} == {
        "z1",
        "z2",
    }
    assert items["z1"]["duplicate"] is True
    assert items["z1"]["site_likes"] == 4


def test_duplicate_requires_blog_item(tmp_path):
    make_archive(tmp_path)

    refresh_output_stats.refresh(tmp_path)
    items = read_items(tmp_path)

    assert items["z1"]["duplicate"] is False


def test_missing_lastmod_uses_created(tmp_path):
    make_archive(
        tmp_path,
        blog_item={
            "source": "blog",
            "id": "posts/a",
            "url": "https://example.com/posts/a/",
            "date": "2026-01-01",
        },
    )

    refresh_output_stats.refresh(tmp_path)
    items = read_items(tmp_path)

    assert items["z1"]["lastmod"] == "2026-01-05"
    assert items["z2"]["lastmod"] == items["z2"]["date"]


def test_check_detects_stale(tmp_path):
    make_archive(tmp_path)
    refresh_output_stats.refresh(tmp_path)

    assert refresh_output_stats.check(tmp_path) == []

    stats_path = tmp_path / "data" / "zhihu_stats.json"
    stats = json.loads(stats_path.read_text("utf-8"))
    stats["items"]["answers:z1"]["word_count"] = 999
    write_json(stats_path, stats)

    assert refresh_output_stats.check(tmp_path)


def test_missing_output_file_creates_empty_blog_side(tmp_path):
    make_archive(tmp_path)

    counts = refresh_output_stats.refresh(tmp_path)
    items = read_items(tmp_path)

    assert counts["zhihu"] == 2
    assert all(item["source"] == "zhihu" for item in items.values())

import json

from zhihu_archive.crossposts import (
    apply_crossposts,
    load_crossposts,
    set_crosspost,
    zhihu_id,
)

PAGE = """---
title: "测试"
date: 2026-01-01
type: articles
zhihu_id: "123"
---

正文
"""


def test_set_crosspost_inserts_canonical_after_zhihu_id():
    result = set_crosspost(PAGE, "https://example.com/post/")
    assert 'canonicalURL: "https://example.com/post/"' in result
    assert "ShowCanonicalLink: true" in result
    assert result.index("zhihu_id:") < result.index("canonicalURL:")
    assert zhihu_id(result) == "123"
    assert result.endswith("正文\n")


def test_set_crosspost_is_idempotent():
    once = set_crosspost(PAGE, "https://example.com/post/")
    assert set_crosspost(once, "https://example.com/post/") == once


def test_apply_crossposts_updates_only_matching_pages(tmp_path):
    matched = tmp_path / "articles" / "123"
    matched.mkdir(parents=True)
    (matched / "index.md").write_text(PAGE, encoding="utf-8")
    other = tmp_path / "articles" / "999"
    other.mkdir(parents=True)
    (other / "index.md").write_text(PAGE.replace('"123"', '"999"'), encoding="utf-8")

    mapping = {"123": {"url": "https://example.com/post/", "title": "测试"}}
    assert apply_crossposts(tmp_path, mapping) == 1
    assert "canonicalURL" in (matched / "index.md").read_text(encoding="utf-8")
    assert "canonicalURL" not in (other / "index.md").read_text(encoding="utf-8")
    assert apply_crossposts(tmp_path, mapping) == 0


def test_load_crossposts_missing_file_returns_empty(tmp_path):
    assert load_crossposts(tmp_path / "missing.json") == {}


def test_load_crossposts_skips_entries_without_url(tmp_path):
    path = tmp_path / "crossposts.json"
    path.write_text(
        json.dumps(
            {"1": {"url": "https://example.com/"}, "2": {"title": "没有链接"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert load_crossposts(path) == {
        "1": {"url": "https://example.com/", "title": "", "blog_title": ""}
    }

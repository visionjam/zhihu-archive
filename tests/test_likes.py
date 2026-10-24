import json

import fetch_likes


def test_extract_likes_reads_thumbs_up_only():
    nodes = [
        {
            "title": "/zhihu-archive/answers/1/",
            "url": "https://github.com/o/r/discussions/1",
            "reactionGroups": [
                {"content": "THUMBS_UP", "users": {"totalCount": 3}},
                {"content": "HEART", "users": {"totalCount": 9}},
            ],
        }
    ]
    assert fetch_likes.extract_likes(nodes) == {
        "/zhihu-archive/answers/1/": {
            "likes": 3,
            "url": "https://github.com/o/r/discussions/1",
        }
    }


def test_discussion_key_extracts_trailing_path():
    assert (
        fetch_likes.discussion_key("/zhihu-archive/answers/1/")
        == "/zhihu-archive/answers/1/"
    )
    assert (
        fetch_likes.discussion_key("Comments for /zhihu-archive/answers/1/")
        == "/zhihu-archive/answers/1/"
    )
    assert (
        fetch_likes.discussion_key("https://example.com/zhihu-archive/answers/1/")
        == "/zhihu-archive/answers/1/"
    )


def test_collect_paginates():
    pages = [
        {
            "data": {
                "repository": {
                    "discussions": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                        "nodes": [{"title": "/a/", "reactionGroups": []}],
                    }
                }
            }
        },
        {
            "data": {
                "repository": {
                    "discussions": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [{"title": "/b/", "reactionGroups": []}],
                    }
                }
            }
        },
    ]
    calls = []

    def opener(query, variables, token):
        calls.append(variables)
        return pages[len(calls) - 1]

    items = fetch_likes.collect("o", "r", "t", opener=opener)
    assert set(items) == {"/a/", "/b/"}
    assert len(calls) == 2
    assert calls[0]["cursor"] is None
    assert calls[1]["cursor"] == "c1"


def test_main_without_token_keeps_existing_file(tmp_path):
    path = tmp_path / "likes.json"
    path.write_text('{"items": {"x": {"likes": 1}}}', encoding="utf-8")
    assert fetch_likes.main(["--output", str(path)], env={}) == 0
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "items": {"x": {"likes": 1}}
    }


def test_main_api_failure_keeps_existing_file(tmp_path, monkeypatch):
    path = tmp_path / "likes.json"
    path.write_text('{"items": {"x": {"likes": 1}}}', encoding="utf-8")

    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(fetch_likes, "collect", fail)
    code = fetch_likes.main(
        ["--output", str(path), "--owner", "o", "--repo", "r"],
        env={"GITHUB_TOKEN": "t"},
    )
    assert code == 0
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "items": {"x": {"likes": 1}}
    }


def test_main_writes_items(tmp_path, monkeypatch):
    path = tmp_path / "likes.json"
    monkeypatch.setattr(
        fetch_likes,
        "collect",
        lambda *args, **kwargs: {"/zhihu-archive/answers/1/": {"likes": 2, "url": "u"}},
    )
    code = fetch_likes.main(
        ["--output", str(path), "--owner", "o", "--repo", "r"],
        env={"GITHUB_TOKEN": "t"},
    )
    assert code == 0
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["items"]["/zhihu-archive/answers/1/"]["likes"] == 2

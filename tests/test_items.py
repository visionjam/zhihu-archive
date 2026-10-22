import json
from pathlib import Path

import pytest

from zhihu_archive.client import ZhihuClient
from zhihu_archive.models import item_from_answer, item_from_article, item_from_pin

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status, data=None):
        self.status_code = status
        self._data = data or {}
        self.text = str(self._data)

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []
        self.params = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        self.params.append(params or {})
        return self.responses.pop(0)


def test_answer_maps_url_and_question():
    item = item_from_answer(load("answers_page1.json")["data"][0])
    assert item.kind == "answers"
    assert item.id == "456"
    assert item.title == "问题标题一"
    assert item.question == "问题标题一"
    assert item.url == "https://www.zhihu.com/question/123/answer/456"
    assert item.tags == ["数学", "物理"]


def test_article_maps_url_and_tags():
    item = item_from_article(load("article.json"))
    assert item.kind == "articles"
    assert item.id == "111"
    assert item.title == "文章标题"
    assert item.url == "https://zhuanlan.zhihu.com/p/111"
    assert item.tags == ["随笔"]


def test_pin_repost_keeps_own_text_and_quote():
    item = item_from_pin(load("pin_repost.json"))
    assert item.kind == "pins"
    assert "我的转发评论" in item.content_html
    assert "被转发的原文" in item.content_html
    assert item.url == "https://www.zhihu.com/pin/789"


def test_pin_without_origin_still_maps():
    raw = {
        "id": 790,
        "type": "pin",
        "created_time": 1560000000,
        "content": [{"type": "text", "content": "原创想法"}],
    }
    item = item_from_pin(raw)
    assert item.title
    assert "原创想法" in item.content_html


def test_iter_items_paginates_and_maps():
    session = FakeSession(
        [
            FakeResponse(200, load("answers_page1.json")),
            FakeResponse(200, load("answers_page2.json")),
        ]
    )
    client = ZhihuClient("z_c0=x", session=session, delay=(0, 0))
    items = list(client.iter_items("answers", "token"))
    assert [item.id for item in items] == ["456", "457", "458"]
    assert [params["offset"] for params in session.params] == [0, 20]


def test_get_detail_maps_answer():
    session = FakeSession([FakeResponse(200, load("answers_page1.json")["data"][0])])
    client = ZhihuClient("z_c0=x", session=session, delay=(0, 0))
    item = client.get_detail("answers", "456")
    assert item.title == "问题标题一"


def test_get_detail_404_returns_none():
    session = FakeSession([FakeResponse(404)])
    client = ZhihuClient("z_c0=x", session=session, delay=(0, 0), retries=1)
    assert client.get_detail("answers", "999") is None

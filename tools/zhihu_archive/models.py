"""知乎接口数据到统一内容模型的映射。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ContentItem:
    kind: str
    id: str
    title: str
    question: str | None
    url: str
    created: datetime
    updated: datetime
    content_html: str
    voteup_count: int
    comment_count: int
    tags: list[str]


def _datetime(timestamp: int | float | None) -> datetime:
    return datetime.fromtimestamp(int(timestamp or 0), tz=timezone.utc)


def _tags(raw: dict) -> list[str]:
    return [topic["name"] for topic in raw.get("topics") or [] if topic.get("name")]


def _plain_text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).replace("&nbsp;", " ").strip()


def _pin_blocks(blocks: list[dict] | None) -> str:
    parts: list[str] = []
    for block in blocks or []:
        block_type = block.get("type")
        if block_type == "text":
            parts.append(f"<p>{block.get('content', '')}</p>")
        elif block_type == "image":
            source = block.get("src") or block.get("url")
            if source:
                parts.append(f'<p><img src="{source}"></p>')
        elif block_type == "link":
            url = block.get("url") or block.get("src")
            if url:
                title = block.get("title") or url
                parts.append(f'<p><a href="{url}">{title}</a></p>')
        elif block.get("content"):
            parts.append(f"<p>{block['content']}</p>")
    return "".join(parts)


def item_from_answer(raw: dict) -> ContentItem:
    question = raw.get("question") or {}
    question_title = question.get("title") or ""
    created = _datetime(raw.get("created_time"))
    fallback = f"回答 · {created:%Y-%m-%d}"
    return ContentItem(
        kind="answers",
        id=str(raw["id"]),
        title=question_title or fallback,
        question=question_title or None,
        url=f"https://www.zhihu.com/question/{question.get('id')}/answer/{raw['id']}",
        created=created,
        updated=_datetime(raw.get("updated_time") or raw.get("created_time")),
        content_html=raw.get("content") or "",
        voteup_count=int(raw.get("voteup_count") or 0),
        comment_count=int(raw.get("comment_count") or 0),
        tags=_tags(raw),
    )


def item_from_article(raw: dict) -> ContentItem:
    created = _datetime(raw.get("created_time"))
    title = raw.get("title") or f"文章 · {created:%Y-%m-%d}"
    return ContentItem(
        kind="articles",
        id=str(raw["id"]),
        title=title,
        question=None,
        url=f"https://zhuanlan.zhihu.com/p/{raw['id']}",
        created=created,
        updated=_datetime(raw.get("updated_time") or raw.get("created_time")),
        content_html=raw.get("content") or "",
        voteup_count=int(raw.get("voteup_count") or 0),
        comment_count=int(raw.get("comment_count") or 0),
        tags=_tags(raw),
    )


def item_from_pin(raw: dict) -> ContentItem:
    created = _datetime(raw.get("created_time"))
    html = _pin_blocks(raw.get("content"))
    origin = raw.get("origin_pin")
    if origin:
        html += "<blockquote><p>转发自知乎</p>" + _pin_blocks(origin.get("content")) + "</blockquote>"
    text = _plain_text(html)
    title = text[:40] if text else f"想法 · {created:%Y-%m-%d}"
    return ContentItem(
        kind="pins",
        id=str(raw["id"]),
        title=title,
        question=None,
        url=f"https://www.zhihu.com/pin/{raw['id']}",
        created=created,
        updated=_datetime(raw.get("updated_time") or raw.get("created_time")),
        content_html=html,
        voteup_count=int(raw.get("voteup_count") or 0),
        comment_count=int(raw.get("comment_count") or 0),
        tags=_tags(raw),
    )


def item_from_raw(kind: str, raw: dict) -> ContentItem:
    if kind == "answers":
        return item_from_answer(raw)
    if kind == "articles":
        return item_from_article(raw)
    if kind == "pins":
        return item_from_pin(raw)
    raise ValueError(f"未知内容类型：{kind}")

"""知乎 HTML 到 Markdown 页面。"""

from __future__ import annotations

import json
from datetime import date
from typing import Mapping
from urllib.parse import unquote, urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify

from .models import ContentItem

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _preprocess(html: str, image_map: Mapping[str, str] | None) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    for image in soup.find_all("img"):
        source = image.get("src") or ""
        if image_map and source in image_map:
            image["src"] = image_map[source]
        elif source.startswith("//"):
            image["src"] = "https:" + source
        if not image.get("alt"):
            image["alt"] = "image"

    for span in soup.find_all("span", class_="ztext-math"):
        tex = span.get("data-tex") or ""
        if tex:
            span.replace_with(NavigableString(f"${tex}$"))
        else:
            span.decompose()

    for link in soup.find_all("a"):
        href = link.get("href") or ""
        if href.startswith("//link.zhihu.com/?target="):
            href = unquote(href.split("target=", 1)[1])
        elif href.startswith("/"):
            href = urljoin("https://www.zhihu.com", href)
        if href:
            link["href"] = href

    for media in soup.find_all(["video", "iframe"]):
        source = media.get("src") or ""
        if source:
            replacement = soup.new_tag("a", href=source)
            replacement.string = "查看视频/嵌入内容"
            media.replace_with(replacement)
        else:
            media.decompose()

    return soup


def html_to_markdown(
    html: str, image_map: Mapping[str, str] | None = None
) -> str:
    soup = _preprocess(html, image_map)
    return markdownify(
        str(soup), heading_style="ATX", strip=["script", "style"]
    ).strip()


def build_front_matter(
    item: ContentItem,
    deleted: bool,
    archived_at: date,
    has_math: bool = False,
) -> str:
    lines = [
        "---",
        f"title: {_string(item.title)}",
        f"date: {item.created.astimezone(SHANGHAI):%Y-%m-%d}",
        f"lastmod: {item.updated.astimezone(SHANGHAI):%Y-%m-%d}",
        f"type: {item.kind}",
        f"zhihu_id: {_string(item.id)}",
        f"zhihu_url: {_string(item.url)}",
    ]
    if item.question:
        lines.append(f"question: {_string(item.question)}")
    lines.extend(
        [
            f"deleted: {'true' if deleted else 'false'}",
            f"archived_at: {archived_at.isoformat()}",
            f"tags: {json.dumps(item.tags, ensure_ascii=False)}",
        ]
    )
    if has_math:
        lines.append("math: true")
    lines.append("---")
    return "\n".join(lines)


def render_page(
    item: ContentItem, body: str, deleted: bool, archived_at: date
) -> str:
    has_math = "$" in body
    front = build_front_matter(item, deleted, archived_at, has_math=has_math)
    parts = [front, ""]
    if deleted:
        parts.extend(["> 该内容已从知乎删除，本页为归档副本。", ""])
    parts.extend(
        [
            body.strip(),
            "",
            "---",
            "",
            f"原文链接：[查看知乎原文]({item.url})",
            "",
        ]
    )
    return "\n".join(parts)

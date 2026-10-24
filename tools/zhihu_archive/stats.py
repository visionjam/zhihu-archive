"""归档统计：赞数、评论数、字数、阅读时长与排行数据。"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Mapping

from .models import item_from_raw

KINDS = ("answers", "articles", "pins")
READING_SPEED = 400  # 中文字符/分钟

_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_FENCE_RE = re.compile(r"^\s*```.*$", re.MULTILINE)
_HTML_RE = re.compile(r"<[^>]*>")
_MD_CHARS_RE = re.compile(r"[#*_~`>]")
_LIST_RE = re.compile(r"^\s*[-+]\s+", re.MULTILINE)


def count_text(markdown: str) -> int:
    """统计正文可见字符数：去掉 Markdown 标记、图片与链接地址，保留文字和标点。"""
    text = _FENCE_RE.sub("", markdown or "")
    text = _IMAGE_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _HTML_RE.sub("", text)
    text = _LIST_RE.sub("", text)
    text = _MD_CHARS_RE.sub("", text)
    text = unescape(text)
    return sum(1 for char in text if not char.isspace())


def reading_minutes(chars: int, speed: int = READING_SPEED) -> int:
    if chars <= 0:
        return 0
    return max(1, math.ceil(chars / speed))


def extract_body(page: str) -> str:
    """从生成的 page bundle 中取出正文，去掉 front matter、删除提示和原文链接尾注。"""
    text = (page or "").replace("\r\n", "\n")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5 :]
    footer = "\n---\n\n原文链接："
    index = text.rfind(footer)
    if index != -1:
        text = text[:index]
    text = text.strip()
    notice = "> 该内容已从知乎删除"
    if text.startswith(notice):
        _, _, rest = text.partition("\n")
        text = rest.strip()
    return text


def parse_front_matter(page: str) -> dict:
    """读取同步生成的简单 YAML front matter；只解析统计需要的标量字段。"""
    text = (page or "").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    fields: dict = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        value = raw.strip()
        if value.startswith('"'):
            try:
                fields[key.strip()] = json.loads(value)
            except json.JSONDecodeError:
                fields[key.strip()] = value.strip('"')
        elif value in ("true", "false"):
            fields[key.strip()] = value == "true"
        else:
            fields[key.strip()] = value
    return fields


def _is_deleted(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def _raw_counts(raw_root: Path | None, kind: str, item_id: str) -> tuple[int, int]:
    if raw_root is None:
        return 0, 0
    path = raw_root / kind / f"{item_id}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        item = item_from_raw(kind, raw)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return 0, 0
    return item.voteup_count, item.comment_count


def build_stats(
    content_root: Path,
    raw_root: Path | None = None,
    *,
    previous: Mapping | None = None,
    fresh: Mapping[str, Mapping] | None = None,
    kinds: tuple[str, ...] = KINDS,
    now: datetime | None = None,
) -> dict:
    """扫描 page bundle，生成排行与全站统计。

    计数优先级：本轮列表接口的新数据 > 上次统计文件 > 本地缓存的详情 JSON。
    """
    content_root = Path(content_root)
    raw_root = Path(raw_root) if raw_root is not None else None
    previous_items = (previous or {}).get("items") or {}
    fresh = fresh or {}
    entries: dict[str, dict] = {}

    for kind in kinds:
        kind_dir = content_root / kind
        if not kind_dir.is_dir():
            continue
        for page_path in sorted(kind_dir.glob("*/index.md")):
            page_text = page_path.read_text(encoding="utf-8", errors="replace")
            fields = parse_front_matter(page_text)
            item_id = str(fields.get("zhihu_id") or page_path.parent.name)
            key = f"{kind}:{item_id}"
            body = extract_body(page_text)
            words = count_text(body)

            if key in fresh:
                votes = int(fresh[key].get("voteup_count") or 0)
                comments = int(fresh[key].get("comment_count") or 0)
            elif key in previous_items:
                votes = int(previous_items[key].get("voteup_count") or 0)
                comments = int(previous_items[key].get("comment_count") or 0)
            else:
                votes, comments = _raw_counts(raw_root, kind, item_id)

            entries[key] = {
                "kind": kind,
                "id": item_id,
                "title": str(fields.get("title") or ""),
                "url": str(fields.get("zhihu_url") or ""),
                "rel_path": f"/{kind}/{item_id}/",
                "created": str(fields.get("date") or ""),
                "deleted": _is_deleted(fields.get("deleted")),
                "voteup_count": votes,
                "comment_count": comments,
                "word_count": words,
                "reading_minutes": reading_minutes(words),
            }

    by_kind = {kind: 0 for kind in KINDS}
    for entry in entries.values():
        by_kind[entry["kind"]] = by_kind.get(entry["kind"], 0) + 1
    totals = {
        "items": len(entries),
        "words": sum(entry["word_count"] for entry in entries.values()),
        "votes": sum(entry["voteup_count"] for entry in entries.values()),
        "comments": sum(entry["comment_count"] for entry in entries.values()),
        "by_kind": by_kind,
    }
    generated = now or datetime.now(timezone.utc)
    return {
        "generated_at": generated.isoformat(timespec="seconds"),
        "totals": totals,
        "items": entries,
    }


def load_stats(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_stats(path: Path, data: dict) -> None:
    """写统计文件；只有时间戳变化时保留旧时间戳，避免每次同步产生无意义 diff。"""
    path = Path(path)
    existing = load_stats(path)
    if existing.get("generated_at"):
        new_body = {key: value for key, value in data.items() if key != "generated_at"}
        old_body = {
            key: value for key, value in existing.items() if key != "generated_at"
        }
        if new_body == old_body:
            data = {**data, "generated_at": existing["generated_at"]}

    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == text:
                return
        except OSError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

"""把归档文章与博客站上的同一篇内容关联起来。"""

from __future__ import annotations

import json
import re
from pathlib import Path

_FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n?", re.S)
_ZHIHU_ID = re.compile(r'^zhihu_id:\s*"?([^"\n]+)"?\s*$', re.M)


def load_crossposts(path: Path) -> dict[str, dict[str, str]]:
    """读取 zhihu_id -> {url, title} 的映射；文件不存在时返回空表。"""
    path = Path(path)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} 必须是 JSON 对象")
    result: dict[str, dict[str, str]] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        url = str(value.get("url") or "").strip()
        if not url:
            continue
        result[str(key)] = {
            "url": url,
            "title": str(value.get("title") or "").strip(),
        }
    return result


def _split_front_matter(text: str) -> tuple[str | None, str | None]:
    match = _FRONT_MATTER.match(text)
    if not match:
        return None, None
    return match.group(1), text[match.end():]


def zhihu_id(text: str) -> str:
    """从页面 frontmatter 里取 zhihu_id。"""
    front, _ = _split_front_matter(text)
    if not front:
        return ""
    match = _ZHIHU_ID.search(front)
    return match.group(1).strip() if match else ""


def set_crosspost(text: str, url: str) -> str:
    """在 frontmatter 中写入 canonicalURL 与 ShowCanonicalLink。"""
    front, body = _split_front_matter(text)
    if front is None:
        return text
    canonical = f"canonicalURL: {json.dumps(url, ensure_ascii=False)}"
    show = "ShowCanonicalLink: true"
    lines = [
        line
        for line in front.splitlines()
        if not line.startswith("canonicalURL:")
        and not line.startswith("ShowCanonicalLink:")
    ]
    insert_at = len(lines)
    for index, line in enumerate(lines):
        if line.startswith("zhihu_id:"):
            insert_at = index + 1
            break
    lines[insert_at:insert_at] = [canonical, show]
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def apply_crossposts(content_root: Path, mapping: dict[str, dict[str, str]]) -> int:
    """给已有页面补写交叉发布字段，返回修改页数。"""
    content_root = Path(content_root)
    changed = 0
    for kind in ("answers", "articles", "pins"):
        for path in (content_root / kind).glob("*/index.md"):
            text = path.read_text(encoding="utf-8")
            entry = mapping.get(zhihu_id(text))
            if not entry:
                continue
            new_text = set_crosspost(text, entry["url"])
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                changed += 1
    return changed

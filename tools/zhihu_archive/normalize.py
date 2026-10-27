"""同步后的内容整理：交叉发布、公式标记、相邻重复图片。"""

from __future__ import annotations

import re
from pathlib import Path

from .crossposts import set_crosspost, zhihu_id
from .render import dedupe_adjacent_images, has_math_markup

_FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n?", re.S)
_MATH_LINE = re.compile(r"^math:\s*true\s*$", re.M)


def _split_front_matter(text: str) -> tuple[str | None, str | None]:
    match = _FRONT_MATTER.match(text)
    if not match:
        return None, None
    return match.group(1), text[match.end():]


def set_math_flag(text: str) -> str:
    """按正文实际公式增删 math: true，避免代码里的 $ 误触发 KaTeX。"""
    front, body = _split_front_matter(text)
    if front is None:
        return text
    should_have = has_math_markup(body or "")
    has_flag = _MATH_LINE.search(front) is not None
    if should_have == has_flag:
        return text
    lines = front.splitlines()
    if should_have:
        lines.append("math: true")
    else:
        lines = [line for line in lines if not _MATH_LINE.match(line)]
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def normalize_page(text: str, crosspost_url: str | None = None) -> str:
    """对单页做幂等整理。"""
    result = text
    if crosspost_url:
        result = set_crosspost(result, crosspost_url)
    result = set_math_flag(result)
    return dedupe_adjacent_images(result)


def normalize_content(
    content_root: Path, crossposts: dict[str, dict[str, str]] | None = None
) -> int:
    """整理全部页面，返回实际修改的页数。"""
    content_root = Path(content_root)
    mapping = crossposts or {}
    changed = 0
    for kind in ("answers", "articles", "pins"):
        for path in (content_root / kind).glob("*/index.md"):
            text = path.read_text(encoding="utf-8")
            entry = mapping.get(zhihu_id(text))
            new_text = normalize_page(text, entry["url"] if entry else None)
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                changed += 1
    return changed

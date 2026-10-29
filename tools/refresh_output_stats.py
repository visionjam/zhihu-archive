#!/usr/bin/env python3
"""从本地归档数据重建 data/output_stats.json 的知乎侧。"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from zhihu_archive.stats import parse_front_matter

SCHEMA_VERSION = 1
_BASE_URL_RE = re.compile(r'(?m)^baseURL:\s*"([^"]+)"')


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_document(path: Path) -> dict:
    return _load_json(Path(path))


def _base_url(root: Path) -> str:
    try:
        text = (root / "hugo.yml").read_text(encoding="utf-8")
    except OSError:
        return ""
    match = _BASE_URL_RE.search(text)
    return match.group(1).rstrip("/") if match else ""


def _site_likes(root: Path) -> dict:
    items = _load_json(root / "data" / "likes.json").get("items") or {}
    return items if isinstance(items, dict) else {}


def _like_count(likes: dict, rel_path: str) -> int:
    entry = likes.get(rel_path)
    if not isinstance(entry, dict):
        return 0
    try:
        return int(entry.get("likes") or 0)
    except (TypeError, ValueError):
        return 0


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _lastmod(root: Path, kind: str, item_id: str, date: str) -> str:
    path = root / "content" / kind / item_id / "index.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return date
    value = parse_front_matter(text).get("lastmod")
    return str(value) if value else date


def _sort_items(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda item: (
            str(item.get("source", "")),
            str(item.get("date", "")),
            str(item.get("id", "")),
        ),
    )


def _blog_urls(items: list[dict]) -> set[str]:
    return {
        str(item.get("url") or "").rstrip("/")
        for item in items
        if item.get("source") == "blog" and item.get("url")
    }


def build_zhihu_items(root: Path, blog_urls: set[str]) -> list[dict]:
    root = Path(root).resolve()
    raw_items = _load_json(root / "data" / "zhihu_stats.json").get("items") or {}
    if isinstance(raw_items, dict):
        entries = list(raw_items.values())
    elif isinstance(raw_items, list):
        entries = raw_items
    else:
        entries = []
    base_url = _base_url(root)
    likes = _site_likes(root)
    crossposts = _load_json(root / "data" / "crossposts.json")
    normalized_blog_urls = {url.rstrip("/") for url in blog_urls}
    items: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind") or "")
        item_id = str(entry.get("id") or "")
        rel_path = str(entry.get("rel_path") or f"/{kind}/{item_id}/")
        date = str(entry.get("created") or "")
        mapping = crossposts.get(item_id)
        mapped_url = (
            str(mapping.get("url") or "").rstrip("/")
            if isinstance(mapping, dict)
            else ""
        )
        words = _int(entry.get("word_count"))
        items.append(
            {
                "source": "zhihu",
                "kind": kind,
                "id": item_id,
                "title": str(entry.get("title") or ""),
                "url": (base_url + rel_path) if base_url else rel_path,
                "rel_path": rel_path,
                "date": date,
                "lastmod": _lastmod(root, kind, item_id, date),
                "words": words,
                "minutes": _int(entry.get("reading_minutes")),
                "votes": _int(entry.get("voteup_count")),
                "comments": _int(entry.get("comment_count")),
                "site_likes": _like_count(likes, rel_path),
                "duplicate": bool(
                    mapped_url and mapped_url in normalized_blog_urls
                ),
            }
        )
    return _sort_items(items)


def _write_document(path: Path, items: list[dict], now: str | None = None) -> bool:
    path = Path(path)
    old = load_document(path)
    if old.get("items") == items and old.get("generated_at"):
        return False
    stamp = now or datetime.now().astimezone().isoformat(timespec="seconds")
    document = {"version": SCHEMA_VERSION, "generated_at": stamp, "items": items}
    text = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def refresh(root: Path, now: str | None = None) -> dict[str, int]:
    root = Path(root).resolve()
    path = root / "data" / "output_stats.json"
    existing = load_document(path).get("items") or []
    if not isinstance(existing, list):
        existing = []
    blog = [
        item
        for item in existing
        if isinstance(item, dict) and item.get("source") == "blog"
    ]
    zhihu = build_zhihu_items(root, _blog_urls(blog))
    _write_document(path, _sort_items(blog + zhihu), now)
    return {"zhihu": len(zhihu)}


def check(root: Path) -> list[str]:
    root = Path(root).resolve()
    path = root / "data" / "output_stats.json"
    if not path.is_file():
        return ["缺少 data/output_stats.json（运行 python tools/refresh_output_stats.py --write）"]
    document = load_document(path)
    issues: list[str] = []
    if document.get("version") != SCHEMA_VERSION:
        issues.append(f"快照 version 不是 {SCHEMA_VERSION}")
    items = document.get("items")
    if not isinstance(items, list):
        return issues + ["快照缺少 items 列表"]
    existing_zhihu = {
        item.get("id"): item
        for item in items
        if isinstance(item, dict) and item.get("source") == "zhihu"
    }
    blog = [
        item
        for item in items
        if isinstance(item, dict) and item.get("source") == "blog"
    ]
    actual = build_zhihu_items(root, _blog_urls(blog))
    if set(existing_zhihu) != {item["id"] for item in actual}:
        issues.append(
            "快照的知乎条目与本地数据不一致（运行 python tools/refresh_output_stats.py --write）"
        )
        return issues
    fields = (
        "source",
        "kind",
        "id",
        "title",
        "url",
        "rel_path",
        "date",
        "lastmod",
        "words",
        "minutes",
        "votes",
        "comments",
        "site_likes",
        "duplicate",
    )
    for item in actual:
        old = existing_zhihu.get(item["id"])
        differing = [
            field for field in fields if old is None or old.get(field) != item.get(field)
        ]
        if differing:
            issues.append(
                f"快照的知乎条目 {item['id']} 与本地数据不一致："
                + ", ".join(differing)
            )
    return issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="重建跨站统计快照的知乎侧。")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="归档仓库根目录（默认：本脚本所在仓库）",
    )
    parser.add_argument("--write", action="store_true", help="写回 data/output_stats.json")
    parser.add_argument("--check", action="store_true", help="只校验（默认）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.write:
        counts = refresh(root)
        print(f"知乎 {counts['zhihu']} 条 -> {root / 'data' / 'output_stats.json'}")
        return 0
    issues = check(root)
    for issue in issues:
        print(f"问题：{issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""从 GitHub Discussions 读取 giscus 主帖的 👍 数，写入 data/likes.json。"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib import request
from urllib.parse import urlparse

GRAPHQL_URL = "https://api.github.com/graphql"
THUMBS_UP = "THUMBS_UP"
QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    discussions(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        title
        url
        reactionGroups { content users { totalCount } }
      }
    }
  }
}
"""

PATH_RE = re.compile(r"(/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+/?)\s*$")


def discussion_key(title: str) -> str:
    """giscus 的 pathname 映射会把页面路径写进讨论标题；取出末尾路径。"""
    title = (title or "").strip()
    for token in title.split():
        if "://" in token:
            path = urlparse(token).path
            if path:
                return path
    match = PATH_RE.search(title)
    return match.group(1) if match else title


def extract_likes(nodes) -> dict:
    items: dict[str, dict] = {}
    for node in nodes or []:
        key = discussion_key(node.get("title", ""))
        if not key:
            continue
        likes = 0
        for group in node.get("reactionGroups") or []:
            if group.get("content") == THUMBS_UP:
                likes = int((group.get("users") or {}).get("totalCount") or 0)
        items[key] = {"likes": likes, "url": node.get("url", "")}
    return items


def _post(query: str, variables: dict, token: str) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "visionjam-likes",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        return json.load(response)


def collect(owner: str, repo: str, token: str, opener=None) -> dict:
    opener = opener or _post
    items: dict[str, dict] = {}
    cursor = None
    while True:
        data = opener(QUERY, {"owner": owner, "name": repo, "cursor": cursor}, token)
        if data.get("errors"):
            messages = "; ".join(str(e.get("message")) for e in data["errors"])
            raise RuntimeError(messages)
        repository = (data.get("data") or {}).get("repository") or {}
        discussions = repository.get("discussions") or {}
        items.update(extract_likes(discussions.get("nodes") or []))
        page = discussions.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
        if not cursor:
            break
    return items


def main(argv: list[str] | None = None, env: dict | None = None) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="读取 GitHub Discussions 的站内点赞数。")
    parser.add_argument("--output", default="data/likes.json")
    parser.add_argument("--owner")
    parser.add_argument("--repo")
    args = parser.parse_args(argv)

    repository = env.get("GITHUB_REPOSITORY") or "/"
    default_owner, _, default_repo = repository.partition("/")
    owner = args.owner or default_owner
    repo = args.repo or default_repo
    token = env.get("GITHUB_TOKEN") or env.get("GH_TOKEN")

    if not token:
        print("未设置 GITHUB_TOKEN，保留现有 likes.json。")
        return 0
    if not owner or not repo:
        print("无法确定仓库，保留现有 likes.json。")
        return 0

    try:
        items = collect(owner, repo, token)
    except Exception as exc:  # 取赞失败不应阻断站点构建
        print(f"取赞失败，保留现有 likes.json：{exc}")
        return 0

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": items,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"站内赞已更新：{len(items)} 条 -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

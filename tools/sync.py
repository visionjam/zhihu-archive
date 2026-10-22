#!/usr/bin/env python3
"""知乎归档同步入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zhihu_archive.client import AuthError, RateLimitError, ZhihuClient
from zhihu_archive.cookie import CookieFormatError, load_cookie
from zhihu_archive.state import SyncState
from zhihu_archive.sync import KINDS, run_sync

ROOT = Path(__file__).resolve().parents[1]


def parse_types(value: str) -> tuple[str, ...]:
    kinds = tuple(part.strip() for part in value.split(",") if part.strip())
    unknown = [kind for kind in kinds if kind not in KINDS]
    if not kinds or unknown:
        raise ValueError(f"未知内容类型：{', '.join(unknown) or value}")
    return kinds


def load_config() -> dict:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    config["content_root"] = str((ROOT / config["content_root"]).resolve())
    config["state_dir"] = str((ROOT / config["state_dir"]).resolve())
    return config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="同步知乎回答、想法与文章到本地归档。")
    parser.add_argument("--check", action="store_true", help="只验证 Cookie 与登录态")
    parser.add_argument("--sample", type=int, default=0, help="每种类型只打印 N 条标题")
    parser.add_argument("--dry-run", action="store_true", help="只计算，不写文件")
    parser.add_argument("--no-push", action="store_true", help="写文件但不提交推送")
    parser.add_argument(
        "--types",
        default="answers,articles,pins",
        help="逗号分隔：answers,articles,pins",
    )
    parser.add_argument("--limit", type=int, default=None, help="每种类型最多处理 N 条")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        kinds = parse_types(args.types)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.check:
        try:
            me = ZhihuClient(load_cookie()).check_auth()
        except (CookieFormatError, AuthError, RateLimitError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"OK: {me['name']} (url_token={me['url_token']})")
        return 0

    config = load_config()
    cookie_file = Path(config["cookie_file"]) if config.get("cookie_file") else None
    try:
        client = ZhihuClient(load_cookie(cookie_file))
        me = client.check_auth()
    except (CookieFormatError, AuthError, RateLimitError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.sample:
        for kind in kinds:
            shown = 0
            for item in client.iter_items(kind, me["url_token"]):
                print(f"{kind}: {item.title}")
                shown += 1
                if shown >= args.sample:
                    break
        return 0

    state_dir = Path(config["state_dir"])
    state = SyncState.load(state_dir / "state.json")
    state.url_token = me["url_token"]
    try:
        report = run_sync(
            client,
            state,
            config,
            kinds=kinds,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    except AuthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except RateLimitError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    if not args.dry_run:
        state.save(state_dir / "state.json")
    print(
        f"完成：新增 {report.added} / 更新 {report.updated} / "
        f"删除标记 {report.marked_deleted} / 失败 {report.failed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

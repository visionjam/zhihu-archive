#!/usr/bin/env python3
"""知乎归档同步入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zhihu_archive.client import AuthError, RateLimitError, ZhihuClient
from zhihu_archive.cookie import CookieFormatError, load_cookie


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="同步知乎回答、想法与文章到本地归档。")
    parser.add_argument("--check", action="store_true", help="只验证 Cookie 与登录态")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check:
        try:
            client = ZhihuClient(load_cookie())
            me = client.check_auth()
        except (CookieFormatError, AuthError, RateLimitError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"OK: {me['name']} (url_token={me['url_token']})")
        return 0
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""推送前扫描归档内容中的隐私与凭证风险。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zhihu_archive.privacy import load_allowlist, scan_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="扫描归档内容中的隐私与凭证风险。")
    parser.add_argument("paths", nargs="*", default=["content"], help="要扫描的文件或目录")
    parser.add_argument("--root", default=".", help="仓库根目录")
    parser.add_argument(
        "--allowlist",
        default=".local/scan-allowlist.txt",
        help="需确认项的放行名单（仅本机）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    allowlist = load_allowlist(root / args.allowlist)
    report = scan_paths(root, args.paths, allowlist)

    for finding in report.hard:
        print(f"HARD  {finding.path}:{finding.line} [{finding.kind}] <hidden>")
    for finding in report.review:
        print(f"REVIEW {finding.path}:{finding.line} [{finding.kind}] {finding.text[:80]}")
    for image in report.images:
        print(f"IMAGE {image}")

    if report.hard:
        print(f"\n失败：{len(report.hard)} 个硬拦截项。", file=sys.stderr)
        return 1
    if report.review:
        print(
            f"\n失败：{len(report.review)} 个需确认项；确认后可写入 {args.allowlist}。",
            file=sys.stderr,
        )
        return 1
    print(f"\n通过：扫描 {len(report.images)} 张图片，无硬拦截或未确认项。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

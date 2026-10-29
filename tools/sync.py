#!/usr/bin/env python3
"""知乎归档同步入口。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import refresh_output_stats

from zhihu_archive.client import AuthError, RateLimitError, ZhihuClient
from zhihu_archive.cookie import CookieFormatError, load_cookie
from zhihu_archive.crossposts import load_crossposts
from zhihu_archive.normalize import normalize_content
from zhihu_archive.privacy import IMAGE_EXTS, load_allowlist, scan_paths
from zhihu_archive.state import SyncState
from zhihu_archive.stats import build_stats, load_stats, write_stats
from zhihu_archive.sync import KINDS, SyncReport, run_sync

ROOT = Path(__file__).resolve().parents[1]


def find_blog_root(
    root: Path = ROOT,
    env: dict | None = None,
    config: dict | None = None,
) -> Path | None:
    env = os.environ if env is None else env
    value = env.get("BLOG_ROOT")
    if value:
        candidate = Path(value)
    elif config and config.get("blog_root"):
        candidate = Path(str(config["blog_root"]))
        if not candidate.is_absolute():
            candidate = Path(root) / candidate
    else:
        candidate = Path(root).parent / "my blog"
    candidate = candidate.resolve()
    tool = candidate / "tools" / "output_stats.py"
    return candidate if tool.is_file() else None


def refresh_stats_snapshots(
    root: Path = ROOT, config: dict | None = None
) -> None:
    try:
        counts = refresh_output_stats.refresh(root)
        print(f"统计快照：归档 {counts['zhihu']} 条。")
    except Exception as exc:  # noqa: BLE001 - 统计失败不应阻断同步
        print(f"警告：归档统计快照生成失败：{exc}")
        return
    blog = find_blog_root(root, config=config)
    if blog is None:
        return
    tool = blog / "tools" / "output_stats.py"
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(tool),
                "--side",
                "zhihu",
                "--blog-root",
                str(blog),
                "--archive-root",
                str(root),
            ],
            cwd=str(blog),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"警告：博客仓库统计快照更新失败：{exc}")
        return
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        print(f"警告：博客仓库统计快照更新失败：{detail}")
        return
    print("统计快照：博客仓库副本已更新。")


def run_git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def staged_changes(root: Path) -> bool:
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=str(root), capture_output=True
    )
    return result.returncode != 0


def staged_image_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return []
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if Path(line.strip()).suffix.lower() in IMAGE_EXTS
    ]


def publish_if_clean(
    root: Path,
    content_root: Path,
    state_dir: Path,
    report: SyncReport,
    push: bool,
    images_approved: bool = False,
) -> bool:
    root = Path(root).resolve()
    allowlist = load_allowlist(ROOT / "tools" / "privacy_allowlist.txt") | load_allowlist(
        Path(state_dir) / "scan-allowlist.txt"
    )
    try:
        relative = Path(content_root).resolve().relative_to(root).as_posix()
    except ValueError:
        relative = str(content_root)
    data_root = root / "data"
    scan_paths_to_check = [relative]
    if data_root.exists():
        scan_paths_to_check.append("data")
    scan = scan_paths(root, scan_paths_to_check, allowlist)

    for finding in scan.hard:
        print(f"HARD  {finding.path}:{finding.line} [{finding.kind}] <hidden>")
    for finding in scan.review:
        print(f"REVIEW {finding.path}:{finding.line} [{finding.kind}] {finding.text[:80]}")
    if not scan.ok:
        return False

    if data_root.exists():
        run_git(root, "add", "content", "data")
    else:
        run_git(root, "add", "content")
    images = staged_image_paths(root)
    if images and not images_approved:
        print(f"新增/修改图片 {len(images)} 张，需人工确认：")
        for image in images[:10]:
            print(f"  {image}")
        if len(images) > 10:
            print(f"  ... 其余 {len(images) - 10} 张")
        print("确认后使用 --yes-images 重新运行。")
        return False
    if staged_changes(root):
        message = (
            f"sync: {date.today():%Y-%m-%d} "
            f"(新增 {report.added} / 更新 {report.updated} / 删除标记 {report.marked_deleted})"
        )
        run_git(root, "commit", "-m", message)
    if push:
        run_git(root, "push", "origin", "main")
    return True


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
    if config.get("stats_file"):
        config["stats_file"] = str((ROOT / config["stats_file"]).resolve())
    if config.get("crossposts_file"):
        config["crossposts_file"] = str((ROOT / config["crossposts_file"]).resolve())
    return config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="同步知乎回答、想法与文章到本地归档。")
    parser.add_argument("--check", action="store_true", help="只验证 Cookie 与登录态")
    parser.add_argument(
        "--refresh-stats",
        action="store_true",
        help="不联网，仅根据本地内容与缓存重建统计文件",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="不联网，刷新交叉发布/canonical、math 标记与相邻重复图片",
    )
    parser.add_argument("--sample", type=int, default=0, help="每种类型只打印 N 条标题")
    parser.add_argument("--dry-run", action="store_true", help="只计算，不写文件")
    parser.add_argument("--no-push", action="store_true", help="本地提交但不推送远端")
    parser.add_argument(
        "--yes-images", action="store_true", help="确认新增/修改的图片可以公开"
    )
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

    if args.refresh_stats:
        config = load_config()
        stats_file = config.get("stats_file")
        if not stats_file:
            print("ERROR: config.json 缺少 stats_file。", file=sys.stderr)
            return 2
        stats_path = Path(stats_file)
        data = build_stats(
            Path(config["content_root"]),
            Path(config["state_dir"]) / "raw",
            previous=load_stats(stats_path),
        )
        write_stats(stats_path, data)
        refresh_stats_snapshots(ROOT, config)
        print(f"统计已重建：{data['totals']['items']} 条 -> {stats_path}")
        return 0

    if args.normalize:
        config = load_config()
        crossposts_file = config.get("crossposts_file")
        mapping = (
            load_crossposts(Path(crossposts_file)) if crossposts_file else {}
        )
        changed = normalize_content(Path(config["content_root"]), mapping)
        print(f"内容整理完成：{changed} 个页面")
        return 0

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
        if report.incomplete:
            print(
                "ERROR: 本轮列表抓取不完整，已写入本地但未推送；请稍后重试。",
                file=sys.stderr,
            )
            return 4
        refresh_stats_snapshots(ROOT, config)
        try:
            published = publish_if_clean(
                ROOT,
                Path(config["content_root"]),
                state_dir,
                report,
                push=not args.no_push,
                images_approved=args.yes_images,
            )
        except subprocess.CalledProcessError as exc:
            print(f"ERROR: git 操作失败：{exc}", file=sys.stderr)
            return 1
        if not published:
            print(
                "ERROR: 隐私扫描未通过，内容已写入本地但未提交。",
                file=sys.stderr,
            )
            return 1
    print(
        f"完成：新增 {report.added} / 更新 {report.updated} / "
        f"删除标记 {report.marked_deleted} / 失败 {report.failed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

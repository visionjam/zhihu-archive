#!/usr/bin/env python3
"""彻底撤回一条归档内容（重写历史并 force-push）。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zhihu_archive.purge import (
    KINDS,
    build_filter_branch_command,
    build_filter_repo_command,
    content_path,
    ensure_archive_repo,
)


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(root), check=True, capture_output=True, text=True
    )


def add_exclusion(root: Path, key: str) -> None:
    state_dir = root / ".local"
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "exclude.txt"
    existing = set()
    if path.exists():
        existing = {
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    if key not in existing:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(key + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从归档仓库彻底移除一条内容。")
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--id", required=True, dest="item_id")
    parser.add_argument("--root", default=".", help="归档仓库根目录")
    parser.add_argument("--yes", action="store_true", help="跳过交互确认")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    ensure_archive_repo(root)
    path = content_path(args.kind, args.item_id)
    key = f"{args.kind}:{args.item_id}"

    commit_count = git(root, "rev-list", "--count", "HEAD").stdout.strip()
    print(f"仓库：{root}")
    print(f"将删除：{path}")
    print(f"将重写历史：{commit_count} 个提交")
    print("远端：origin/main（force-with-lease）")
    if not args.yes:
        answer = input(f"确认请输入仓库目录名（{root.name}）：").strip()
        if answer != root.name:
            print("已取消。", file=sys.stderr)
            return 1

    add_exclusion(root, key)
    shutil.rmtree(root / path, ignore_errors=True)

    git(root, "add", "-A", "content")
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=str(root), capture_output=True
    )
    if staged.returncode != 0:
        git(root, "commit", "-m", f"purge: 移除 {key}")

    has_filter_repo = shutil.which("git-filter-repo") is not None
    command = (
        build_filter_repo_command([path])
        if has_filter_repo
        else build_filter_branch_command([path])
    )
    if not has_filter_repo:
        print("提示：未安装 git-filter-repo，改用 git filter-branch（较慢）。")
    subprocess.run(command, cwd=str(root), check=True)
    git(root, "push", "--force-with-lease", "origin", "main")
    print(f"已撤回 {key}，历史已重写并推送。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

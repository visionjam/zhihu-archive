"""从归档仓库中彻底移除指定条目（含 git 历史）。"""

from __future__ import annotations

import re
from pathlib import Path

KINDS = ("answers", "articles", "pins")


def content_path(kind: str, item_id: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"未知内容类型：{kind}")
    if not re.fullmatch(r"\d+", item_id):
        raise ValueError(f"不合法的内容 ID：{item_id}")
    return f"content/{kind}/{item_id}"


def build_force_push_command(old_sha: str) -> list[str]:
    return [
        "git",
        "push",
        f"--force-with-lease=main:{old_sha}",
        "origin",
        "main",
    ]


def ensure_archive_repo(root: Path) -> None:
    root = Path(root)
    config = root / "hugo.yml"
    if not config.exists():
        raise RuntimeError(f"没有找到 hugo.yml，拒绝运行：{root}")
    if "zhihu-archive" not in config.read_text(encoding="utf-8"):
        raise RuntimeError("当前目录不是知乎归档仓库，拒绝改写历史。")


def build_filter_repo_command(paths: list[str]) -> list[str]:
    command = ["git", "filter-repo", "--force", "--invert-paths"]
    for path in paths:
        command.extend(["--path", path])
    return command


def build_filter_branch_command(paths: list[str]) -> list[str]:
    index_filter = "git rm -r --cached --ignore-unmatch " + " ".join(paths)
    return [
        "git",
        "filter-branch",
        "--index-filter",
        index_filter,
        "--prune-empty",
        "--",
        "--all",
    ]

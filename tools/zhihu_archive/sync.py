"""同步编排：列表 → 详情（按需）→ 图片 → Markdown → page bundle。"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .client import AuthError, RateLimitError
from .images import ImageLocalizer
from .models import ContentItem
from .render import html_to_markdown, render_page
from .state import SyncState

KINDS = ("answers", "articles", "pins")
KIND_ALIASES = {"回答": "answers", "文章": "articles", "想法": "pins"}


@dataclass
class SyncReport:
    added: int = 0
    updated: int = 0
    marked_deleted: int = 0
    failed: int = 0
    incomplete: bool = False


def _load_excluded(state_dir: Path) -> set[tuple[str, str]]:
    path = state_dir / "exclude.txt"
    if not path.exists():
        return set()
    excluded: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        kind, item_id = stripped.split(":", 1)
        kind = KIND_ALIASES.get(kind.strip(), kind.strip())
        if kind not in KINDS:
            print(f"警告：忽略未知的排除类型 {kind}", file=sys.stderr)
            continue
        excluded.add((kind, item_id.strip()))
    return excluded


def _log(state_dir: Path, message: str) -> None:
    log_dir = state_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"sync-{date.today():%Y-%m-%d}.log"
    timestamp = datetime.now().strftime("%H:%M:%S")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def _write_item(
    content_root: Path,
    kind: str,
    item: ContentItem,
    client,
    state_dir: Path,
) -> list[str]:
    bundle = content_root / kind / item.id
    localizer = ImageLocalizer(client, bundle)
    localized_html, _, failed = localizer.localize(item.content_html)
    if failed:
        _log(state_dir, f"images failed {kind}:{item.id} count={len(failed)}")
    body = html_to_markdown(localized_html)
    page = render_page(item, body, deleted=False, archived_at=date.today())
    (bundle / "index.md").write_text(page, encoding="utf-8")

    raw_dir = state_dir / "raw" / kind
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{item.id}.json").write_text(
        json.dumps(item.raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return failed


def _mark_deleted(content_root: Path, kind: str, item_id: str) -> bool:
    path = content_root / kind / item_id / "index.md"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if "deleted: true" in text:
        return False
    text = text.replace("deleted: false", "deleted: true", 1)
    if "该内容已从知乎删除" not in text:
        marker = "\n---\n"
        closing = text.find(marker, 3)
        if closing != -1:
            insert_at = closing + len(marker)
            text = (
                text[:insert_at]
                + "\n> 该内容已从知乎删除，本页为归档副本。\n"
                + text[insert_at:]
            )
    path.write_text(text, encoding="utf-8")
    return True


def run_sync(
    client,
    state: SyncState,
    config: dict,
    kinds: tuple[str, ...] = KINDS,
    dry_run: bool = False,
    limit: int | None = None,
) -> SyncReport:
    content_root = Path(config["content_root"])
    state_dir = Path(config["state_dir"])
    if not dry_run:
        state_dir.mkdir(parents=True, exist_ok=True)
    url_token = state.url_token or config.get("url_token") or ""
    excluded = _load_excluded(state_dir)
    report = SyncReport()

    for kind in kinds:
        excluded_ids = {item_id for excluded_kind, item_id in excluded if excluded_kind == kind}
        if not dry_run:
            for item_id in excluded_ids:
                shutil.rmtree(content_root / kind / item_id, ignore_errors=True)

        seen: set[str] = set()
        processed = 0
        complete = limit is None
        try:
            for item in client.iter_items(kind, url_token):
                seen.add(item.id)
                if item.id in excluded_ids:
                    continue
                if limit is not None and processed >= limit:
                    complete = False
                    break
                known = f"{kind}:{item.id}" in state.items
                bundle_exists = (content_root / kind / item.id / "index.md").exists()
                if not state.needs_update(kind, item) and bundle_exists:
                    continue
                if dry_run:
                    report.added += 0 if known else 1
                    report.updated += 1 if known else 0
                    processed += 1
                    continue
                try:
                    needs_detail = getattr(item, "truncated", False) or not item.content_html.strip()
                    detail = client.get_detail(kind, item.id) if needs_detail else item
                    if detail is None:
                        report.failed += 1
                        processed += 1
                        _log(state_dir, f"detail not found {kind}:{item.id}")
                        continue
                    failed_images = _write_item(
                        content_root, kind, detail, client, state_dir
                    )
                    if failed_images:
                        report.failed += 1
                        processed += 1
                        _log(
                            state_dir,
                            f"images pending retry {kind}:{item.id} count={len(failed_images)}",
                        )
                        continue
                    state.record(kind, detail)
                    report.added += 0 if known else 1
                    report.updated += 1 if known else 0
                    processed += 1
                except (AuthError, RateLimitError):
                    raise
                except Exception as exc:
                    report.failed += 1
                    processed += 1
                    _log(state_dir, f"item failed {kind}:{item.id} error={exc}")
        except (AuthError, RateLimitError):
            raise
        except Exception as exc:
            complete = False
            report.incomplete = True
            _log(state_dir, f"list failed {kind} error={exc}")

        if not dry_run:
            deleted = state.apply_scan(kind, seen, complete)
            for item_id in deleted:
                if _mark_deleted(content_root, kind, item_id):
                    report.marked_deleted += 1

    if not dry_run:
        state.touch()
    return report

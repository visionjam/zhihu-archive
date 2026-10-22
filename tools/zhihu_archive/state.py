"""同步状态与删除检测。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def _updated_value(item) -> int:
    value = item.updated
    if isinstance(value, datetime):
        return int(value.timestamp())
    return int(value)


@dataclass
class SyncState:
    items: dict[str, dict] = field(default_factory=dict)
    last_sync: str | None = None
    url_token: str | None = None
    last_complete_scan: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "SyncState":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            items=data.get("items") or {},
            last_sync=data.get("last_sync"),
            url_token=data.get("url_token"),
            last_complete_scan=data.get("last_complete_scan") or {},
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_sync": self.last_sync,
            "url_token": self.url_token,
            "items": self.items,
            "last_complete_scan": self.last_complete_scan,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def touch(self) -> None:
        self.last_sync = datetime.now(timezone.utc).isoformat()

    def needs_update(self, kind: str, item) -> bool:
        key = f"{kind}:{item.id}"
        meta = self.items.get(key)
        if meta is None:
            return True
        return meta.get("updated") != _updated_value(item) or bool(meta.get("deleted"))

    def record(self, kind: str, item) -> None:
        self.items[f"{kind}:{item.id}"] = {
            "updated": _updated_value(item),
            "deleted": False,
        }

    def apply_scan(self, kind: str, seen_ids: set[str], complete: bool) -> set[str]:
        """完整扫描后标记消失的条目；不完整扫描不做任何改动。"""
        if not complete:
            return set()
        prefix = f"{kind}:"
        deleted: set[str] = set()
        for key, meta in self.items.items():
            if not key.startswith(prefix):
                continue
            item_id = key[len(prefix) :]
            if item_id not in seen_ids:
                if not meta.get("deleted"):
                    deleted.add(item_id)
                meta["deleted"] = True
            else:
                meta["deleted"] = False
        self.last_complete_scan[kind] = True
        return deleted

    def deleted_ids(self, kind: str) -> set[str]:
        prefix = f"{kind}:"
        return {
            key[len(prefix) :]
            for key, meta in self.items.items()
            if key.startswith(prefix) and meta.get("deleted")
        }

"""知乎正文图片下载与本地化。"""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

TYPE_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
KNOWN_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def image_name(content: bytes, content_type: str, url: str = "") -> str:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    extension = TYPE_EXT.get(mime)
    if extension is None:
        suffix = Path(urlparse(url).path).suffix.lower()
        extension = suffix if suffix in KNOWN_EXT else ".jpg"
    digest = hashlib.sha256(content).hexdigest()[:16]
    return f"{digest}{extension}"


class ImageLocalizer:
    def __init__(self, client, bundle_dir: Path) -> None:
        self.client = client
        self.bundle_dir = Path(bundle_dir)

    def localize(self, html: str) -> tuple[str, list[str], list[str]]:
        soup = BeautifulSoup(html or "", "html.parser")
        self.bundle_dir.mkdir(parents=True, exist_ok=True)
        saved: list[str] = []
        failed: list[str] = []
        cache: dict[str, str] = {}

        for image in soup.find_all("img"):
            source = image.get("src") or ""
            if not source:
                continue
            if source.startswith("//"):
                source = "https:" + source
                image["src"] = source
            if source in cache:
                image["src"] = cache[source]
                continue
            try:
                content, content_type = self.client.download(source)
            except (OSError, ValueError):
                failed.append(source)
                continue
            name = image_name(content, content_type, source)
            (self.bundle_dir / name).write_bytes(content)
            relative = f"./{name}"
            cache[source] = relative
            image["src"] = relative
            if name not in saved:
                saved.append(name)

        return str(soup), saved, failed

"""知乎网页接口的最小 HTTP 客户端。"""

from __future__ import annotations

import random
import time
from collections.abc import Iterator

import requests

from .models import ContentItem, item_from_raw

BASE = "https://www.zhihu.com"

DETAIL_KIND = {"answers": "answer", "articles": "article", "pins": "pin"}
INCLUDE_FIELDS = {
    "answers": (
        "data[*].content,excerpt,created_time,updated_time,voteup_count,"
        "comment_count,question.title,question.id,topics.name"
    ),
    "articles": (
        "data[*].content,excerpt,created_time,updated_time,voteup_count,"
        "comment_count,topics.name"
    ),
    "pins": (
        "data[*].content,created_time,updated_time,voteup_count,"
        "comment_count,topics.name,origin_pin"
    ),
}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


class ZhihuError(RuntimeError):
    """所有知乎请求错误的基类。"""


class AuthError(ZhihuError):
    """Cookie 缺失、过期或登录态无效（401）。"""


class RateLimitError(ZhihuError):
    """触发知乎风控或权限限制（403）。"""


class NotFoundError(ZhihuError):
    """内容不存在或已删除（404）。"""


class ApiError(ZhihuError):
    """其他接口错误。"""


class ZhihuClient:
    def __init__(
        self,
        cookie: str,
        delay: tuple[float, float] = (2.0, 5.0),
        session: requests.Session | None = None,
        retries: int = 3,
        backoff: float = 2.0,
        timeout: float = 20.0,
    ) -> None:
        self.cookie = cookie
        self.delay = delay
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(self._headers())

    def _headers(self) -> dict[str, str]:
        return {
            "Cookie": self.cookie,
            "User-Agent": USER_AGENT,
            "Referer": "https://www.zhihu.com/",
            "x-requested-with": "fetch",
            "Accept": "application/json, text/plain, */*",
        }

    def _sleep(self) -> None:
        low, high = self.delay
        if high > 0:
            time.sleep(random.uniform(low, high))

    def get_json(self, path: str, params: dict | None = None) -> dict:
        url = path if path.startswith("http") else BASE + path
        last_status = None
        for attempt in range(self.retries):
            self._sleep()
            response = self.session.get(url, params=params, timeout=self.timeout)
            status = response.status_code
            if status == 200:
                return response.json()
            if status == 401:
                raise AuthError("知乎登录态无效或已过期，请重新导出 Cookie。")
            if status == 403:
                raise RateLimitError("知乎返回 403（风控或权限限制），本轮同步已停止。")
            if status == 404:
                raise NotFoundError(f"内容不存在：{url}")
            last_status = status
            if status == 429 or status >= 500:
                if attempt + 1 < self.retries:
                    time.sleep(self.backoff * (2**attempt))
                    continue
                raise ApiError(f"知乎接口连续失败（HTTP {status}）：{url}")
            raise ApiError(f"知乎接口返回 HTTP {status}：{url}")
        raise ApiError(f"知乎接口失败（HTTP {last_status}）：{url}")

    def check_auth(self) -> dict:
        data = self.get_json("/api/v4/me")
        return {
            "id": data.get("id"),
            "url_token": data.get("url_token"),
            "name": data.get("name"),
        }

    def iter_items(self, kind: str, url_token: str, limit: int = 20) -> Iterator[ContentItem]:
        if kind not in DETAIL_KIND:
            raise ValueError(f"未知内容类型：{kind}")
        offset = 0
        while True:
            data = self.get_json(
                f"/api/v4/members/{url_token}/{kind}",
                params={
                    "include": INCLUDE_FIELDS[kind],
                    "limit": limit,
                    "offset": offset,
                },
            )
            for raw in data.get("data") or []:
                yield item_from_raw(kind, raw)
            if data.get("paging", {}).get("is_end", True):
                break
            offset += limit

    def get_detail(self, kind: str, item_id: str) -> ContentItem | None:
        try:
            raw = self.get_json(f"/api/v4/{DETAIL_KIND[kind]}/{item_id}")
        except NotFoundError:
            return None
        return item_from_raw(kind, raw)

    def download(self, url: str) -> tuple[bytes, str]:
        """下载图片等静态资源；CDN 请求不套用接口的 2–5 秒限速。"""
        response = self.session.get(url, timeout=self.timeout)
        if response.status_code != 200:
            raise OSError(f"HTTP {response.status_code}: {url}")
        headers = getattr(response, "headers", {}) or {}
        return response.content, headers.get("Content-Type", "")

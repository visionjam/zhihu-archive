"""读取并规范化知乎登录 Cookie。

支持 Netscape cookies.txt、Copy as cURL、Cookie 请求头、JSON 导出与纯 cookie 字符串。
任何情况下都不打印 Cookie 的值。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


class CookieFormatError(ValueError):
    """Cookie 文件缺失、格式无法识别或缺少登录令牌。"""


def _parse_netscape(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_") :]
        elif line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 7:
            rows.append((fields[0], fields[5], fields[6]))
    return rows


def extract_cookie(text: str) -> str:
    """从任意支持的导出文本中提取一条 Cookie 字符串。"""
    value = text.strip()
    if not value:
        raise CookieFormatError("Cookie 文件是空的。")

    if "\t" in value[:4000]:
        rows = _parse_netscape(value)
        if rows:
            zhihu = [row for row in rows if "zhihu.com" in row[0]]
            if not zhihu:
                raise CookieFormatError(
                    "Netscape 文件里没有 zhihu.com 的 Cookie，请确认已登录知乎再导出。"
                )
            return "; ".join(f"{name}={cookie_value}" for _, name, cookie_value in zhihu)

    if "curl" in value.lower() or re.search(r"-H\s|--header\s", value):
        match = re.search(
            r"(?:-H|--header)\s+['\"]cookie:\s*([^'\"]+)['\"]", value, re.IGNORECASE
        )
        if match:
            return match.group(1).strip()

    match = re.search(r"^cookie\s*:\s*(.+)$", value, re.IGNORECASE | re.MULTILINE)
    if match and "=" in match.group(1):
        return match.group(1).strip()

    if value[:1] in "[{":
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and "cookies" in data:
            data = data["cookies"]
        if isinstance(data, list) and data and isinstance(data[0], dict) and "name" in data[0]:
            cookies = [
                item
                for item in data
                if "value" in item and ("domain" not in item or "zhihu.com" in str(item["domain"]))
            ]
            if not cookies:
                raise CookieFormatError("JSON 导出里没有 zhihu.com 的 Cookie。")
            return "; ".join(f"{item['name']}={item['value']}" for item in cookies)

    if re.match(r"^[\w\-%.]+\s*=", value) and "curl" not in value.lower():
        return value

    raise CookieFormatError(
        "无法识别 Cookie 文件格式（支持 Netscape / cURL / Cookie 头 / JSON / 纯字符串）。"
    )


def default_cookie_path() -> Path:
    override = os.environ.get("ZHIHU_COOKIE_FILE")
    if override:
        return Path(override)
    return Path.home() / ".config" / "zhihu-archive" / "cookie.txt"


def load_cookie(path: Path | None = None) -> str:
    """读取 Cookie；缺少 z_c0 时视为无效登录态。"""
    cookie_path = path or default_cookie_path()
    try:
        text = cookie_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise CookieFormatError(f"无法读取 Cookie 文件：{cookie_path}") from exc

    cookie = extract_cookie(text)
    names = [part.split("=", 1)[0].strip() for part in cookie.split(";") if "=" in part]
    if "z_c0" not in names:
        raise CookieFormatError(f"Cookie 里缺少 z_c0 登录令牌，请重新登录后导出：{cookie_path}")
    return cookie

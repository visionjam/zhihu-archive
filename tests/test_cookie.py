import json

import pytest

from zhihu_archive.cookie import CookieFormatError, extract_cookie, load_cookie

NETSCAPE = """# Netscape HTTP Cookie File
.zhihu.com\tTRUE\t/\tTRUE\t1999999999\tz_c0\tTOKEN
.example.com\tTRUE\t/\tTRUE\t1999999999\tsession\tOTHER
"""


def test_extract_netscape_keeps_only_zhihu():
    assert extract_cookie(NETSCAPE) == "z_c0=TOKEN"


def test_extract_netscape_httponly_prefix():
    text = "#HttpOnly_.zhihu.com\tTRUE\t/\tTRUE\t1999999999\tz_c0\tTOKEN\n"
    assert extract_cookie(text) == "z_c0=TOKEN"


def test_extract_curl_header():
    text = """curl 'https://www.zhihu.com/' -H 'cookie: z_c0=TOKEN; d_c0=DEVICE'"""
    assert extract_cookie(text) == "z_c0=TOKEN; d_c0=DEVICE"


def test_extract_cookie_header_line():
    assert extract_cookie("Cookie: z_c0=TOKEN; _xsrf=ABC") == "z_c0=TOKEN; _xsrf=ABC"


def test_extract_plain_string():
    assert extract_cookie("z_c0=TOKEN; d_c0=DEVICE") == "z_c0=TOKEN; d_c0=DEVICE"


def test_extract_json_export():
    text = json.dumps(
        [
            {"name": "z_c0", "value": "TOKEN", "domain": ".zhihu.com"},
            {"name": "d_c0", "value": "DEVICE", "domain": ".zhihu.com"},
        ]
    )
    assert extract_cookie(text) == "z_c0=TOKEN; d_c0=DEVICE"


def test_extract_unknown_format_raises():
    with pytest.raises(CookieFormatError):
        extract_cookie("这不是一份 cookie")


def test_load_cookie_rejects_missing_login_token(tmp_path):
    path = tmp_path / "cookie.txt"
    path.write_text("d_c0=DEVICE", encoding="utf-8")
    with pytest.raises(CookieFormatError):
        load_cookie(path)


def test_load_cookie_reads_file(tmp_path):
    path = tmp_path / "cookie.txt"
    path.write_text("z_c0=TOKEN; d_c0=DEVICE", encoding="utf-8")
    assert load_cookie(path) == "z_c0=TOKEN; d_c0=DEVICE"

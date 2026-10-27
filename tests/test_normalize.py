from zhihu_archive.normalize import normalize_page, set_math_flag

PAGE = """---
title: "测试"
date: 2026-01-01
---

正文
"""

PAGE_WITH_MATH = """---
title: "测试"
date: 2026-01-01
math: true
---

正文
"""


def test_math_flag_added_for_real_formula():
    page = PAGE.replace("正文", "公式 $x^2$")
    assert "math: true" in set_math_flag(page)


def test_math_flag_ignores_dollar_in_code():
    page = PAGE.replace(
        "正文", "命令 `$env:PATH`\n\n```powershell\n$HOME\n```"
    )
    assert "math: true" not in set_math_flag(page)


def test_false_math_flag_removed():
    assert "math: true" not in set_math_flag(PAGE_WITH_MATH)


def test_normalize_page_dedupes_adjacent_images():
    page = PAGE.replace(
        "正文", "![image](./a.jpg)![image](./a.jpg)\n\n![image](./a.jpg)"
    )
    result = normalize_page(page)
    assert result.count("./a.jpg") == 2


def test_normalize_page_is_idempotent():
    once = normalize_page(PAGE_WITH_MATH, "https://example.com/post/")
    assert normalize_page(once, "https://example.com/post/") == once
    assert 'canonicalURL: "https://example.com/post/"' in once

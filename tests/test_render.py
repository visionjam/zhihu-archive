from datetime import date, datetime, timezone

from zhihu_archive.models import ContentItem
from zhihu_archive.render import build_front_matter, html_to_markdown, render_page

ITEM = ContentItem(
    kind="answers",
    id="456",
    title='问题 "标题"',
    question='问题 "标题"',
    url="https://www.zhihu.com/question/123/answer/456",
    created=datetime(2019, 8, 14, tzinfo=timezone.utc),
    updated=datetime(2019, 8, 14, tzinfo=timezone.utc),
    content_html="",
    voteup_count=12,
    comment_count=3,
    tags=["数学"],
)


def test_images_and_links_rewritten():
    html = (
        '<p><img src="https://pic1.zhimg.com/a.jpg"> '
        '<a href="//link.zhihu.com/?target=https%3A%2F%2Fexample.com">链接</a></p>'
    )
    md = html_to_markdown(html, {"https://pic1.zhimg.com/a.jpg": "./a.jpg"})
    assert "![image](./a.jpg)" in md
    assert "https://example.com" in md


def test_equation_span_becomes_tex():
    html = '<span class="ztext-math" data-tex="x^2+y^2=1"></span>'
    assert "$x^2+y^2=1$" in html_to_markdown(html)


def test_relative_links_become_absolute():
    html = '<p><a href="/question/1">问题</a></p>'
    assert "https://www.zhihu.com/question/1" in html_to_markdown(html)


def test_front_matter_quotes_special_titles():
    fm = build_front_matter(ITEM, False, date(2026, 10, 22))
    assert 'title: "问题 \\"标题\\""' in fm


def test_deleted_banner_and_original_link():
    page = render_page(ITEM, "正文", deleted=True, archived_at=date(2026, 10, 22))
    assert "该内容已从知乎删除" in page
    assert "https://www.zhihu.com/question/123/answer/456" in page
    assert "archived_at: 2026-10-22" in page


def test_math_front_matter_when_body_has_math():
    page = render_page(ITEM, "公式 $x^2$", deleted=False, archived_at=date(2026, 10, 22))
    assert "math: true" in page

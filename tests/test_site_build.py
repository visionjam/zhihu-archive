import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def build_site(tmp_path):
    public = tmp_path / "public"
    subprocess.run(
        [
            "hugo",
            "--source",
            str(ROOT),
            "--destination",
            str(public),
            "--quiet",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return public


def read_page(public, *parts):
    return public.joinpath(*parts, "index.html").read_text(encoding="utf-8")


@pytest.fixture
def temp_bundles():
    created = []

    def add(kind, slug, title, date="2026-01-01", zhihu_id=None):
        bundle = ROOT / "content" / kind / slug
        bundle.mkdir(parents=True)
        zhihu_id_line = f'zhihu_id: "{zhihu_id}"\n' if zhihu_id else ""
        (bundle / "index.md").write_text(
            f'---\ntitle: "{title}"\ndate: {date}\ntype: {kind}\n'
            f"{zhihu_id_line}---\n\n测试正文\n",
            encoding="utf-8",
        )
        created.append(bundle)
        return bundle

    yield add
    for bundle in reversed(created):
        shutil.rmtree(bundle, ignore_errors=True)


@pytest.fixture
def temp_likes():
    path = ROOT / "data" / "likes.json"
    backup = path.read_bytes() if path.exists() else None

    def write(data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    yield write
    if backup is None:
        path.unlink(missing_ok=True)
    else:
        path.write_bytes(backup)


@pytest.fixture
def temp_stats():
    path = ROOT / "data" / "zhihu_stats.json"
    backup = path.read_bytes() if path.exists() else None

    def write(data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    yield write
    if backup is None:
        path.unlink(missing_ok=True)
    else:
        path.write_bytes(backup)


def stats_entry(
    kind, item_id, title, votes, words=100, minutes=1, comments=0, deleted=False
):
    return {
        "kind": kind,
        "id": item_id,
        "title": title,
        "url": f"https://www.zhihu.com/{item_id}",
        "rel_path": f"/{kind}/{item_id}/",
        "created": "2026-01-01",
        "deleted": deleted,
        "voteup_count": votes,
        "comment_count": comments,
        "word_count": words,
        "reading_minutes": minutes,
    }


def test_ranking_page_sorts_by_votes_and_shows_totals(tmp_path, temp_stats):
    temp_stats(
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "totals": {
                "items": 3,
                "words": 300,
                "votes": 15,
                "comments": 0,
                "by_kind": {"answers": 1, "articles": 1, "pins": 1},
            },
            "items": {
                "answers:test-low": stats_entry(
                    "answers", "test-low", "TABTEST-RANK-LOW", 1, deleted=True
                ),
                "articles:test-high": stats_entry(
                    "articles", "test-high", "TABTEST-RANK-HIGH", 9
                ),
                "pins:test-mid": stats_entry(
                    "pins", "test-mid", "TABTEST-RANK-MID", 5
                ),
            },
        }
    )
    public = build_site(tmp_path)
    ranking = read_page(public, "ranking")
    flat = re.sub(r"\s+", " ", ranking)

    high = flat.index("TABTEST-RANK-HIGH")
    mid = flat.index("TABTEST-RANK-MID")
    low = flat.index("TABTEST-RANK-LOW")
    assert high < mid < low
    assert "收录 3 篇" in flat
    assert "总字数 300" in flat
    assert "总赞 15" in flat
    assert 'href="/zhihu-archive/answers/test-low/"' in flat
    assert "rank-top" not in flat
    for kind in ("answers", "articles", "pins"):
        assert f'data-filter="{kind}"' in flat
        assert f'data-kind="{kind}"' in flat
    assert "已删除" in flat
    assert "gc.zgo.at" not in ranking


def test_goatcounter_loads_only_when_configured(tmp_path, temp_bundles, temp_stats):
    config = ROOT / "hugo.yml"
    backup = config.read_bytes()
    temp_bundles("answers", "_stats_gc", "TABTEST-GC-SINGLE", zhihu_id="gc")
    temp_stats(
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "totals": {
                "items": 1,
                "words": 2,
                "votes": 1,
                "comments": 0,
                "by_kind": {"answers": 1, "articles": 0, "pins": 0},
            },
            "items": {
                "answers:gc": stats_entry("answers", "gc", "TABTEST-GC-SINGLE", 1, 2, 1)
            },
        }
    )
    try:
        config.write_text(
            backup.decode("utf-8").replace('goatcounter: ""', 'goatcounter: "tabtest"'),
            encoding="utf-8",
        )
        public = build_site(tmp_path)
        home = read_page(public)
        page = read_page(public, "answers", "_stats_gc")

        assert "tabtest.goatcounter.com/count" in home
        assert "gc.zgo.at/count.js" in home
        assert "站内浏览" in page
        assert "gc-views" in page
    finally:
        config.write_bytes(backup)


def test_site_likes_show_on_post_and_ranking(
    tmp_path, temp_bundles, temp_stats, temp_likes
):
    temp_bundles("answers", "_likes_test", "TABTEST-SITE-LIKES", zhihu_id="_likes_test")
    temp_stats(
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "totals": {
                "items": 1,
                "words": 100,
                "votes": 7,
                "comments": 2,
                "by_kind": {"answers": 1, "articles": 0, "pins": 0},
            },
            "items": {
                "answers:_likes_test": stats_entry(
                    "answers", "_likes_test", "TABTEST-SITE-LIKES", 7, 100, 1, comments=2
                )
            },
        }
    )
    temp_likes(
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "items": {"/zhihu-archive/answers/_likes_test/": {"likes": 4, "url": ""}},
        }
    )
    public = build_site(tmp_path)

    page = read_page(public, "answers", "_likes_test")
    assert "站内赞&nbsp;4" in page
    assert "giscus.app/client.js" in page

    ranking = re.sub(r"\s+", " ", read_page(public, "ranking"))
    assert "站内赞 4" in ranking


def test_about_page_has_common_links_and_contributions(tmp_path):
    public = build_site(tmp_path)
    about = read_page(public, "about")

    for needle in (
        "GitHub",
        "知乎",
        "Gmail",
        "QQ",
        "博客",
        "归档站",
        "博客源码",
        "归档站源码",
        "RSS",
        "GitHub 贡献",
    ):
        assert needle in about
    assert "github.com/visionjam/visionjam.github.io" in about
    assert "github.com/visionjam/zhihu-archive" in about
    assert "在 GitHub 查看贡献" in about


def test_single_page_shows_votes_words_and_reading_time(
    tmp_path, temp_bundles, temp_stats
):
    temp_bundles("answers", "_stats_single", "TABTEST-STATS-SINGLE", zhihu_id="single")
    temp_stats(
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "totals": {
                "items": 1,
                "words": 1234,
                "votes": 7,
                "comments": 2,
                "by_kind": {"answers": 1, "articles": 0, "pins": 0},
            },
            "items": {
                "answers:single": stats_entry(
                    "answers", "single", "TABTEST-STATS-SINGLE", 7, 1234, 4, comments=2
                )
            },
        }
    )
    public = build_site(tmp_path)
    page = read_page(public, "answers", "_stats_single")

    assert "赞同&nbsp;7" in page
    assert "评论&nbsp;2" in page
    assert "1,234&nbsp;字" in page
    assert "约&nbsp;4&nbsp;分钟" in page
    assert "gc.zgo.at" not in page


def test_katex_assets_exist():
    assert (ROOT / "static" / "katex" / "katex.min.css").exists()
    assert (ROOT / "static" / "katex" / "katex.min.js").exists()
    assert (ROOT / "static" / "katex" / "auto-render.min.js").exists()


def test_footer_mentions_source(tmp_path):
    subprocess.run(
        [
            "hugo",
            "--source",
            str(ROOT),
            "--destination",
            str(tmp_path / "public"),
            "--quiet",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    html = (tmp_path / "public" / "index.html").read_text(encoding="utf-8")
    assert "内容来自知乎" in html
    assert "https://visionjam.github.io/" in html


def test_math_page_loads_local_katex(tmp_path):
    bundle = ROOT / "content" / "answers" / "_math_test"
    bundle.mkdir(parents=True)
    (bundle / "index.md").write_text(
        '---\ntitle: "数学测试"\ndate: 2026-01-01\nmath: true\n---\n\n$x^2$\n',
        encoding="utf-8",
    )
    try:
        subprocess.run(
            [
                "hugo",
                "--source",
                str(ROOT),
                "--destination",
                str(tmp_path / "public"),
                "--quiet",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        html = (tmp_path / "public" / "answers" / "_math_test" / "index.html").read_text(
            encoding="utf-8"
        )
        assert "katex/katex.min.css" in html
        assert "cdn.jsdelivr.net" not in html
    finally:
        shutil.rmtree(bundle, ignore_errors=True)


def test_home_has_five_content_tabs(tmp_path):
    public = build_site(tmp_path)
    home = read_page(public)

    nav = re.search(r'<nav class="type-tabs".*?</nav>', home, re.S)
    assert nav, "主页缺少分类标签栏"
    for label in ("主页", "全部", "回答", "文章", "想法"):
        assert f">{label}</a>" in nav.group(0)
    for href in (
        "/zhihu-archive/",
        "/zhihu-archive/all/",
        "/zhihu-archive/answers/",
        "/zhihu-archive/articles/",
        "/zhihu-archive/pins/",
    ):
        assert f'href="{href}"' in nav.group(0)

    assert (public / "all" / "index.html").exists()
    all_page = read_page(public, "all")
    assert 'aria-current="page"' in all_page


def test_home_excludes_pins_but_all_page_aggregates_every_type(tmp_path, temp_bundles):
    temp_bundles("answers", "_tab_answer", "TABTEST-ANSWER-MARKER", "2026-10-20")
    temp_bundles("articles", "_tab_article", "TABTEST-ARTICLE-MARKER", "2026-10-19")
    temp_bundles("pins", "_tab_pin", "TABTEST-PIN-MARKER", "2026-10-18")
    public = build_site(tmp_path)

    home = read_page(public)
    assert "TABTEST-ANSWER-MARKER" in home
    assert "TABTEST-ARTICLE-MARKER" in home
    assert "TABTEST-PIN-MARKER" not in home

    all_page = read_page(public, "all")
    for marker in (
        "TABTEST-ANSWER-MARKER",
        "TABTEST-ARTICLE-MARKER",
        "TABTEST-PIN-MARKER",
    ):
        assert marker in all_page


def test_home_caps_latest_at_twenty(tmp_path, temp_bundles):
    for i in range(21):
        day = 4 + i // 2
        hour = 12 if i % 2 else 0
        if i == 0:
            title = "TABTEST-OLDEST-MARKER"
        elif i == 20:
            title = "TABTEST-NEWEST-MARKER"
        else:
            title = f"TABTEST-LATEST-{i:02d}"
        temp_bundles(
            "answers",
            f"_tab_limit_{i:02d}",
            title,
            f"2026-10-{day:02d}T{hour:02d}:00:00+08:00",
        )

    public = build_site(tmp_path)
    home = read_page(public)

    assert home.count('class="post-entry"') == 20
    assert "TABTEST-NEWEST-MARKER" in home
    assert "TABTEST-OLDEST-MARKER" not in home
    assert "page/2" not in home
    assert 'href="/zhihu-archive/all/"' in home
    assert "查看全部内容" in home

    all_pages = "\n".join(
        page.read_text(encoding="utf-8")
        for page in (public / "all").rglob("*.html")
    )
    assert "TABTEST-OLDEST-MARKER" in all_pages


def test_home_shows_pinned_items_before_latest(tmp_path):
    data = ROOT / "data" / "pinned.yml"
    backup = data.read_bytes() if data.exists() else None
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_text(
        "items:\n"
        '  - title: "TABTEST-PINNED-TITLE"\n'
        '    url: "https://example.com/tabtest"\n'
        '    description: "TABTEST-PINNED-DESC"\n',
        encoding="utf-8",
    )
    try:
        public = build_site(tmp_path)
        home = read_page(public)
        assert "TABTEST-PINNED-TITLE" in home
        assert "TABTEST-PINNED-DESC" in home
        assert "https://example.com/tabtest" in home
        assert home.index("TABTEST-PINNED-TITLE") < home.index(
            '<h2 class="home-section-title">最新</h2>'
        )
    finally:
        if backup is None:
            data.unlink()
        else:
            data.write_bytes(backup)


def test_all_page_is_not_listed_in_archive_or_search_index(tmp_path):
    public = build_site(tmp_path)
    assert (public / "all" / "index.html").exists()

    archives = read_page(public, "archives")
    assert "/all/" not in archives

    search_index = (public / "index.json").read_text(encoding="utf-8")
    assert "/all/" not in search_index

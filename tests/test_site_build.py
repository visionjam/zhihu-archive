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

    def add(kind, slug, title, date="2026-01-01"):
        bundle = ROOT / "content" / kind / slug
        bundle.mkdir(parents=True)
        (bundle / "index.md").write_text(
            f'---\ntitle: "{title}"\ndate: {date}\ntype: {kind}\n---\n\n测试正文\n',
            encoding="utf-8",
        )
        created.append(bundle)
        return bundle

    yield add
    for bundle in reversed(created):
        shutil.rmtree(bundle, ignore_errors=True)


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

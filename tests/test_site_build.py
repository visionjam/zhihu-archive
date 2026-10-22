import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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

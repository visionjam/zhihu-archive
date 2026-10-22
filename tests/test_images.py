from zhihu_archive.images import ImageLocalizer


class FakeClient:
    def __init__(self, mapping):
        self.mapping = mapping

    def download(self, url):
        return self.mapping[url]


def test_two_images_saved_and_rewritten(tmp_path):
    html = (
        '<p><img src="https://pic1.zhimg.com/a.png">'
        '<img src="https://pic1.zhimg.com/b.png"></p>'
    )
    client = FakeClient(
        {
            "https://pic1.zhimg.com/a.png": (b"aaa", "image/png"),
            "https://pic1.zhimg.com/b.png": (b"bbb", "image/jpeg"),
        }
    )
    new_html, saved, failed = ImageLocalizer(client, tmp_path).localize(html)
    assert len(saved) == 2 and failed == []
    assert (tmp_path / saved[0]).read_bytes() in (b"aaa", b"bbb")
    assert all(name in new_html for name in saved)


def test_same_image_saved_once(tmp_path):
    html = (
        '<img src="https://pic1.zhimg.com/a.png">'
        '<img src="https://pic1.zhimg.com/a.png">'
    )
    client = FakeClient({"https://pic1.zhimg.com/a.png": (b"aaa", "image/png")})
    _, saved, _ = ImageLocalizer(client, tmp_path).localize(html)
    assert len(saved) == 1


def test_failed_image_keeps_url(tmp_path):
    html = '<img src="https://pic1.zhimg.com/missing.png">'

    class Failing:
        def download(self, url):
            raise OSError("404")

    new_html, saved, failed = ImageLocalizer(Failing(), tmp_path).localize(html)
    assert saved == [] and failed == ["https://pic1.zhimg.com/missing.png"]
    assert "https://pic1.zhimg.com/missing.png" in new_html


def test_lazy_loaded_image_uses_real_source(tmp_path):
    html = (
        '<img src="data:image/svg+xml;utf8,<svg></svg>" '
        'data-original="https://pic1.zhimg.com/a.png">'
    )
    client = FakeClient({"https://pic1.zhimg.com/a.png": (b"aaa", "image/png")})
    new_html, saved, failed = ImageLocalizer(client, tmp_path).localize(html)
    assert len(saved) == 1 and failed == []
    assert "./" in new_html


def test_protocol_relative_image_is_fetched(tmp_path):
    html = '<img src="//pic1.zhimg.com/a.png">'
    client = FakeClient({"https://pic1.zhimg.com/a.png": (b"aaa", "image/png")})
    _, saved, failed = ImageLocalizer(client, tmp_path).localize(html)
    assert len(saved) == 1 and failed == []

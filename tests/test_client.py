import pytest
import requests

from zhihu_archive.client import AuthError, NotFoundError, RateLimitError, ZhihuClient


class FakeResponse:
    def __init__(self, status, data=None, content=b"", headers=None):
        self.status_code = status
        self._data = data or {}
        self.text = str(self._data)
        self.content = content
        self.headers = headers or {}

    def json(self):
        return self._data


class DownloadSession:
    def __init__(self, response):
        self.headers = {}
        self.response = response
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        return self.response


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return self.responses.pop(0)


def test_401_raises_auth_error():
    client = ZhihuClient("z_c0=x", session=FakeSession([FakeResponse(401)]), delay=(0, 0))
    with pytest.raises(AuthError):
        client.get_json("/api/v4/me")


def test_403_raises_rate_limit_error():
    client = ZhihuClient("z_c0=x", session=FakeSession([FakeResponse(403)]), delay=(0, 0))
    with pytest.raises(RateLimitError):
        client.get_json("/api/v4/me")


def test_404_raises_not_found():
    client = ZhihuClient("z_c0=x", session=FakeSession([FakeResponse(404)]), delay=(0, 0))
    with pytest.raises(NotFoundError):
        client.get_json("/api/v4/answers/1")


def test_500_retries_then_succeeds():
    session = FakeSession([FakeResponse(500), FakeResponse(200, {"ok": True})])
    client = ZhihuClient("z_c0=x", session=session, delay=(0, 0), retries=3, backoff=0)
    assert client.get_json("/api/v4/me") == {"ok": True}
    assert session.calls == 2


def test_download_uses_separate_session_without_cookie():
    download_session = DownloadSession(
        FakeResponse(200, content=b"png", headers={"Content-Type": "image/png"})
    )
    client = ZhihuClient(
        "z_c0=SECRET",
        session=FakeSession([]),
        delay=(0, 0),
        download_session=download_session,
    )
    content, content_type = client.download("https://example.com/a.png")
    assert content == b"png"
    assert content_type == "image/png"
    assert "Cookie" not in download_session.headers
    assert download_session.calls == 1


class FlakySession(FakeSession):
    def __init__(self, failures, response):
        super().__init__([])
        self.failures = failures
        self.response = response

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise requests.ConnectionError("boom")
        return self.response


def test_connection_error_retries_then_succeeds():
    session = FlakySession(2, FakeResponse(200, {"ok": True}))
    client = ZhihuClient(
        "z_c0=x", session=session, delay=(0, 0), retries=3, backoff=0
    )
    assert client.get_json("/api/v4/me") == {"ok": True}
    assert session.calls == 3


def test_check_auth_returns_identity_fields():
    session = FakeSession(
        [FakeResponse(200, {"id": "1", "url_token": "token", "name": "名字"})]
    )
    client = ZhihuClient("z_c0=x", session=session, delay=(0, 0))
    assert client.check_auth() == {"id": "1", "url_token": "token", "name": "名字"}

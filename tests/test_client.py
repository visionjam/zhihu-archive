import pytest

from zhihu_archive.client import AuthError, NotFoundError, RateLimitError, ZhihuClient


class FakeResponse:
    def __init__(self, status, data=None):
        self.status_code = status
        self._data = data or {}
        self.text = str(self._data)

    def json(self):
        return self._data


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


def test_check_auth_returns_identity_fields():
    session = FakeSession(
        [FakeResponse(200, {"id": "1", "url_token": "token", "name": "名字"})]
    )
    client = ZhihuClient("z_c0=x", session=session, delay=(0, 0))
    assert client.check_auth() == {"id": "1", "url_token": "token", "name": "名字"}

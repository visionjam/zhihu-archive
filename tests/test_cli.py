import pytest

import sync
from zhihu_archive.cookie import CookieFormatError


def test_parse_types():
    assert sync.parse_types("answers,pins") == ("answers", "pins")


def test_parse_types_rejects_unknown():
    with pytest.raises(ValueError):
        sync.parse_types("comments")


def test_check_returns_2_on_cookie_error(monkeypatch):
    def fail():
        raise CookieFormatError("bad cookie")

    monkeypatch.setattr(sync, "load_cookie", fail)
    assert sync.main(["--check"]) == 2


def test_parser_defaults():
    args = sync.build_parser().parse_args([])
    assert args.types == "answers,articles,pins"
    assert args.dry_run is False
    assert args.limit is None

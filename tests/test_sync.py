from datetime import datetime, timezone

from zhihu_archive.client import ApiError
from zhihu_archive.models import ContentItem
from zhihu_archive.state import SyncState
from zhihu_archive.sync import run_sync


def item(i, kind="answers"):
    return ContentItem(
        kind=kind,
        id=str(i),
        title=f"标题{i}",
        question=f"问题{i}",
        url=f"https://www.zhihu.com/question/1/answer/{i}",
        created=datetime(2020, 1, 1, tzinfo=timezone.utc),
        updated=datetime(2020, 1, 1, tzinfo=timezone.utc),
        content_html=f"<p>正文{i}</p>",
        voteup_count=0,
        comment_count=0,
        tags=[],
    )


class FakeClient:
    def __init__(self, items):
        self.items = items
        self.downloaded = set()

    def iter_items(self, kind, url_token):
        yield from self.items.get(kind, [])

    def get_detail(self, kind, item_id):
        return next((x for x in self.items.get(kind, []) if x.id == item_id), None)

    def download(self, url):
        return b"img", "image/png"


def test_first_sync_writes_bundles(tmp_path):
    state = SyncState()
    report = run_sync(
        FakeClient({"answers": [item(1), item(2)]}),
        state,
        {"content_root": tmp_path, "state_dir": tmp_path / ".local"},
        limit=None,
    )
    assert report.added == 2
    assert (tmp_path / "answers/1/index.md").exists()
    assert (tmp_path / ".local/raw/answers/1.json").exists()
    assert "标题1" in (tmp_path / "answers/1/index.md").read_text(encoding="utf-8")


def test_second_sync_is_incremental(tmp_path):
    state = SyncState()
    client = FakeClient({"answers": [item(1)]})
    config = {"content_root": tmp_path, "state_dir": tmp_path / ".local"}
    run_sync(client, state, config)
    before = (tmp_path / "answers/1/index.md").stat().st_mtime_ns
    report = run_sync(client, state, config)
    assert report.added == 0
    assert (tmp_path / "answers/1/index.md").stat().st_mtime_ns == before


def test_missing_item_kept_and_marked_deleted(tmp_path):
    state = SyncState()
    config = {"content_root": tmp_path, "state_dir": tmp_path / ".local"}
    run_sync(FakeClient({"answers": [item(1)]}), state, config)
    report = run_sync(FakeClient({"answers": []}), state, config)
    assert report.marked_deleted == 1
    text = (tmp_path / "answers/1/index.md").read_text(encoding="utf-8")
    assert "deleted: true" in text
    assert "该内容已从知乎删除" in text


def test_excluded_item_removed(tmp_path):
    local = tmp_path / ".local"
    local.mkdir()
    (local / "exclude.txt").write_text("answers:1\n", encoding="utf-8")
    config = {"content_root": tmp_path, "state_dir": local}
    run_sync(FakeClient({"answers": [item(1)]}), SyncState(), config)
    assert not (tmp_path / "answers/1").exists()


class NoDetailClient(FakeClient):
    def get_detail(self, kind, item_id):
        raise AssertionError("列表已带全文时不应请求详情")


class CountingDetailClient(FakeClient):
    def __init__(self, items):
        super().__init__(items)
        self.detail_calls = 0

    def get_detail(self, kind, item_id):
        self.detail_calls += 1
        return next(x for x in self.items[kind] if x.id == item_id)


def test_sync_uses_list_content_without_detail(tmp_path):
    state = SyncState()
    report = run_sync(
        NoDetailClient({"answers": [item(1)]}),
        state,
        {"content_root": tmp_path, "state_dir": tmp_path / ".local"},
    )
    assert report.added == 1
    assert "正文1" in (tmp_path / "answers/1/index.md").read_text(encoding="utf-8")


def test_truncated_item_fetches_detail(tmp_path):
    truncated = item(1)
    truncated.truncated = True
    client = CountingDetailClient({"answers": [truncated]})
    report = run_sync(
        client,
        SyncState(),
        {"content_root": tmp_path, "state_dir": tmp_path / ".local"},
    )
    assert report.added == 1
    assert client.detail_calls == 1


class PartialDetailClient(FakeClient):
    def __init__(self, items):
        super().__init__(items)
        self.detail_calls = []

    def get_detail(self, kind, item_id):
        self.detail_calls.append(item_id)
        if item_id == "2":
            raise ApiError("boom")
        return next(x for x in self.items[kind] if x.id == item_id)


class FailingImageClient(FakeClient):
    def download(self, url):
        raise OSError("404")


class FailingListClient(FakeClient):
    def iter_items(self, kind, url_token):
        if kind == "answers":
            raise ApiError("boom")
        yield from super().iter_items(kind, url_token)


def test_per_item_failure_does_not_abort_kind(tmp_path):
    items = [item(1), item(2), item(3)]
    items[1].truncated = True
    report = run_sync(
        PartialDetailClient({"answers": items}),
        SyncState(),
        {"content_root": tmp_path, "state_dir": tmp_path / ".local"},
    )
    assert report.added == 2
    assert report.failed == 1
    assert report.incomplete is False
    assert (tmp_path / "answers/1/index.md").exists()
    assert (tmp_path / "answers/3/index.md").exists()
    assert not (tmp_path / "answers/2/index.md").exists()


def test_image_failure_is_retried_next_run(tmp_path):
    broken = item(1)
    broken.content_html = '<p><img src="https://pic1.zhimg.com/a.png"></p>'
    state = SyncState()
    config = {"content_root": tmp_path, "state_dir": tmp_path / ".local"}
    report = run_sync(FailingImageClient({"answers": [broken]}), state, config)
    assert report.failed == 1
    assert "answers:1" not in state.items
    assert (tmp_path / "answers/1/index.md").exists()

    report2 = run_sync(FakeClient({"answers": [broken]}), state, config)
    assert report2.added == 1
    assert "answers:1" in state.items


def test_list_failure_marks_incomplete(tmp_path):
    report = run_sync(
        FailingListClient({}),
        SyncState(),
        {"content_root": tmp_path, "state_dir": tmp_path / ".local"},
    )
    assert report.incomplete is True


def test_exclude_accepts_chinese_alias(tmp_path):
    local = tmp_path / ".local"
    local.mkdir()
    (local / "exclude.txt").write_text("回答:1\n", encoding="utf-8")
    run_sync(
        FakeClient({"answers": [item(1)]}),
        SyncState(),
        {"content_root": tmp_path, "state_dir": local},
    )
    assert not (tmp_path / "answers/1").exists()


def test_unexclude_rebuilds_missing_bundle(tmp_path):
    state = SyncState()
    config = {"content_root": tmp_path, "state_dir": tmp_path / ".local"}
    client = FakeClient({"answers": [item(1)]})
    run_sync(client, state, config)
    local = tmp_path / ".local"
    (local / "exclude.txt").write_text("answers:1\n", encoding="utf-8")
    run_sync(client, state, config)
    assert not (tmp_path / "answers/1").exists()
    (local / "exclude.txt").write_text("", encoding="utf-8")
    run_sync(client, state, config)
    assert (tmp_path / "answers/1/index.md").exists()


def test_dry_run_writes_nothing(tmp_path):
    config = {"content_root": tmp_path / "content", "state_dir": tmp_path / ".local"}
    report = run_sync(FakeClient({"answers": [item(1)]}), SyncState(), config, dry_run=True)
    assert report.added == 1
    assert not (tmp_path / "content").exists()

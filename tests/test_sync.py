from datetime import datetime, timezone

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


def test_dry_run_writes_nothing(tmp_path):
    config = {"content_root": tmp_path / "content", "state_dir": tmp_path / ".local"}
    report = run_sync(FakeClient({"answers": [item(1)]}), SyncState(), config, dry_run=True)
    assert report.added == 1
    assert not (tmp_path / "content").exists()

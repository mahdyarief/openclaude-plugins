from josc.watch_diff import diff_results, render_rss, result_keys, watch_fingerprint
from josc.watches import WATCH_SCHEMA, WatchStore, check_watch


def test_fingerprint_is_stable_across_dict_key_order():
    a = watch_fingerprint("q", None, ["crossref", "openalex"], {"year_from": 2020})
    b = watch_fingerprint("q", None, ["openalex", "crossref"], {"year_from": 2020})
    assert a == b
    assert len(a) == 64


def test_fingerprint_changes_when_query_changes():
    assert watch_fingerprint("a", None, None, None) != watch_fingerprint("b", None, None, None)


def test_result_keys_prefers_doi_and_falls_back_to_title():
    keys = result_keys(
        [
            {"doi": "https://doi.org/10.1/ABC", "title": "One"},
            {"title": "Attention Is All You Need!"},
        ]
    )
    assert keys == {"doi:10.1/abc", "title:attention is all you need"}


def test_diff_results_returns_only_unseen_papers():
    previous = {"doi:10.1/old"}
    current = [
        {"doi": "10.1/old", "title": "Old"},
        {"doi": "10.1/new", "title": "New"},
    ]
    fresh = diff_results(previous, current)
    assert [paper["title"] for paper in fresh] == ["New"]


def test_render_rss_escapes_markup():
    out = render_rss(
        "Watch & Roll",
        "https://example.test/feed",
        [{"title": "A <b>Title</b>", "url": "https://example.test/a?x=1&y=2"}],
    )
    assert out.startswith("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
    assert "Watch &amp; Roll" in out
    assert "A &lt;b&gt;Title&lt;/b&gt;" in out
    assert "x=1&amp;y=2" in out


class FakeStore:

    def __init__(self):
        self.rows = {}

    async def execute(self, sql, params):
        normalized = " ".join(sql.split()).lower()
        if normalized.startswith("create table"):
            return None, []
        if normalized.startswith("insert into search_watches"):
            watch_id, query, author, sources, filters, seen, last_results, fingerprint, created_at = params
            self.rows[watch_id] = {
                "id": watch_id,
                "query": query,
                "author": author,
                "sources": sources,
                "filters": filters,
                "seen": seen,
                "last_results": last_results,
                "created_at": created_at,
            }
            return None, []
        if normalized.startswith("select id, query, author, sources, filters, seen"):
            return None, [
                (
                    row["id"],
                    row["query"],
                    row["author"],
                    row["sources"],
                    row["filters"],
                    row["seen"],
                    row["last_results"],
                    row["created_at"],
                )
                for row in self.rows.values()
            ]
        if normalized.startswith("update search_watches"):
            seen, last_results, watch_id = params
            if watch_id in self.rows:
                self.rows[watch_id]["seen"] = seen
                self.rows[watch_id]["last_results"] = last_results
            return None, []
        if normalized.startswith("delete from search_watches"):
            self.rows.pop(params[0], None)
            return None, []
        raise AssertionError(f"unexpected SQL: {sql}")


def test_watch_schema_declares_the_table():
    assert "search_watches" in WATCH_SCHEMA
    assert "fingerprint" in WATCH_SCHEMA


async def test_create_list_and_delete_round_trip():
    store = FakeStore()
    watches = WatchStore(store)
    await watches.setup()

    watch_id = await watches.create("graph neural networks", sources=["openalex"])
    listed = await watches.list()
    assert len(listed) == 1
    assert listed[0]["query"] == "graph neural networks"

    assert await watches.delete(watch_id) is True
    assert await watches.list() == []


async def test_check_watch_reports_only_new_papers_and_marks_them_seen():
    store = FakeStore()
    watches = WatchStore(store)
    await watches.setup()
    watch_id = await watches.create("q")
    watch = await watches.get(watch_id)

    async def runner(_watch):
        return [
            {"doi": "10.1/old", "title": "Old"},
            {"doi": "10.1/new", "title": "New"},
        ]

    await watches.mark_seen(watch_id, {"doi:10.1/old"}, [])
    watch = await watches.get(watch_id)
    result = await check_watch(watch, runner, watches)

    assert [paper["title"] for paper in result["new"]] == ["New"]
    refreshed = await watches.get(watch_id)
    assert "doi:10.1/new" in refreshed["seen"]

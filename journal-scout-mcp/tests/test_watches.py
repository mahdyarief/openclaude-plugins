from josc.watch_diff import diff_results, render_rss, result_keys, watch_fingerprint


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

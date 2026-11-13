from josc.quota import quota_report


class FakeProvider:
    def __init__(self, name):
        self.name = name


DOCUMENTED = {
    "scopus": "Weekly quota, tracked via X-RateLimit-* / X-ELS-Status headers",
    "openalex": "100,000 requests/day (polite pool)",
    "semanticscholar": "1 request/second shared pool",
    "crossref": "Polite pool, no hard cap",
    "pubmed": "3 requests/second without a key, 10 with",
    "arxiv": "1 request per 3 seconds",
    "dblp": "Best effort, no published quota",
    "opencitations": "180 requests/minute",
    "unpaywall": "100,000 requests/day",
}


def test_empty_providers_yields_empty_sources():
    assert quota_report([]) == {"sources": {}}


def test_all_documented_providers_have_limits():
    report = quota_report([FakeProvider(name) for name in DOCUMENTED])
    sources = report["sources"]
    assert list(sources) == list(DOCUMENTED)
    for name, limit in DOCUMENTED.items():
        assert sources[name]["limit"] == limit


def test_undocumented_provider_still_emitted():
    report = quota_report([FakeProvider("mystery")])
    entry = report["sources"]["mystery"]
    assert entry["limit"] == "Not documented"
    assert entry["notes"]


def test_quota_counters_are_none():
    report = quota_report([FakeProvider(name) for name in DOCUMENTED])
    for entry in report["sources"].values():
        assert entry["used"] is None
        assert entry["remaining"] is None
        assert entry["reset"] is None


def test_source_key_matches_dict_key():
    report = quota_report([FakeProvider(name) for name in DOCUMENTED] + [FakeProvider("mystery")])
    for key, entry in report["sources"].items():
        assert entry["source"] == key


def test_providers_without_usable_name_are_skipped():
    report = quota_report([FakeProvider(""), FakeProvider(None), object(), FakeProvider("arxiv")])
    assert list(report["sources"]) == ["arxiv"]

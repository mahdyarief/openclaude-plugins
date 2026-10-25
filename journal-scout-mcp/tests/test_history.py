"""Search fingerprinting and the history write path.

The history table is upserted on a fingerprint so that repeating an identical
search refreshes one row instead of appending a duplicate.
"""

from josc.api import history


class FakeStore:
    def __init__(self):
        self.calls = []

    async def record_search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return "row-id"


def _fingerprint(**overrides):
    params = {
        "query": "machine learning",
        "sources": ["garuda"],
        "limit_per_source": 10,
        "year_from": None,
        "year_to": None,
        "tech_only": False,
        "offset": 0,
        "affiliation": None,
        "issn": None,
        "orcid": None,
        "doi": None,
        "sort": None,
        "order": "desc",
    }
    params.update(overrides)
    return history.search_fingerprint(**params)


def test_fingerprint_is_stable_for_identical_parameters():
    assert _fingerprint() == _fingerprint()


def test_fingerprint_ignores_source_order():
    assert _fingerprint(sources=["garuda", "arxiv"]) == _fingerprint(
        sources=["arxiv", "garuda"]
    )


def test_fingerprint_changes_when_a_filter_changes():
    assert _fingerprint() != _fingerprint(year_from=2020)
    assert _fingerprint() != _fingerprint(limit_per_source=25)


def test_fingerprint_changes_when_topic_filter_changes():
    assert _fingerprint() != _fingerprint(topic="machine learning")


async def test_remember_forwards_the_fingerprint_to_the_store(monkeypatch):
    store = FakeStore()
    monkeypatch.setattr(history, "_store", lambda: store)

    await history._remember(
        query="machine learning",
        sources=["garuda"],
        filters={},
        payload={"results": [{"title": "A"}]},
        fingerprint="fp-1",
    )

    query, kwargs = store.calls[0]
    assert query == "machine learning"
    assert kwargs["fingerprint"] == "fp-1"
    assert kwargs["result_count"] == 1

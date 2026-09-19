from journal_scout_mcp.providers.base import ProviderBase


class DummyProvider(ProviderBase):
    name = "dummy"


async def test_default_methods_return_empty():
    p = DummyProvider(fetcher=None)
    assert p.supports_search is True
    assert await p.search("anything", 5) == []
    assert await p.get("anything") is None
    assert await p.citations("anything", 5) == []


def test_name_and_search_flag():
    p = DummyProvider(fetcher=None)
    assert p.name == "dummy"
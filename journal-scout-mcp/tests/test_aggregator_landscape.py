from josc.aggregator import build_landscape


async def test_build_landscape_searches_then_clusters(monkeypatch):
    from josc.models import Paper

    papers = [
        Paper(doi="10.1/ml1", title="Deep learning for vision", year=2019,
              topics=["Machine Learning"], authors=["Alice"]),
        Paper(doi="10.1/ml2", title="Neural networks for language", year=2021,
              topics=["Machine Learning"], authors=["Bob"]),
        Paper(doi="10.1/db1", title="Database query optimization", year=2018,
              topics=["Databases"], authors=["Carol"]),
        Paper(doi="10.1/db2", title="Database indexing strategies", year=2020,
              topics=["Databases"], authors=["Dave"]),
    ]

    async def fake_search(*args, **kwargs):
        return {"results": papers, "query_translated": {}, "query_scoping": {}}

    import josc.aggregator as aggregator
    monkeypatch.setattr(aggregator, "search_all", fake_search)

    result = await build_landscape("neural networks", n_clusters=2)

    assert result["stats"]["papers"] == 4
    assert result["stats"]["clusters"] == 2
    assert len(result["nodes"]) == 4
    ml = {n["title"] for n in result["nodes"] if n["cluster"] == 0}
    assert len(ml) == 2

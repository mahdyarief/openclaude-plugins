import asyncio

from josc.providers.exa import ExaProvider, parse_text_results

TEXT = (
    "Title: Graph neural networks | Nature Reviews Methods Primers\n"
    "URL: https://www.nature.com/articles/s43586-024-00294-7\n"
    "Published: 2024-03-07T03:21:03.000Z\n"
    "Author: Corso, Gabriele, Stark, Hannes\n"
    "Highlights:\n"
    "Graphs are flexible mathematical objects used in GNNs.\n"
    "\n---\n\n"
    "Title: Graph neural network\n"
    "URL: https://en.wikipedia.org/wiki/Graph_neural_network\n"
    "Published: 2023-05-01T00:00:00.000Z\n"
    "Highlights:\n"
    "A graph neural network is an artificial neural network.\n"
)


def test_parse_text_results_splits_blocks_and_fields():
    items = parse_text_results(TEXT)
    assert [item["title"] for item in items] == [
        "Graph neural networks | Nature Reviews Methods Primers",
        "Graph neural network",
    ]
    assert items[0]["author"] == "Corso, Gabriele, Stark, Hannes"
    assert items[0]["publishedDate"] == "2024-03-07T03:21:03.000Z"
    assert "Graphs are flexible" in items[0]["text"]
    assert items[1]["text"] == "A graph neural network is an artificial neural network."


def test_exa_search_maps_plain_text_to_papers(monkeypatch):
    async def fake_call(tool_name, arguments, **kwargs):
        assert tool_name == "web_search_exa"
        return TEXT

    monkeypatch.setattr("josc.providers.exa.call_exa_mcp", fake_call)

    papers = asyncio.run(ExaProvider(object()).search("graph neural networks", 5))

    assert [paper.title for paper in papers] == [
        "Graph neural networks | Nature Reviews Methods Primers",
        "Graph neural network",
    ]
    assert papers[0].year == 2024
    assert papers[0].authors == ["Corso, Gabriele", "Stark, Hannes"]
    assert "Graphs are flexible" in papers[0].abstract
    assert papers[1].url == "https://en.wikipedia.org/wiki/Graph_neural_network"

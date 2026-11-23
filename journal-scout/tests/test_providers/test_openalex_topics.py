import httpx

from josc.providers.openalex import OpenAlexProvider


async def test_openalex_maps_full_topic_hierarchy_and_keywords():
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "doi": "https://doi.org/10.1/x",
                "title": "A paper",
                "publication_year": 2020,
                "cited_by_count": 10,
                "primary_topic": {
                    "display_name": "Machine Learning",
                    "subfield": {"display_name": "Artificial Intelligence"},
                    "field": {"display_name": "Computer Science"},
                    "domain": {"display_name": "Information and Computing Sciences"},
                },
                "topics": [
                    {"display_name": "Deep Learning", "id": "https://openalex.org/T1"},
                    {"display_name": "Neural Networks", "id": "https://openalex.org/T2"},
                ],
                "keywords": [
                    {"display_name": "gradient descent"},
                    {"display_name": "backpropagation"},
                ],
                "authorships": [],
            }
        ]
    }

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAlexProvider(client)
    try:
        paper = (await provider.search("paper", 5))[0]
        assert "Machine Learning" in paper.topics
        assert "Deep Learning" in paper.topics
        assert "Neural Networks" in paper.topics
        assert "Artificial Intelligence" in paper.topics
        assert "Computer Science" in paper.topics
        assert "gradient descent" in paper.keywords
        assert "backpropagation" in paper.keywords
        assert "https://openalex.org/T1" in paper.topic_ids
        assert "https://openalex.org/T2" in paper.topic_ids
        assert [
            "Information and Computing Sciences",
            "Computer Science",
            "Artificial Intelligence",
            "Machine Learning",
        ] in paper.topic_paths
    finally:
        await client.aclose()

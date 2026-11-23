import httpx
import pytest

from josc.providers.openalex import OpenAlexProvider


def _topic(topic_id, name, score=0.9, cited_by_count=100):
    return {
        "id": f"https://openalex.org/{topic_id}",
        "display_name": name,
        "works_count": 5000,
        "cited_by_count": cited_by_count,
        "relevance_score": score,
        "description": f"About {name}.",
        "keywords": [
            {"display_name": "neural nets"},
            {"display_name": "gradient descent"},
        ],
        "domain": {"display_name": "Information and Computing Sciences"},
        "field": {"display_name": "Computer Science"},
        "subfield": {"display_name": "Artificial Intelligence"},
    }


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_classify_topics_returns_ranked_candidates():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["search"] = request.url.params.get("search")
        seen["per_page"] = request.url.params.get("per-page")
        return httpx.Response(
            200,
            json={
                "results": [
                    _topic("T10102", "Machine Learning", score=0.97),
                    _topic("T10234", "Deep Learning", score=0.84),
                ]
            },
        )

    client = _client(handler)
    provider = OpenAlexProvider(client)
    try:
        candidates = await provider.classify_topics(
            "claim prediction with transformers"
        )
        assert seen["path"] == "/topics"
        assert seen["search"] == "claim prediction with transformers"
        assert seen["per_page"] == "5"
        assert [c["name"] for c in candidates] == ["Machine Learning", "Deep Learning"]
        assert candidates[0]["score"] == 0.97
        assert candidates[0]["id"] == "https://openalex.org/T10102"
        assert candidates[0]["works_count"] == 5000
        assert candidates[0]["path"] == [
            "Information and Computing Sciences",
            "Computer Science",
            "Artificial Intelligence",
            "Machine Learning",
        ]
        assert candidates[0]["keywords"] == ["neural nets", "gradient descent"]
    finally:
        await client.aclose()


async def test_classify_topics_falls_back_to_topics_on_matching_works():
    seen = []

    def handler(request):
        seen.append((request.url.path, request.url.params.get("search")))
        if request.url.path == "/topics":
            return httpx.Response(200, json={"results": []})
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "primary_topic": _topic("T10102", "Machine Learning", 0.78),
                    },
                    {
                        "primary_topic": _topic("T10102", "Machine Learning", 0.72),
                    },
                    {
                        "primary_topic": _topic("T10234", "Deep Learning", 0.65),
                    },
                ]
            },
        )

    client = _client(handler)
    provider = OpenAlexProvider(client)
    try:
        candidates = await provider.classify_topics(
            "claim prediction with transformers in health insurance"
        )
        assert seen == [
            ("/topics", "claim prediction with transformers in health insurance"),
            (
                "/works",
                "claim prediction with transformers in health insurance",
            ),
        ]
        assert [candidate["name"] for candidate in candidates] == [
            "Machine Learning",
            "Deep Learning",
        ]
        assert candidates[0]["score"] == pytest.approx(0.75)
        assert candidates[0]["works_count"] == 2
    finally:
        await client.aclose()


async def test_classify_topics_subfield_fallback_inherits_primary_topic_score():
    def handler(request):
        if request.url.path == "/works":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "primary_topic": {
                                **_topic("T10102", "Machine Learning", 0.82),
                                "score": 0.82,
                            }
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"results": []})

    client = _client(handler)
    provider = OpenAlexProvider(client)
    try:
        candidates = await provider.classify_topics(
            "long research question", level="subfield"
        )
        assert candidates[0]["name"] == "Artificial Intelligence"
        assert candidates[0]["level"] == "subfield"
        assert candidates[0]["score"] == pytest.approx(0.82)
    finally:
        await client.aclose()


async def test_classify_topics_supports_coarser_taxonomy_levels():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/subfields/1702",
                        "display_name": "Artificial Intelligence",
                        "works_count": 900,
                        "cited_by_count": 12,
                        "domain": {
                            "display_name": "Information and Computing Sciences"
                        },
                        "field": {"display_name": "Computer Science"},
                    }
                ]
            },
        )

    client = _client(handler)
    provider = OpenAlexProvider(client)
    try:
        candidates = await provider.classify_topics("ai", level="subfield")
        assert seen["path"] == "/subfields"
        assert candidates[0]["level"] == "subfield"
        assert candidates[0]["path"] == [
            "Information and Computing Sciences",
            "Computer Science",
            "Artificial Intelligence",
        ]
        assert candidates[0]["keywords"] == []
    finally:
        await client.aclose()


async def test_classify_topics_honours_limit():
    seen = {}

    def handler(request):
        if request.url.path == "/topics":
            seen["per_page"] = request.url.params.get("per-page")
        return httpx.Response(200, json={"results": []})

    client = _client(handler)
    provider = OpenAlexProvider(client)
    try:
        assert await provider.classify_topics("ai", limit=12) == []
        assert seen["per_page"] == "12"
    finally:
        await client.aclose()


async def test_classify_topics_rejects_unknown_level():
    client = _client(lambda request: httpx.Response(200, json={"results": []}))
    provider = OpenAlexProvider(client)
    try:
        with pytest.raises(ValueError, match="level"):
            await provider.classify_topics("ai", level="kingdom")
    finally:
        await client.aclose()

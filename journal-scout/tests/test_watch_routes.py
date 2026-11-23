from josc.api.watch_routes import watch_feed


def test_watch_feed_renders_persisted_results_without_network():
    class FakeWatchStore:
        async def get(self, watch_id):
            return {
                "id": watch_id,
                "query": "graph neural networks",
                "seen": {"doi:10.1/a"},
                "last_results": [{"doi": "10.1/a", "title": "Old Paper"}],
            }

    class FakeRequest:
        path_params = {"watch_id": "abc"}
        app = type("App", (), {"state": type("S", (), {"watches": FakeWatchStore()})()})()

    response = __import__("asyncio").run(watch_feed(FakeRequest()))
    assert response.media_type == "application/rss+xml"
    assert b"<rss" in response.body
    assert b"Old Paper" in response.body

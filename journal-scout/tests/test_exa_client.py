import json

import httpx

from josc.exa import parse_mcp_body, parse_payload
from josc.exa_client import call_exa_mcp, load_exa_keys, reset_key_index


def _sse(payload: dict) -> str:
    return f"event: message\ndata: {json.dumps(payload)}\n\n"


def _result(text: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": text}]},
    }


def test_parse_mcp_body_accepts_sse():
    body = _sse(_result('{"ok": true}'))
    payload = parse_mcp_body(body)
    assert payload is not None
    assert payload["result"]["content"][0]["text"] == '{"ok": true}'


def test_parse_payload_decodes_json_text():
    assert parse_payload(_result('[{"title": "A"}]')) == [{"title": "A"}]


def test_load_keys_splits_comma_list(monkeypatch):
    monkeypatch.setenv("EXA_API_KEYS", " one , two,three ")
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    assert load_exa_keys() == ["one", "two", "three"]


def test_load_keys_accepts_semicolons_and_json(monkeypatch):
    monkeypatch.setenv("EXA_API_KEYS", "one;two")
    assert load_exa_keys() == ["one", "two"]
    monkeypatch.setenv("EXA_API_KEYS", '["a", "b"]')
    assert load_exa_keys() == ["a", "b"]


def test_load_keys_dedupes_and_falls_back_to_single(monkeypatch):
    monkeypatch.setenv("EXA_API_KEYS", "")
    monkeypatch.setenv("EXA_API_KEY", "solo")
    assert load_exa_keys() == ["solo"]
    monkeypatch.setenv("EXA_API_KEYS", "k1,k1,k2")
    assert load_exa_keys() == ["k1", "k2"]


def test_load_keys_empty_when_unset(monkeypatch):
    monkeypatch.delenv("EXA_API_KEYS", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    assert load_exa_keys() == []


async def test_call_rotates_on_401(monkeypatch):
    monkeypatch.setattr(
        "josc.exa_client.load_exa_keys", lambda: ["bad-key", "good-key"]
    )
    reset_key_index()

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("authorization", "")
        seen.append(auth)
        if auth.endswith("bad-key"):
            return httpx.Response(401, text="unauthorized")
        return httpx.Response(
            200,
            text=_sse(_result('[{"title": "Found", "url": "https://x"}]')),
            headers={"content-type": "text/event-stream"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await call_exa_mcp("web_search_exa", {"query": "x"}, client=client)

    assert result == [{"title": "Found", "url": "https://x"}]
    assert seen == ["Bearer bad-key", "Bearer good-key"]


async def test_call_exhausts_keys_and_raises(monkeypatch):
    monkeypatch.setattr("josc.exa_client.load_exa_keys", lambda: ["only-key"])
    reset_key_index()

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(429, text="slow down"))
    )
    try:
        await call_exa_mcp("web_search_exa", {"query": "x"}, client=client)
    except Exception as exc:  # noqa: BLE001 - provider error surface
        assert "429" in str(exc)
    else:
        raise AssertionError("expected a rotation failure")

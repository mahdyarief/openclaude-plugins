import json

import httpx
import pytest

from josc.consensus_key import (
    mask_key,
    rotate_consensus_key,
    verify_consensus_key,
    write_consensus_key,
)


def _mock_client(status: int = 200, exc: Exception | None = None) -> httpx.AsyncClient:
    def handler(request):
        if exc is not None:
            raise exc
        return httpx.Response(status, json={"results": [], "is_end": True})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_mask_key_keeps_prefix_and_masks_rest():
    masked = mask_key("ak_JDKAVS6VFX4D1E7278T0Q56ADA6QW5AE")
    assert masked.startswith("ak_JDK")
    assert "*" in masked
    assert "AVS6VFX4D1E7278T0Q56ADA6QW5AE" not in masked
    assert len(masked) == len("ak_JDKAVS6VFX4D1E7278T0Q56ADA6QW5AE")


def test_mask_key_empty_returns_empty():
    assert mask_key("") == ""


async def test_verify_reports_valid_on_200():
    client = _mock_client(200)
    result = await verify_consensus_key("test-key", client=client)
    assert result["valid"] is True
    assert result["status"] == 200
    assert result["error"] is None


async def test_verify_reports_invalid_on_401():
    client = _mock_client(401)
    result = await verify_consensus_key("bad-key", client=client)
    assert result["valid"] is False
    assert result["status"] == 401


async def test_verify_handles_network_error():
    client = _mock_client(exc=httpx.ConnectError("boom"))
    result = await verify_consensus_key("test-key", client=client)
    assert result["valid"] is False
    assert result["status"] is None
    assert "boom" in result["error"]


async def test_rotate_persists_key_when_valid(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"api_key": "x"}), encoding="utf-8")
    client = _mock_client(200)

    result = await rotate_consensus_key("ak_NEW123", client=client, config_path=config_path)

    assert result["rotated"] is True
    assert result["valid"] is True
    assert result["key_hint"].startswith("ak_NEW")
    written = json.loads(config_path.read_text(encoding="utf-8"))
    assert written["consensus_api_key"] == "ak_NEW123"
    assert written["api_key"] == "x"


async def test_rotate_rejects_key_when_invalid(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"api_key": "x", "consensus_api_key": "ak_OLD"}), encoding="utf-8")
    client = _mock_client(401)

    result = await rotate_consensus_key("ak_BAD", client=client, config_path=config_path)

    assert result["rotated"] is False
    assert result["valid"] is False
    written = json.loads(config_path.read_text(encoding="utf-8"))
    # The old key must survive a failed rotation.
    assert written["consensus_api_key"] == "ak_OLD"

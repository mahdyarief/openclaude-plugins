"""Client-side routes must fall back to index.html, not 404."""

from starlette.exceptions import HTTPException
import pytest

from josc.api import SPAStaticFiles

INDEX = "<!doctype html><html><body><div id='root'></div></body></html>"


def _scope(path: str, method: str = "GET") -> dict:
    return {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
    }


@pytest.fixture
def spa(tmp_path):
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return SPAStaticFiles(directory=str(tmp_path), html=True)


def _served_text(response) -> str:
    with open(response.path, encoding="utf-8") as handle:
        return handle.read()


async def test_client_route_serves_index(spa):
    response = await spa.get_response("history", _scope("/history"))
    assert response.status_code == 200
    assert _served_text(response) == INDEX


async def test_nested_client_route_serves_index(spa):
    response = await spa.get_response("history/abc", _scope("/history/abc"))
    assert response.status_code == 200
    assert _served_text(response) == INDEX


async def test_real_asset_still_served(spa):
    response = await spa.get_response("assets/app.js", _scope("/assets/app.js"))
    assert response.status_code == 200
    assert _served_text(response) == "console.log(1)"


async def test_missing_asset_still_404(spa):
    with pytest.raises(HTTPException) as exc:
        await spa.get_response("assets/nope.js", _scope("/assets/nope.js"))
    assert exc.value.status_code == 404


async def test_non_get_does_not_fall_back(spa):
    with pytest.raises(HTTPException) as exc:
        await spa.get_response("history", _scope("/history", method="POST"))
    assert exc.value.status_code == 405

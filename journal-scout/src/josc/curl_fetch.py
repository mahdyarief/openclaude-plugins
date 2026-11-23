"""Download through the system ``curl`` binary, the primary PDF client.

Some publisher front ends (Springer's "Client Challenge", PeerJ's 403) reject
httpx's connection while serving the same URL to ``curl`` normally, so
``get_fulltext`` tries curl first and falls back to httpx. This module shells
out to ``curl`` with an argument list (never a shell string), follows
redirects, and caps time and size.

Enabled by default when ``curl`` is on ``PATH``; disable with
``JOURNAL_SCOUT_CURL=0`` or ``"curl_fallback": false`` in config.json.
"""

import asyncio
import os
import shutil
import tempfile
from typing import Dict, Optional, Tuple

from .models import ProviderError

PROVIDER = "curl"
MAX_SECONDS = 60
MAX_BYTES = 100 * 1024 * 1024
_STATUS_MARK = "\n__JOSC_STATUS__"


def curl_path() -> Optional[str]:
    return shutil.which("curl")


def _command(binary: str, url: str, out_path: str, headers: Optional[Dict[str, str]]):
    command = [
        binary,
        "--silent",
        "--show-error",
        "--location",
        "--max-redirs", "10",
        "--max-time", str(MAX_SECONDS),
        "--max-filesize", str(MAX_BYTES),
        "--proto", "=https,http",
        "--compressed",
        "--output", out_path,
        "--write-out", _STATUS_MARK + "%{http_code} %{url_effective}",
    ]
    for name, value in (headers or {}).items():
        if name.lower() == "user-agent":
            command += ["--user-agent", value]
        else:
            command += ["--header", f"{name}: {value}"]
    # ``--`` ends option parsing, so a URL can never be read as a flag.
    command += ["--", url]
    return command


async def curl_get(
    url: str, headers: Optional[Dict[str, str]] = None
) -> Tuple[str, bytes]:
    """GET ``url`` with curl; return ``(final_url, body)`` or raise ``ProviderError``."""
    binary = curl_path()
    if not binary:
        raise ProviderError(PROVIDER, "curl is not installed")
    handle, out_path = tempfile.mkstemp(prefix="josc-curl-")
    os.close(handle)
    try:
        process = await asyncio.create_subprocess_exec(
            *_command(binary, url, out_path, headers),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=MAX_SECONDS + 10
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise ProviderError(PROVIDER, f"curl timed out fetching {url}")
        report = stdout.decode("utf-8", "replace")
        status_text, _, final_url = report.rpartition(_STATUS_MARK)[2].partition(" ")
        if process.returncode != 0:
            detail = stderr.decode("utf-8", "replace").strip()[:200]
            raise ProviderError(PROVIDER, f"curl exit {process.returncode}: {detail}")
        status = int(status_text) if status_text.isdigit() else 0
        if status >= 400 or status == 0:
            raise ProviderError(PROVIDER, f"HTTP {status} via curl")
        with open(out_path, "rb") as body:
            return final_url.strip() or url, body.read()
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass

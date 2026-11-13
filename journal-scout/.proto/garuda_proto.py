"""
Prototipe parser Garuda (garuda.kemdiktisaintek.go.id).

Di luar src/josc dengan sengaja: ini alat riset untuk memvalidasi selector
sebelum masuk ke arsitektur provider. Jalankan:

    uv run python .proto/garuda_proto.py "neural network" 2
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

BASE = "https://garuda.kemdiktisaintek.go.id"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
YEAR_RE = re.compile(r"\((\d{4})\)")
# Some records say "SNATI) 2005" with no parentheses at all.
BARE_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
VOLUME_RE = re.compile(r"\bVol\.?\s*(\d+)\b", re.IGNORECASE)
ISSUE_RE = re.compile(r"\bNo\.?\s*(\d+)\b", re.IGNORECASE)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)")
# Garuda appends " -" to authors that have no linked affiliation page.
AUTHOR_TRAILER_RE = re.compile(r"\s*-\s*$")


@dataclass
class GarudaRecord:
    title: str = ""
    authors: List[str] = field(default_factory=list)
    venue: Optional[str] = None
    year: Optional[int] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    detail_url: Optional[str] = None
    source_url: Optional[str] = None


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _parse_venue(raw: str) -> tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return None, None, None, None
    year = None
    if m := YEAR_RE.search(raw):
        year = int(m.group(1))
    elif m := BARE_YEAR_RE.search(raw):
        year = int(m.group(1))
    volume = None
    if m := VOLUME_RE.search(raw):
        volume = m.group(1)
    issue = None
    if m := ISSUE_RE.search(raw):
        issue = m.group(1)
    venue = raw
    venue = YEAR_RE.sub("", venue)
    if year is not None:
        venue = BARE_YEAR_RE.sub("", venue, count=1) if not YEAR_RE.search(raw) else venue
    venue = VOLUME_RE.sub("", venue)
    venue = ISSUE_RE.sub("", venue)
    venue = re.sub(r"\(\s*\)", "", venue)
    # Garuda joins "venue : full-title (month)" and "venue , : month", so the
    # leftovers arrive as runs of separators. Collapse them to one clean cut.
    venue = re.split(r"\s*[,:]\s*[,:]\s*|\s+:\s+", venue)[0]
    venue = re.sub(r"[,:]+\s*$", "", venue)
    venue = re.sub(r"\s{2,}", " ", venue).strip(" .,:;-")
    return (venue or None), year, volume, issue


def parse_page(html: str) -> List[GarudaRecord]:
    soup = BeautifulSoup(html, "lxml")
    records: List[GarudaRecord] = []

    for item in soup.select("div.article-item"):
        rec = GarudaRecord()

        title_link = item.select_one("a.title-article")
        if title_link is None:
            continue
        rec.title = _text(title_link)
        if href := title_link.get("href"):
            rec.detail_url = href if href.startswith("http") else BASE + href

        rec.authors = [
            cleaned
            for a in item.select("a.author-article")
            if (cleaned := AUTHOR_TRAILER_RE.sub("", _text(a)))
        ]

        subtitles = item.select("xmp.subtitle-article")
        if subtitles:
            venue, year, volume, issue = _parse_venue(_text(subtitles[0]))
            rec.venue, rec.year, rec.volume, rec.issue = venue, year, volume, issue
        if len(subtitles) > 1:
            rec.publisher = _text(subtitles[1]) or None

        for link in item.select("p.action-article a[href]"):
            text = _text(link).lower()
            href = link["href"]
            if "original source" in text:
                rec.source_url = href
            elif "download original" in text and not rec.source_url:
                rec.source_url = href

        blob = " ".join([rec.title, rec.detail_url or "", rec.source_url or ""])
        if m := DOI_RE.search(blob):
            rec.doi = m.group(1).rstrip(".,;")

        records.append(rec)

    return records


def fetch(query: str, page: int = 1, timeout: float = 25.0) -> str:
    with httpx.Client(
        headers={"User-Agent": UA, "Accept-Language": "id,en;q=0.8"},
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        resp = client.get(f"{BASE}/documents", params={"q": query, "page": page})
        resp.raise_for_status()
        return resp.text


def main(argv: List[str]) -> int:
    query = argv[1] if len(argv) > 1 else "neural network"
    page = int(argv[2]) if len(argv) > 2 else 1

    html = fetch(query, page)
    records = parse_page(html)

    print(f"query={query!r} page={page} html={len(html)}b records={len(records)}")
    print("-" * 78)
    for i, rec in enumerate(records, 1):
        print(f"[{i}] {rec.title[:110]}")
        print(f"    authors  : {', '.join(rec.authors) or '-'}")
        print(f"    venue    : {rec.venue or '-'}")
        print(f"    year/vol : {rec.year or '-'} / {rec.volume or '-'} / no {rec.issue or '-'}")
        print(f"    publisher: {rec.publisher or '-'}")
        print(f"    doi      : {rec.doi or '-'}")
        print(f"    detail   : {rec.detail_url or '-'}")
        print(f"    source   : {rec.source_url or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

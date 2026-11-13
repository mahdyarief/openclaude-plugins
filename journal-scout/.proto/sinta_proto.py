"""
Prototipe parser Sinta (sinta.kemdiktisaintek.go.id).

Dua hal yang diurai:
1. ``/journals?q=``  -> daftar jurnal + ISSN + akreditasi (S1..S6).
2. ``/authors/profile/{id}`` -> daftar artikel penulis (judul, jurnal, tahun,
   sitasi, quartile) — satu-satunya tempat Sinta memaparkan data artikel.

Jalankan:

    uv run python .proto/sinta_proto.py journals "information systems"
    uv run python .proto/sinta_proto.py author 6009908
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

BASE = "https://sinta.kemdiktisaintek.go.id"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)

ISSN_RE = re.compile(r"([PE])-ISSN\s*:\s*(\d{7,9}[0-9Xx])?", re.IGNORECASE)
SUBJECT_RE = re.compile(r"Subject Area\s*:\s*(.+?)\s*$", re.IGNORECASE)
ACCRED_RE = re.compile(r"\bS([1-6])\b")
CITED_RE = re.compile(r"(\d+)\s*cited", re.IGNORECASE)
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
QUARTILE_RE = re.compile(r"\bQ([1-4])\b")


@dataclass
class SintaJournal:
    title: str = ""
    profile_url: Optional[str] = None
    affiliation: Optional[str] = None
    p_issn: Optional[str] = None
    e_issn: Optional[str] = None
    subject: Optional[str] = None
    accreditation: Optional[str] = None  # "S1".."S6"
    impact: Optional[float] = None
    h5_index: Optional[int] = None
    citations_5yr: Optional[int] = None
    garuda_url: Optional[str] = None


@dataclass
class SintaArticle:
    title: str = ""
    venue: Optional[str] = None
    year: Optional[int] = None
    citations: Optional[int] = None
    quartile: Optional[str] = None
    url: Optional[str] = None
    author_order: Optional[str] = None


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _num(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    cleaned = raw.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _int(raw: Optional[str]) -> Optional[int]:
    value = _num(raw)
    return int(value) if value is not None else None


def parse_journals(html: str) -> List[SintaJournal]:
    soup = BeautifulSoup(html, "lxml")
    journals: List[SintaJournal] = []

    for item in soup.select("div.list-item"):
        rec = SintaJournal()

        name_link = item.select_one("div.affil-name a")
        if name_link is None:
            continue
        rec.title = _text(name_link)
        if href := name_link.get("href"):
            rec.profile_url = href if href.startswith("http") else BASE + href

        if loc := item.select_one("div.affil-loc a"):
            rec.affiliation = _text(loc) or None

        profile_id = item.select_one("div.profile-id")
        if profile_id is not None:
            raw = _text(profile_id)
            for kind, value in ISSN_RE.findall(raw):
                value = (value or "").strip() or None
                if value:
                    if kind.upper() == "P":
                        rec.p_issn = value
                    else:
                        rec.e_issn = value
            if m := SUBJECT_RE.search(raw):
                rec.subject = m.group(1).strip() or None

        if accred := item.select_one("div.stat-prev span.accredited"):
            if m := ACCRED_RE.search(_text(accred)):
                rec.accreditation = f"S{m.group(1)}"

        stats = {}
        for block in item.select("div.stat-profile .pr-num"):
            label_node = block.find_next_sibling("div", class_="pr-txt")
            if label_node is not None:
                stats[_text(label_node).lower()] = _text(block)
        rec.impact = _num(stats.get("impact"))
        rec.h5_index = _int(stats.get("h5-index"))
        rec.citations_5yr = _int(stats.get("citations 5yr"))

        for link in item.select("a[href*='garuda.kemdiktisaintek.go.id/journal/view/']"):
            rec.garuda_url = link.get("href")
            break

        journals.append(rec)

    return journals


def parse_author_articles(html: str) -> List[SintaArticle]:
    soup = BeautifulSoup(html, "lxml")
    articles: List[SintaArticle] = []

    for item in soup.select("div.ar-list-item"):
        rec = SintaArticle()

        title_link = item.select_one("div.ar-title a")
        if title_link is None:
            continue
        rec.title = _text(title_link)
        if href := title_link.get("href"):
            rec.url = href

        if pub := item.select_one("a.ar-pub"):
            rec.venue = _text(pub) or None
        if quart := item.select_one("a.ar-quartile"):
            if m := QUARTILE_RE.search(_text(quart)):
                rec.quartile = f"Q{m.group(1)}"
        if year := item.select_one("a.ar-year"):
            if m := YEAR_RE.search(_text(year)):
                rec.year = int(m.group(1))
        if cited := item.select_one("a.ar-cited"):
            if m := CITED_RE.search(_text(cited)):
                rec.citations = int(m.group(1))

        for meta in item.select("a"):
            text = _text(meta)
            if text.lower().startswith("author order"):
                rec.author_order = text.split(":", 1)[-1].strip() or None

        articles.append(rec)

    return articles


def fetch_journals(query: str, page: int = 1, timeout: float = 25.0) -> str:
    with httpx.Client(
        headers={"User-Agent": UA, "Accept-Language": "id,en;q=0.8"},
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        resp = client.get(f"{BASE}/journals", params={"q": query, "page": page})
        resp.raise_for_status()
        return resp.text


def fetch_author(author_id: str, timeout: float = 25.0) -> str:
    with httpx.Client(
        headers={"User-Agent": UA, "Accept-Language": "id,en;q=0.8"},
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        resp = client.get(f"{BASE}/authors/profile/{author_id}")
        resp.raise_for_status()
        return resp.text


def _print_journals(journals: List[SintaJournal]) -> None:
    for i, rec in enumerate(journals, 1):
        print(f"[{i}] {rec.title}")
        print(f"    affiliation : {rec.affiliation or '-'}")
        print(f"    issn        : P={rec.p_issn or '-'}  E={rec.e_issn or '-'}")
        print(f"    subject     : {rec.subject or '-'}")
        print(f"    accred      : {rec.accreditation or '-'}")
        print(f"    impact      : {rec.impact if rec.impact is not None else '-'}")
        print(f"    h5 / cit5yr : {rec.h5_index if rec.h5_index is not None else '-'} / "
              f"{rec.citations_5yr if rec.citations_5yr is not None else '-'}")
        print(f"    profile     : {rec.profile_url or '-'}")
        print(f"    garuda      : {rec.garuda_url or '-'}")


def _print_articles(articles: List[SintaArticle]) -> None:
    for i, rec in enumerate(articles, 1):
        print(f"[{i}] {rec.title}")
        print(f"    venue    : {rec.venue or '-'}")
        print(f"    year     : {rec.year if rec.year is not None else '-'}")
        print(f"    cited    : {rec.citations if rec.citations is not None else '-'}")
        print(f"    quartile : {rec.quartile or '-'}")
        print(f"    order    : {rec.author_order or '-'}")
        print(f"    url      : {rec.url or '-'}")


def main(argv: List[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "journals"

    if mode == "author":
        author_id = argv[2] if len(argv) > 2 else "6009908"
        articles = parse_author_articles(fetch_author(author_id))
        print(f"mode=author id={author_id} articles={len(articles)}")
        print("-" * 78)
        _print_articles(articles)
        return 0

    query = argv[2] if len(argv) > 2 else "information systems"
    page = int(argv[3]) if len(argv) > 3 else 1
    html = fetch_journals(query, page)
    journals = parse_journals(html)
    print(f"mode=journals query={query!r} page={page} html={len(html)}b journals={len(journals)}")
    print("-" * 78)
    _print_journals(journals)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

"""
Uji rantai jembatan Garuda -> Sinta dengan lookup per-venue (bukan uji sampel).

Kenapa versi pertama salah: ia membangun indeks dari ``/journals`` halaman 1
tanpa query -- 10 jurnal sembarang -- lalu menanyakan apakah venue Garuda
kebetulan ada di antara 10 itu. Hasil 0/10 mengukur sampel acak, bukan
jembatannya.

Versi ini melakukan apa yang akan dilakukan provider sungguhan: untuk setiap
venue Garuda, cari di Sinta dengan ``/journals?q={venue}``, lalu cocokkan ID
jurnal Garuda yang dibagikan kedua sisi.

Rantai:
    Garuda article detail  ->  /journal/view/{id}
    Garuda journal page    ->  ISSN / EISSN
    Sinta search ?q=venue  ->  kartu jurnal berisi /journal/view/{id} yang sama
    Sinta card             ->  akreditasi S1..S6
"""

from __future__ import annotations

import re
import sys
import time

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, ".proto")

from garuda_proto import UA, fetch as g_fetch, parse_page as g_parse  # noqa: E402
from sinta_proto import fetch_journals, parse_journals  # noqa: E402

GARUDA = "https://garuda.kemdiktisaintek.go.id"
JOURNAL_LINK_RE = re.compile(r"/journal/view/(\d+)")


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": UA}, timeout=25, follow_redirects=True)


def garuda_journal_page(detail_url: str) -> tuple[str | None, str | None, str | None]:
    """Dari halaman artikel -> (journal_id, p_issn, e_issn)."""
    with _client() as c:
        r = c.get(detail_url)
        r.raise_for_status()
        m = JOURNAL_LINK_RE.search(r.text)
        if not m:
            return None, None, None
        jid = m.group(1)

        jr = c.get(f"{GARUDA}/journal/view/{jid}")
        jr.raise_for_status()

    soup = BeautifulSoup(jr.text, "lxml")
    p_issn = e_issn = None
    for block in soup.select("div.j-meta-pub"):
        text = re.sub(r"\s+", " ", block.get_text(" ", strip=True))
        m = re.search(r"\bISSN\s*:\s*([0-9Xx-]+)", text)
        if m and m.group(1).strip(" -"):
            p_issn = m.group(1).strip()
        m = re.search(r"\bEISSN\s*:\s*([0-9Xx-]+)", text)
        if m and m.group(1).strip(" -"):
            e_issn = m.group(1).strip()
    return jid, p_issn, e_issn


def sinta_lookup_by_garuda_id(venue: str) -> dict[str, object]:
    """Query Sinta pakai nama venue; kembalikan peta garuda-id -> kartu jurnal."""
    html = fetch_journals(venue, 1)
    found: dict[str, object] = {}
    for j in parse_journals(html):
        if j.garuda_url and (m := JOURNAL_LINK_RE.search(j.garuda_url)):
            found[m.group(1)] = j
    return found


def main() -> int:
    g_records = g_parse(g_fetch("machine learning", 1))
    print(f"garuda records = {len(g_records)}")
    print("-" * 78)

    seen_venues: set[str] = set()
    id_hits = issn_hits = 0
    unique_articles = 0

    for rec in g_records:
        if not rec.detail_url:
            continue
        unique_articles += 1
        jid, p_issn, e_issn = garuda_journal_page(rec.detail_url)

        if not jid:
            print(f"NO-JOURNAL-LINK  venue={rec.venue!r}")
            continue

        # Lookup Sinta sekali per venue (bukan per artikel).
        if rec.venue not in seen_venues:
            seen_venues.add(rec.venue)
            by_id = sinta_lookup_by_garuda_id(rec.venue)
            time.sleep(0.4)
        else:
            by_id = sinta_lookup_by_garuda_id(rec.venue)

        match = by_id.get(jid)
        if match:
            id_hits += 1

        # Cek juga apakah ISSN Garuda muncul di kartu Sinta mana pun dari hasil.
        sinta_html = fetch_journals(rec.venue, 1)
        time.sleep(0.4)
        by_issn = None
        for j in parse_journals(sinta_html):
            for candidate in (p_issn, e_issn):
                if candidate and candidate in {j.p_issn, j.e_issn}:
                    by_issn = j
        if by_issn:
            issn_hits += 1

        print(f"venue={rec.venue!r}")
        print(f"   garuda_id={jid}  issn={p_issn or '-'}/{e_issn or '-'}")
        print(f"   sinta cards w/ garuda-id in result : {list(by_id)}")
        print(f"   via garuda-id : {getattr(match, 'title', '-')} [{getattr(match, 'accreditation', '-')}]")
        print(f"   via issn      : {getattr(by_issn, 'title', '-')} [{getattr(by_issn, 'accreditation', '-')}]")

    print("-" * 78)
    print(f"articles      = {unique_articles}")
    print(f"unique venues = {len(seen_venues)}")
    print(f"matched by garuda-id = {id_hits}/{unique_articles}")
    print(f"matched by issn      = {issn_hits}/{unique_articles}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

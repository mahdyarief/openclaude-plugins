"""
Jelaskan 4 venue yang gagal cocok di check_bridge.py.

Pertanyaan: apakah jurnalnya benar-benar tidak ada di Sinta (bukan terdaftar
/ tidak diakreditasi), atau hanya query recall yang kurang karena nama venue
Garuda terlalu panjang / tidak persis?

Untuk setiap miss, coba beberapa varian query: nama penuh, potongan nama,
dan ISSNnya sendiri.
"""

from __future__ import annotations

import re
import sys
import time

sys.path.insert(0, ".proto")

from sinta_proto import fetch_journals, parse_journals  # noqa: E402

MISSES = [
    # (garuda_id, garuda_issn_p, garuda_issn_e, venue, deskripsi)
    ("47045", None, "30464900", "Journal of Information Technology, computer science and Electrical Engineering"),
    ("7116", None, "23563974", "Journal of Software Engineering"),
    ("11166", "24434167", "24605263", "Jurnal Elektro dan Mesin Terapan"),
    ("151", "20894872", "22528938", "IAES International Journal of Artificial Intelligence (IJ-AI)"),
]


def probe(label: str, query: str) -> None:
    try:
        html = fetch_journals(query, 1)
    except Exception as exc:  # noqa: BLE001
        print(f"    {label:22} q={query!r:60} ERROR {exc}")
        return
    journals = parse_journals(html)
    titles = [j.title[:58] for j in journals[:3]]
    print(f"    {label:22} q={query!r:60} n={len(journals)} {titles}")


def main() -> int:
    for gid, p_issn, e_issn, venue in MISSES:
        print(f"[garuda_id={gid}] {venue[:70]}")
        # Varian query: penuh, kata kunci inti, ISSN.
        short = re.sub(r"\s*\(.*?\)\s*", " ", venue).strip()
        words = short.split()
        variants = [
            ("full", venue),
            ("words[0:3]", " ".join(words[:3])),
            ("words[0:2]", " ".join(words[:2])),
        ]
        for issn in (e_issn, p_issn):
            if issn:
                variants.append((f"issn {issn}", issn))
        for label, q in variants:
            probe(label, q)
            time.sleep(0.4)
        print()

    # Cek langsung apakah ISSN muncul di profil pencarian kosong besar.
    print("== Apakah ISSN muncul kalau dicari sebagai angka? ==")
    for gid, p_issn, e_issn, venue in MISSES:
        for issn in (e_issn, p_issn):
            if not issn:
                continue
            html = fetch_journals(issn, 1)
            journals = parse_journals(html)
            hit = [j.title for j in journals if issn in (j.p_issn or "", j.e_issn or "")]
            print(f"  issn={issn} garuda_id={gid} -> n={len(journals)} exact_issn_hit={hit}")
            time.sleep(0.4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

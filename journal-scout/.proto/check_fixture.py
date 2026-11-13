"""Offline check of the Garuda parser against the saved fixture."""

import sys

sys.path.insert(0, ".proto")

from garuda_proto import parse_page  # noqa: E402

with open(".proto/garuda.html", encoding="utf-8", errors="replace") as handle:
    html = handle.read()

records = parse_page(html)
print("records:", len(records))
print("-" * 78)

for index, rec in enumerate(records, 1):
    authors = ", ".join(rec.authors) or "-"
    print(f"[{index}] {rec.title[:100]}")
    print(f"    authors  : {authors}")
    print(f"    venue    : {rec.venue or '-'}")
    print(f"    year/vol : {rec.year or '-'} / {rec.volume or '-'} / no {rec.issue or '-'}")
    print(f"    publisher: {rec.publisher or '-'}")
    print(f"    doi      : {rec.doi or '-'}")
    print(f"    detail   : {rec.detail_url or '-'}")
    print(f"    source   : {rec.source_url or '-'}")

"""Ukur tiga cacat parser Garuda pada fixture yang tersimpan."""

import sys

sys.path.insert(0, ".proto")

from garuda_proto import parse_page  # noqa: E402

with open(".proto/garuda.html", encoding="utf-8") as handle:
    html = handle.read()

records = parse_page(html)

print("== 1. Author names with dangling hyphen ==")
for rec in records:
    bad = [a for a in rec.authors if a.endswith(" -")]
    if bad:
        print(f"  {rec.title[:50]!r}")
        print(f"    authors: {rec.authors}")

print()
print("== 2. Venue strings with leftover separators ==")
for rec in records:
    v = rec.venue or ""
    if " : " in v or v.endswith(" ,") or " , :" in v:
        print(f"  {v!r}")

print()
print("== 3. Year missing but a year appears in the raw venue ==")
for rec in records:
    if rec.year is None and rec.venue and any(ch.isdigit() for ch in rec.venue):
        print(f"  year=None venue={rec.venue!r}")

print()
print("== 4. Titles still carrying trailing whitespace / newlines ==")
for rec in records:
    if rec.title != rec.title.strip():
        print(f"  {rec.title!r}")

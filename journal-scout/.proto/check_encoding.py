"""Buktikan encoding Garuda benar dan lihat di mana mojibake muncul."""

import sys

sys.path.insert(0, ".proto")

with open(".proto/garuda.html", encoding="utf-8") as handle:
    html = handle.read()

i = html.find("Platform")
snippet = html[i : i + 40]
print("python repr :", ascii(snippet))
print("codepoints  :", [hex(ord(c)) for c in snippet[:24]])

has_replacement = "\ufffd" in html
print("U+FFFD in file:", has_replacement)

# Where does the replacement char come from?
positions = [n for n, c in enumerate(html) if c == "\ufffd"]
print("count of U+FFFD:", len(positions))
if positions:
    first = positions[0]
    print("context:", ascii(html[max(0, first - 60) : first + 20]))

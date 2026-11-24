"""Uji alur penuh slr.py di folder sementara. Jalankan: python -m unittest discover slr-assist/tests"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SLR = ROOT.parent / "skills" / "slr-assist" / "scripts" / "slr.py"
CONTOH = ROOT / "contoh"


def run(*args, ok=True):
    p = subprocess.run([sys.executable, str(SLR), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    if ok and p.returncode != 0:
        raise AssertionError(p.stdout + p.stderr)
    if not ok:
        assert p.returncode == 1, p.stdout
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return p.stdout


class AlurPenuh(unittest.TestCase):
    def test_alur(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "p"
            run("init", d, "--judul", "Uji")
            prot = d / "protokol.md"
            prot.write_text(re.sub(r"Status: draf.*", "Status: dikunci 2026-11-24", prot.read_text(encoding="utf-8")),
                            encoding="utf-8")
            run("log-cari", d, "--sumber", "Scopus", "--string", "q", "--hasil", 3)
            run("log-cari", d, "--sumber", "IEEE", "--string", "q", "--hasil", 2)
            run("log-cari", d, "--sumber", "Sitasi", "--jenis", "lain", "--string", "snowball", "--hasil", 1)
            self.assertEqual(run("impor", d, CONTOH / "scopus.ris", "--sumber", "Scopus")["ditambah"], 3)
            self.assertEqual(run("impor", d, CONTOH / "ieee.bib", "--sumber", "IEEE")["duplikat_baru"], 1)
            run("impor", d, CONTOH / "garuda.csv", "--sumber", "Sitasi")

            run("putus", d, "--id", "R0003", "--tahap", "ta", "--keputusan", "exclude",
                "--kode", "E9", "--alasan", "x", ok=False)
            run("putus", d, "--id", "R0004", "--tahap", "ta", "--keputusan", "include", "--alasan", "x", ok=False)
            batch = Path(tmp) / "b.json"
            batch.write_text(json.dumps([
                {"id": "R0001", "keputusan": "include", "alasan": "a"},
                {"id": "R0002", "keputusan": "unclear", "alasan": "b"},
                {"id": "R0003", "keputusan": "exclude", "kode": "E2", "alasan": "c"},
                {"id": "R0005", "keputusan": "include", "alasan": "d"},
                {"id": "R0006", "keputusan": "include", "alasan": "e"},
            ]), encoding="utf-8")
            run("putus", d, "--tahap", "ta", "--batch", batch)
            for i, s in [("R0001", "didapat"), ("R0002", "didapat"), ("R0005", "tidak_didapat"), ("R0006", "didapat")]:
                run("putus", d, "--id", i, "--tahap", "ambil", "--keputusan", s)
            run("putus", d, "--id", "R0001", "--tahap", "ft", "--keputusan", "include", "--alasan", "ok")
            run("putus", d, "--id", "R0002", "--tahap", "ft", "--keputusan", "exclude", "--kode", "E4", "--alasan", "ed")
            run("putus", d, "--id", "R0006", "--tahap", "ft", "--keputusan", "include", "--alasan", "ok")
            self.assertEqual(run("sahkan", d, "--oleh", "T", "--semua")["disahkan"], 5)
            self.assertEqual(run("nilai", d, "--id", "R0001", "--skor", "C1=ya,C2=sebagian,C3=0")["total"], "1.5")
            run("nilai", d, "--id", "R0002", "--skor", "C1=ya", ok=False)

            p = run("rekap", d, "--format", "json")["prisma"]
            self.assertEqual(
                (p["identified_db"], p["identified_other"], p["removed_duplicates"], p["screened"],
                 p["excluded_ta"], p["sought"], p["not_retrieved"], p["assessed"], p["excluded_ft"],
                 p["included_studies"]),
                (5, 1, 1, 5, 1, 4, 1, 3, 1, 2))
            self.assertEqual(run("status", d)["tahap"], "2d-uji-kualitas")
            bib = run("ekspor", d, "--format", "bib")
            self.assertIn("doi = {10.1000/abc.1}", bib)
            self.assertNotIn("url", bib)
            self.assertEqual(len(run("tools")["tools"]), 12)


if __name__ == "__main__":
    unittest.main()

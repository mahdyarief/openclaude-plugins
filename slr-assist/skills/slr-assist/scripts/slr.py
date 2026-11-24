#!/usr/bin/env python3
"""slr-assist tools: SLR (Kitchenham + PRISMA 2020) tanpa server.

Setiap subperintah adalah satu "tool": menerima argumen, menulis ke file proyek,
dan mencetak JSON ke stdout. State hidup di file (CSV/Markdown) dalam folder
proyek, jadi bisa dilacak git dan tidak hilang saat sesi berakhir.

  python slr.py tools                 daftar tool + skema (mirip MCP tools/list)
  python slr.py <tool> <folder> ...   jalankan satu tool

Hanya pustaka standar Python 3.8+.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from collections import Counter, OrderedDict
from datetime import date
from pathlib import Path

VERSI = "1.0.0"
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

KOLOM = {
    "log-pencarian.csv": ["sumber", "jenis", "platform", "tanggal", "string", "filter", "hasil", "catatan"],
    "rekaman.csv": [
        "id", "sumber", "judul", "penulis", "tahun", "venue", "doi", "abstrak",
        "pra_saring", "duplikat_dari",
        "ta_keputusan", "ta_kode", "ta_alasan",
        "ft_status", "ft_keputusan", "ft_kode", "ft_alasan",
        "studi_id", "disahkan",
    ],
    "kualitas.csv": ["id", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "total", "kuartil", "catatan", "disahkan"],
    "ekstraksi.csv": [
        "id", "penulis_tahun", "judul", "negara", "konteks", "metode", "data_sampel",
        "temuan_utama", "RQ1", "RQ2", "keterbatasan", "halaman_bukti",
    ],
}

SKOR = {"ya": 1.0, "y": 1.0, "1": 1.0, "sebagian": 0.5, "p": 0.5, "0.5": 0.5, "0,5": 0.5,
        "tidak": 0.0, "t": 0.0, "n": 0.0, "0": 0.0}


class Galat(Exception):
    pass


# ---------------------------------------------------------------- berkas

def baca(folder: Path, nama: str) -> list[dict]:
    p = folder / nama
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "") for k, v in r.items() if k is not None}
                for r in csv.DictReader(f)]


def tulis(folder: Path, nama: str, rows: list[dict]) -> None:
    kol = list(KOLOM.get(nama, []))
    for r in rows:
        for k in r:
            if k not in kol:
                kol.append(k)
    p = folder / nama
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=kol, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in kol})
    tmp.replace(p)


def pastikan_proyek(folder: Path) -> None:
    if not (folder / "rekaman.csv").exists():
        raise Galat(f"{folder} belum diinisialisasi. Jalankan: slr.py init {folder}")


def norm(s: str) -> str:
    return (s or "").strip().lower()


def norm_doi(s: str) -> str:
    s = norm(s)
    s = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", s)
    return s.strip().rstrip(".")


def norm_judul(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", norm(s))


def kode_protokol(folder: Path) -> set[str]:
    p = folder / "protokol.md"
    if not p.exists():
        return set()
    return set(re.findall(r"^\|\s*(E\d+)\s*\|", p.read_text(encoding="utf-8"), flags=re.M))


def cari(rows: list[dict], rid: str) -> dict:
    for r in rows:
        if r.get("id") == rid:
            return r
    raise Galat(f"id tidak ditemukan: {rid}")


# ---------------------------------------------------------------- parser impor

def parse_ris(teks: str) -> list[dict]:
    out, cur = [], {}
    for baris in teks.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])  -\s?(.*)$", baris)
        if not m:
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "ER":
            if cur:
                out.append(cur)
            cur = {}
            continue
        if tag in ("TI", "T1") and not cur.get("judul"):
            cur["judul"] = val
        elif tag in ("AU", "A1"):
            cur["penulis"] = (cur.get("penulis", "") + "; " + val).strip("; ")
        elif tag in ("PY", "Y1", "DA") and not cur.get("tahun"):
            t = re.search(r"\d{4}", val)
            cur["tahun"] = t.group(0) if t else ""
        elif tag in ("T2", "JO", "JF", "J2", "BT") and not cur.get("venue"):
            cur["venue"] = val
        elif tag == "DO":
            cur["doi"] = val
        elif tag in ("AB", "N2") and not cur.get("abstrak"):
            cur["abstrak"] = val
    if cur:
        out.append(cur)
    return out


def parse_bib(teks: str) -> list[dict]:
    out = []
    i = 0
    while True:
        m = re.compile(r"@(\w+)\s*\{", re.S).search(teks, i)
        if not m:
            break
        j, depth = m.end(), 1
        while j < len(teks) and depth:
            depth += {"{": 1, "}": -1}.get(teks[j], 0)
            j += 1
        isi = teks[m.end():j - 1]
        i = j
        if m.group(1).lower() in ("comment", "preamble", "string"):
            continue
        f = {}
        k = isi.find(",") + 1
        while k < len(isi):
            mm = re.compile(r"\s*([\w-]+)\s*=\s*", re.S).match(isi, k)
            if not mm:
                break
            key, k = mm.group(1).lower(), mm.end()
            if k < len(isi) and isi[k] == "{":
                d, s = 1, k + 1
                k += 1
                while k < len(isi) and d:
                    d += {"{": 1, "}": -1}.get(isi[k], 0)
                    k += 1
                val = isi[s:k - 1]
            elif k < len(isi) and isi[k] == '"':
                e = isi.find('"', k + 1)
                val, k = isi[k + 1:e], e + 1
            else:
                mm2 = re.compile(r"[^,]*").match(isi, k)
                val, k = mm2.group(0), mm2.end()
            f[key] = re.sub(r"\s+", " ", val.replace("{", "").replace("}", "")).strip()
            k = isi.find(",", k)
            k = len(isi) if k < 0 else k + 1
        out.append({
            "judul": f.get("title", ""),
            "penulis": f.get("author", "").replace(" and ", "; "),
            "tahun": (re.search(r"\d{4}", f.get("year", "")) or [""])[0] if f.get("year") else "",
            "venue": f.get("journal") or f.get("booktitle") or f.get("publisher", ""),
            "doi": f.get("doi", ""),
            "abstrak": f.get("abstract", ""),
        })
    return out


PETA_CSV = {
    "judul": ["title", "judul", "article title", "document title"],
    "penulis": ["authors", "author", "penulis", "author full names"],
    "tahun": ["year", "tahun", "publication year", "publication_year", "py"],
    "venue": ["source title", "venue", "journal", "publication title", "source", "jurnal"],
    "doi": ["doi"],
    "abstrak": ["abstract", "abstrak"],
}


def parse_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        low = {norm(k): (v or "").strip() for k, v in r.items() if k}
        out.append({tujuan: next((low[c] for c in calon if low.get(c)), "")
                    for tujuan, calon in PETA_CSV.items()})
    return out


def parse_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("papers") or data.get("results") or data.get("records") or []
    out = []
    for p in data:
        au = p.get("authors") or p.get("penulis") or ""
        if isinstance(au, list):
            au = "; ".join(a if isinstance(a, str) else a.get("name", "") for a in au)
        out.append({
            "judul": p.get("title") or p.get("judul") or "",
            "penulis": au,
            "tahun": str(p.get("year") or p.get("tahun") or ""),
            "venue": p.get("venue") or p.get("journal") or "",
            "doi": p.get("doi") or "",
            "abstrak": p.get("abstract") or p.get("abstrak") or "",
        })
    return out


def baca_ekspor(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext in (".ris", ".nbib", ".txt"):
        return parse_ris(path.read_text(encoding="utf-8-sig", errors="replace"))
    if ext == ".bib":
        return parse_bib(path.read_text(encoding="utf-8-sig", errors="replace"))
    if ext == ".csv":
        return parse_csv(path)
    if ext == ".json":
        return parse_json(path)
    raise Galat(f"format tidak dikenal: {ext} (pakai .ris, .bib, .csv, .json)")


# ---------------------------------------------------------------- tools

def t_init(a) -> dict:
    folder = Path(a.folder)
    folder.mkdir(parents=True, exist_ok=True)
    dibuat, ada = [], []
    for nama in ["protokol.md", *KOLOM]:
        tujuan = folder / nama
        if tujuan.exists():
            ada.append(nama)
            continue
        shutil.copyfile(TEMPLATES / nama, tujuan)
        dibuat.append(nama)
    if a.judul and "protokol.md" in dibuat:
        p = folder / "protokol.md"
        p.write_text(p.read_text(encoding="utf-8").replace("<judul singkat>", a.judul, 1), encoding="utf-8")
    return {"folder": str(folder), "dibuat": dibuat, "sudah_ada": ada,
            "lanjut": "Isi protokol.md (perencanaan), lalu kunci sebelum pencarian."}


def t_log_cari(a) -> dict:
    folder = Path(a.folder)
    pastikan_proyek(folder)
    rows = baca(folder, "log-pencarian.csv")
    baru = {"sumber": a.sumber, "jenis": a.jenis, "platform": a.platform or a.sumber,
            "tanggal": a.tanggal or date.today().isoformat(), "string": a.string,
            "filter": a.filter or "", "hasil": str(a.hasil), "catatan": a.catatan or ""}
    rows.append(baru)
    tulis(folder, "log-pencarian.csv", rows)
    return {"ditambah": baru, "jumlah_log": len(rows)}


def _dedup(rows: list[dict]) -> int:
    lihat_doi, lihat_judul, n = {}, {}, 0
    for r in rows:
        if r.get("pra_saring") and r.get("pra_saring") != "duplikat":
            continue
        d, t = norm_doi(r.get("doi", "")), norm_judul(r.get("judul", ""))
        kunci_t = (t, r.get("tahun", "")) if len(t) >= 20 else None
        asal = (lihat_doi.get(d) if d else None) or (lihat_judul.get(kunci_t) if kunci_t else None)
        if asal and asal != r["id"]:
            if r.get("duplikat_dari") != asal:
                n += 1
            r["pra_saring"], r["duplikat_dari"] = "duplikat", asal
            continue
        if r.get("pra_saring") == "duplikat":
            r["pra_saring"], r["duplikat_dari"] = "", ""
        if d:
            lihat_doi.setdefault(d, r["id"])
        if kunci_t:
            lihat_judul.setdefault(kunci_t, r["id"])
    return n


def t_impor(a) -> dict:
    folder = Path(a.folder)
    pastikan_proyek(folder)
    recs = baca_ekspor(Path(a.berkas))
    rows = baca(folder, "rekaman.csv")
    nomor = max([int(m.group(1)) for r in rows if (m := re.match(r"R(\d+)$", r.get("id", "")))] or [0])
    for rec in recs:
        if not rec.get("judul"):
            continue
        nomor += 1
        rows.append({**rec, "id": f"R{nomor:04d}", "sumber": a.sumber})
    ditambah = sum(1 for rec in recs if rec.get("judul"))
    dup = _dedup(rows) if not a.tanpa_dedup else 0
    tulis(folder, "rekaman.csv", rows)
    log = {r["sumber"]: r.get("hasil") for r in baca(folder, "log-pencarian.csv")}
    hasil = {"sumber": a.sumber, "ditambah": ditambah, "duplikat_baru": dup, "total_rekaman": len(rows)}
    if a.sumber not in log:
        hasil["peringatan"] = f"Belum ada baris log-pencarian untuk '{a.sumber}'. Jalankan log-cari."
    return hasil


def t_dedup(a) -> dict:
    folder = Path(a.folder)
    pastikan_proyek(folder)
    rows = baca(folder, "rekaman.csv")
    n = _dedup(rows)
    tulis(folder, "rekaman.csv", rows)
    return {"duplikat_baru": n, "total_duplikat": sum(1 for r in rows if r.get("pra_saring") == "duplikat")}


def _aktif(r: dict) -> bool:
    return not r.get("pra_saring") and not r.get("duplikat_dari")


def _antre(rows: list[dict], tahap: str, folder: Path) -> list[dict]:
    if tahap == "ta":
        return [r for r in rows if _aktif(r) and not r.get("ta_keputusan")]
    lolos = [r for r in rows if _aktif(r) and norm(r.get("ta_keputusan")) in ("include", "unclear")]
    if tahap == "ambil":
        return [r for r in lolos if not r.get("ft_status")]
    if tahap == "ft":
        return [r for r in lolos if norm(r.get("ft_status")) == "didapat" and not r.get("ft_keputusan")]
    final = [r for r in rows if norm(r.get("ft_keputusan")) == "include"]
    if tahap == "kualitas":
        sudah = {r["id"] for r in baca(folder, "kualitas.csv")}
        return [r for r in final if r["id"] not in sudah]
    if tahap == "ekstraksi":
        sudah = {r["id"] for r in baca(folder, "ekstraksi.csv")}
        return [r for r in final if r["id"] not in sudah]
    if tahap == "sahkan":
        return [r for r in rows if r.get("ta_keputusan") and not r.get("disahkan")]
    raise Galat(f"tahap tidak dikenal: {tahap}")


def t_antrian(a) -> dict:
    folder = Path(a.folder)
    pastikan_proyek(folder)
    rows = baca(folder, "rekaman.csv")
    q = _antre(rows, a.tahap, folder)
    kol = ["id", "judul", "tahun", "venue", "doi"]
    if a.tahap == "ta":
        kol.append("abstrak")
    if a.tahap in ("ft", "sahkan"):
        kol += ["ta_keputusan", "ta_kode", "ta_alasan", "ft_keputusan", "ft_kode", "ft_alasan"]
    return {"tahap": a.tahap, "sisa": len(q),
            "rekaman": [{k: r.get(k, "") for k in kol} for r in q[a.mulai:a.mulai + a.batas]]}


def _putus_satu(rows: list[dict], d: dict, kode_ok: set[str]) -> dict:
    r = cari(rows, d["id"])
    tahap, kep = d["tahap"], norm(d["keputusan"])
    if not _aktif(r):
        raise Galat(f"{d['id']} sudah dihapus sebelum penyaringan ({r.get('pra_saring')}).")
    if tahap == "ta":
        if kep not in ("include", "exclude", "unclear"):
            raise Galat("keputusan ta: include | exclude | unclear")
        pre = "ta_"
    elif tahap == "ambil":
        if kep not in ("didapat", "tidak_didapat"):
            raise Galat("keputusan ambil: didapat | tidak_didapat")
        if norm(r.get("ta_keputusan")) not in ("include", "unclear"):
            raise Galat(f"{d['id']} tidak lolos judul/abstrak.")
        r["ft_status"] = kep
        r["disahkan"] = ""
        return {"id": r["id"], "ft_status": kep}
    elif tahap == "ft":
        if kep not in ("include", "exclude"):
            raise Galat("keputusan ft: include | exclude")
        if norm(r.get("ft_status")) != "didapat":
            raise Galat(f"{d['id']}: full-text belum ditandai 'didapat'.")
        pre = "ft_"
    else:
        raise Galat("tahap: ta | ambil | ft")
    kode = (d.get("kode") or "").strip()
    if kep == "exclude":
        if not kode:
            raise Galat(f"{d['id']}: exclude wajib memakai kode eksklusi.")
        if kode_ok and kode not in kode_ok:
            raise Galat(f"{d['id']}: kode {kode} tidak ada di protokol ({', '.join(sorted(kode_ok))}).")
    if not (d.get("alasan") or "").strip():
        raise Galat(f"{d['id']}: alasan wajib diisi.")
    r[pre + "keputusan"], r[pre + "kode"], r[pre + "alasan"] = kep, kode, d["alasan"].strip()
    r["disahkan"] = ""
    return {"id": r["id"], "tahap": tahap, "keputusan": kep, "kode": kode}


def t_putus(a) -> dict:
    folder = Path(a.folder)
    pastikan_proyek(folder)
    rows = baca(folder, "rekaman.csv")
    kode_ok = kode_protokol(folder)
    if a.batch:
        daftar = json.loads(Path(a.batch).read_text(encoding="utf-8"))
    else:
        if not (a.id and a.tahap and a.keputusan):
            raise Galat("butuh --id, --tahap, --keputusan (atau --batch file.json)")
        daftar = [{"id": a.id, "tahap": a.tahap, "keputusan": a.keputusan,
                   "kode": a.kode, "alasan": a.alasan or ("-" if a.tahap == "ambil" else "")}]
    hasil, galat = [], []
    for d in daftar:
        d.setdefault("tahap", a.tahap)
        try:
            hasil.append(_putus_satu(rows, d, kode_ok))
        except Galat as e:
            galat.append(str(e))
    if galat and not a.sebagian:
        return {"ok": False, "galat": galat, "catatan": "Tidak ada yang ditulis. Pakai --sebagian untuk menulis yang valid."}
    tulis(folder, "rekaman.csv", rows)
    return {"ok": not galat, "ditulis": len(hasil), "keputusan": hasil, "galat": galat,
            "pengingat": "Keputusan ini usulan. Sahkan setelah peneliti memeriksa (tool: sahkan)."}


def t_sahkan(a) -> dict:
    folder = Path(a.folder)
    pastikan_proyek(folder)
    rows = baca(folder, "rekaman.csv")
    ids = set(a.id or [])
    n = 0
    for r in rows:
        if r.get("disahkan") or not r.get("ta_keputusan"):
            continue
        if ids and r["id"] not in ids:
            continue
        if not ids and not a.semua:
            continue
        r["disahkan"] = f"{a.oleh} {date.today().isoformat()}"
        n += 1
    tulis(folder, "rekaman.csv", rows)
    return {"disahkan": n, "oleh": a.oleh}


def t_nilai(a) -> dict:
    folder = Path(a.folder)
    pastikan_proyek(folder)
    rek = baca(folder, "rekaman.csv")
    r0 = cari(rek, a.id)
    if norm(r0.get("ft_keputusan")) != "include":
        raise Galat(f"{a.id} belum masuk final (ft_keputusan != include).")
    rows = baca(folder, "kualitas.csv")
    row = next((r for r in rows if r.get("id") == a.id), None)
    if row is None:
        row = {"id": a.id}
        rows.append(row)
    total = 0.0
    for pasangan in a.skor.split(","):
        k, _, v = pasangan.partition("=")
        k, v = k.strip().upper(), norm(v)
        if v not in SKOR:
            raise Galat(f"skor {k}={v} tidak dikenal (ya/sebagian/tidak atau 1/0.5/0)")
        row[k] = str(SKOR[v]).rstrip("0").rstrip(".") if SKOR[v] % 1 else str(int(SKOR[v]))
    for k, v in row.items():
        if re.fullmatch(r"C\d+", k) and v != "":
            total += float(v)
    row["total"] = (f"{total:g}")
    if a.kuartil is not None:
        row["kuartil"] = a.kuartil
    if a.catatan is not None:
        row["catatan"] = a.catatan
    row["disahkan"] = ""
    tulis(folder, "kualitas.csv", rows)
    return {"id": a.id, "skor": {k: v for k, v in row.items() if re.fullmatch(r"C\d+", k)}, "total": row["total"]}


def t_ekstrak(a) -> dict:
    folder = Path(a.folder)
    pastikan_proyek(folder)
    rek = baca(folder, "rekaman.csv")
    r0 = cari(rek, a.id)
    if norm(r0.get("ft_keputusan")) != "include":
        raise Galat(f"{a.id} belum masuk final.")
    data = json.loads(Path(a.data_file).read_text(encoding="utf-8")) if a.data_file else json.loads(a.data)
    if not isinstance(data, dict):
        raise Galat("data harus objek JSON")
    rows = baca(folder, "ekstraksi.csv")
    row = next((r for r in rows if r.get("id") == a.id), None)
    if row is None:
        row = {"id": a.id, "judul": r0.get("judul", "")}
        rows.append(row)
    for k, v in data.items():
        row[k] = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    tulis(folder, "ekstraksi.csv", rows)
    kosong = [k for k in KOLOM["ekstraksi.csv"] if not row.get(k)]
    return {"id": a.id, "kolom_diisi": sorted(data), "kolom_kosong": kosong}


# ---------------------------------------------------------------- rekap / PRISMA

LABEL = {
    "id": dict(identified="Rekaman dari basis data", identified_other="Rekaman dari sumber lain",
               removed="Dihapus sebelum penyaringan", dup="Duplikat", auto="Alat otomatis",
               other="Alasan lain", screened="Rekaman disaring (judul/abstrak)",
               excluded_ta="Rekaman dikeluarkan", sought="Laporan dicari",
               not_retrieved="Laporan tidak didapat", assessed="Laporan dinilai kelayakan (full-text)",
               excluded_ft="Laporan dikeluarkan", included="Studi masuk tinjauan",
               reports="Laporan dari studi yang masuk"),
    "en": dict(identified="Records identified from databases", identified_other="Records identified from other sources",
               removed="Records removed before screening", dup="Duplicate records",
               auto="Marked ineligible by automation tools", other="Removed for other reasons",
               screened="Records screened", excluded_ta="Records excluded",
               sought="Reports sought for retrieval", not_retrieved="Reports not retrieved",
               assessed="Reports assessed for eligibility", excluded_ft="Reports excluded",
               included="Studies included in review", reports="Reports of included studies"),
}


def _lain(jenis: dict, sumber: str) -> bool:
    return jenis.get(sumber, "database") in ("lain", "other", "citation", "website")


def hitung(folder: Path) -> dict:
    log = baca(folder, "log-pencarian.csv")
    rek = baca(folder, "rekaman.csv")
    kual = baca(folder, "kualitas.csv")
    eks = baca(folder, "ekstraksi.csv")
    w: list[str] = []

    jenis = {r["sumber"]: norm(r.get("jenis")) for r in log if r.get("sumber")}
    hasil_log = Counter()
    for r in log:
        if r.get("sumber") and r.get("hasil", "").strip().isdigit():
            hasil_log[r["sumber"]] += int(r["hasil"])

    for i, n in Counter(r.get("id", "") for r in rek).items():
        if n > 1:
            w.append(f"id ganda: {i} ({n} baris)")

    urut: "OrderedDict[str, None]" = OrderedDict((r["sumber"], None) for r in log if r.get("sumber"))
    for r in rek:
        urut[r.get("sumber") or "(tanpa sumber)"] = None
    ps = {s: {"awal": 0, "lolos_ta": 0, "final": 0} for s in urut}
    c, a_ta, a_ft, th = Counter(), Counter(), Counter(), Counter()
    studi, final_ids, belum = set(), [], Counter()

    for r in rek:
        s = r.get("sumber") or "(tanpa sumber)"
        ps[s]["awal"] += 1
        c["id_lain" if _lain(jenis, s) else "id_db"] += 1
        pra = norm(r.get("pra_saring")) or ("duplikat" if r.get("duplikat_dari") else "")
        if pra:
            c[{"duplikat": "dup", "otomatis": "auto"}.get(pra, "other")] += 1
            continue
        c["screened"] += 1
        ta = norm(r.get("ta_keputusan"))
        if not ta:
            belum["ta"] += 1
            continue
        if ta == "exclude":
            c["ex_ta"] += 1
            a_ta[r.get("ta_kode") or "(tanpa kode)"] += 1
            continue
        ps[s]["lolos_ta"] += 1
        c["sought"] += 1
        fs = norm(r.get("ft_status"))
        if fs == "tidak_didapat":
            c["not_ret"] += 1
            continue
        if fs != "didapat":
            belum["ambil"] += 1
            continue
        ft = norm(r.get("ft_keputusan"))
        if not ft:
            belum["ft"] += 1
            continue
        c["assessed"] += 1
        if ft == "exclude":
            c["ex_ft"] += 1
            a_ft[r.get("ft_kode") or "(tanpa kode)"] += 1
            continue
        ps[s]["final"] += 1
        final_ids.append(r["id"])
        studi.add(r.get("studi_id") or r["id"])
        th[r.get("tahun") or "(tanpa tahun)"] += 1

    for s, n in hasil_log.items():
        if s in ps and ps[s]["awal"] != n:
            w.append(f"{s}: log mencatat {n} hasil, rekaman.csv berisi {ps[s]['awal']}.")
    for s in ps:
        if ps[s]["awal"] and s not in hasil_log:
            w.append(f"{s}: tidak ada di log-pencarian.csv (PRISMA-S butir 1-8).")
    nama = {"ta": "judul/abstrak", "ambil": "pengambilan full-text", "ft": "kelayakan full-text"}
    for k, n in belum.items():
        if n:
            w.append(f"{n} rekaman belum diputuskan di tahap {nama[k]}.")
    tak_sah = [r["id"] for r in rek if r.get("ta_keputusan") and not r.get("disahkan")]
    if tak_sah:
        w.append(f"{len(tak_sah)} keputusan belum disahkan peneliti.")
    kid = {r.get("id") for r in kual}
    eid = {r.get("id") for r in eks}
    if final_ids and (kurang := [i for i in final_ids if i not in kid]):
        w.append("Studi final tanpa uji kualitas: " + ", ".join(kurang))
    if final_ids and (kurang := [i for i in final_ids if i not in eid]):
        w.append("Studi final tanpa ekstraksi: " + ", ".join(kurang))

    skor = []
    for r in kual:
        try:
            skor.append(float(r.get("total") or ""))
        except ValueError:
            pass

    p = {
        "identified_db": c["id_db"], "identified_other": c["id_lain"],
        "identified_per_source": {s: v["awal"] for s, v in ps.items() if v["awal"] and not _lain(jenis, s)},
        "identified_other_per_source": {s: v["awal"] for s, v in ps.items() if v["awal"] and _lain(jenis, s)},
        "removed_duplicates": c["dup"], "removed_automation": c["auto"], "removed_other": c["other"],
        "screened": c["screened"], "excluded_ta": c["ex_ta"], "sought": c["sought"],
        "not_retrieved": c["not_ret"], "assessed": c["assessed"], "excluded_ft": c["ex_ft"],
        "excluded_ta_reasons": dict(a_ta.most_common()), "excluded_ft_reasons": dict(a_ft.most_common()),
        "included_studies": len(studi), "included_reports": len(final_ids),
    }
    return {
        "prisma": p, "per_sumber": ps, "per_tahun": dict(sorted(th.items(), reverse=True)),
        "kualitas": {"dinilai": len(kual), "rata_rata": round(sum(skor) / len(skor), 2) if skor else None},
        "belum": dict(belum), "peringatan": w,
    }


def mermaid(p: dict, L: dict) -> str:
    def box(nid: str, teks: str) -> str:
        return f'  {nid}["{teks.replace(chr(34), chr(39))}"]'

    src = "".join(f"<br>{s} (n = {n})" for s, n in p["identified_per_source"].items())
    ft_al = "".join(f"<br>{k} (n = {v})" for k, v in p["excluded_ft_reasons"].items())
    out = ["flowchart TD",
           box("A", f"{L['identified']} (n = {p['identified_db']}){src}"),
           box("R", f"{L['removed']}:<br>{L['dup']} (n = {p['removed_duplicates']})"
                    f"<br>{L['auto']} (n = {p['removed_automation']})<br>{L['other']} (n = {p['removed_other']})"),
           box("B", f"{L['screened']} (n = {p['screened']})"),
           box("XB", f"{L['excluded_ta']} (n = {p['excluded_ta']})"),
           box("C", f"{L['sought']} (n = {p['sought']})"),
           box("XC", f"{L['not_retrieved']} (n = {p['not_retrieved']})"),
           box("D", f"{L['assessed']} (n = {p['assessed']})"),
           box("XD", f"{L['excluded_ft']} (n = {p['excluded_ft']}){ft_al}"),
           box("E", f"{L['included']} (n = {p['included_studies']})<br>{L['reports']} (n = {p['included_reports']})"),
           "  A --> R", "  A --> B --> C --> D --> E", "  B --> XB", "  C --> XC", "  D --> XD"]
    if p["identified_other"]:
        lain = "".join(f"<br>{s} (n = {n})" for s, n in p["identified_other_per_source"].items())
        out.insert(2, box("O", f"{L['identified_other']} (n = {p['identified_other']}){lain}"))
        out.append("  O --> B")
    return "\n".join(out)


def ke_md(h: dict, bahasa: str) -> str:
    p = h["prisma"]
    o = ["## Alur PRISMA 2020", "", "```mermaid", mermaid(p, LABEL[bahasa]), "```", "",
         "## Jumlah per sumber", "", "| Sumber | Inisiasi | Lolos judul/abstrak | Final |", "|---|---:|---:|---:|"]
    tot = Counter()
    for s, v in h["per_sumber"].items():
        if any(v.values()):
            o.append(f"| {s} | {v['awal']} | {v['lolos_ta']} | {v['final']} |")
            tot.update(v)
    o += [f"| **Total** | {tot['awal']} | {tot['lolos_ta']} | {tot['final']} |", "",
          "*Inisiasi* dihitung sebelum hapus duplikat; dua kolom lain sesudahnya "
          "(duplikat mengikuti sumber rekaman yang dipertahankan).", "",
          "## Studi final per tahun", "", "| Tahun | Jumlah |", "|---|---:|"]
    o += [f"| {t} | {n} |" for t, n in h["per_tahun"].items()]
    if p["excluded_ta_reasons"] or p["excluded_ft_reasons"]:
        o += ["", "## Alasan dikeluarkan", "", "| Tahap | Kode | Jumlah |", "|---|---|---:|"]
        o += [f"| Judul/abstrak | {k} | {v} |" for k, v in p["excluded_ta_reasons"].items()]
        o += [f"| Full-text | {k} | {v} |" for k, v in p["excluded_ft_reasons"].items()]
    k = h["kualitas"]
    if k["dinilai"]:
        o += ["", "## Uji kualitas", "", f"{k['dinilai']} studi dinilai; rata-rata total {k['rata_rata']}."]
    o += ["", "## Peringatan", ""] + ([f"- {x}" for x in h["peringatan"]] or ["- Tidak ada."])
    return "\n".join(o) + "\n"


def t_rekap(a):
    folder = Path(a.folder)
    pastikan_proyek(folder)
    h = hitung(folder)
    if a.format == "md":
        teks = ke_md(h, a.bahasa)
        if a.simpan:
            (folder / "prisma.md").write_text(teks, encoding="utf-8")
        return teks
    return h


def t_status(a) -> dict:
    folder = Path(a.folder)
    pastikan_proyek(folder)
    prot = (folder / "protokol.md").read_text(encoding="utf-8") if (folder / "protokol.md").exists() else ""
    terkunci = bool(re.search(r"Status:\s*dikunci", prot))
    log = baca(folder, "log-pencarian.csv")
    rek = baca(folder, "rekaman.csv")
    h = hitung(folder)
    q = {t: len(_antre(rek, t, folder)) for t in ("ta", "ambil", "ft", "kualitas", "ekstraksi")}
    if not terkunci:
        tahap, lanjut = "1-perencanaan", "Lengkapi dan kunci protokol.md (ubah Status menjadi 'dikunci YYYY-MM-DD')."
    elif not log or not rek:
        tahap, lanjut = "2a-identifikasi", "Jalankan pencarian, catat dengan log-cari, lalu impor ekspornya."
    elif q["ta"]:
        tahap, lanjut = "2b-saring-judul-abstrak", f"{q['ta']} rekaman menunggu keputusan judul/abstrak."
    elif q["ambil"]:
        tahap, lanjut = "2c-ambil-full-text", f"{q['ambil']} laporan perlu dicari full-text-nya."
    elif q["ft"]:
        tahap, lanjut = "2c-saring-full-text", f"{q['ft']} laporan menunggu keputusan kelayakan."
    elif q["kualitas"]:
        tahap, lanjut = "2d-uji-kualitas", f"{q['kualitas']} studi final belum dinilai."
    elif q["ekstraksi"]:
        tahap, lanjut = "2e-ekstraksi", f"{q['ekstraksi']} studi final belum diekstraksi."
    elif not (folder / "sintesis.md").exists():
        tahap, lanjut = "2f-sintesis", "Tulis sintesis.md per RQ dari ekstraksi.csv."
    else:
        tahap, lanjut = "3-pelaporan", "Jalankan rekap --simpan, isi checklist PRISMA 2020, tulis laporan."
    return {"tahap": tahap, "protokol_dikunci": terkunci, "antrian": q,
            "prisma": {k: v for k, v in h["prisma"].items() if not isinstance(v, dict)},
            "peringatan": h["peringatan"], "lanjut": lanjut}


def t_ekspor(a):
    folder = Path(a.folder)
    pastikan_proyek(folder)
    rek = baca(folder, "rekaman.csv")
    if a.tahap == "final":
        pilih = [r for r in rek if norm(r.get("ft_keputusan")) == "include"]
    elif a.tahap == "ft":
        pilih = [r for r in rek if _aktif(r) and norm(r.get("ta_keputusan")) in ("include", "unclear")]
    else:
        pilih = [r for r in rek if _aktif(r)]
    out = []
    for r in pilih:
        if a.format == "bib":
            first = re.sub(r"[^a-z]", "", norm((r.get("penulis") or "anon").split(";")[0].split(",")[0])) or "anon"
            kata = next((x for x in re.findall(r"[a-z]{4,}", norm(r.get("judul")))), "x")
            f = [f"  title = {{{r.get('judul', '')}}}", f"  author = {{{(r.get('penulis') or '').replace('; ', ' and ')}}}"]
            if r.get("tahun"):
                f.append(f"  year = {{{r['tahun']}}}")
            if r.get("venue"):
                f.append(f"  journal = {{{r['venue']}}}")
            if r.get("doi"):
                f.append(f"  doi = {{{norm_doi(r['doi'])}}}")
            f.append(f"  note = {{slr-assist {r['id']}}}")
            out.append(f"@article{{{first}{r.get('tahun', '')}{kata},\n" + ",\n".join(f) + "\n}")
        else:
            lines = ["TY  - JOUR", f"TI  - {r.get('judul', '')}"]
            lines += [f"AU  - {x.strip()}" for x in (r.get("penulis") or "").split(";") if x.strip()]
            for tag, k in (("PY", "tahun"), ("T2", "venue"), ("DO", "doi"), ("AB", "abstrak")):
                if r.get(k):
                    lines.append(f"{tag}  - {r[k]}")
            lines += [f"N1  - slr-assist {r['id']}", "ER  - "]
            out.append("\n".join(lines))
    teks = "\n\n".join(out) + "\n"
    if a.keluar:
        Path(a.keluar).write_text(teks, encoding="utf-8")
        return {"ditulis": len(pilih), "berkas": a.keluar}
    return teks


# ---------------------------------------------------------------- CLI

def bangun_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="slr.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versi", action="version", version=VERSI)
    sp = ap.add_subparsers(dest="tool", metavar="<tool>")

    def tool(nama, fn, ringkas):
        p = sp.add_parser(nama, help=ringkas, description=ringkas)
        p.set_defaults(fn=fn)
        if nama != "tools":
            p.add_argument("folder", help="folder proyek SLR")
        return p

    tool("tools", None, "Daftar tool dan skema argumennya (JSON), seperti MCP tools/list.")

    p = tool("init", t_init, "Buat folder proyek dari templat (protokol.md + CSV). Tidak menimpa file yang ada.")
    p.add_argument("--judul", help="judul singkat SLR untuk protokol")

    tool("status", t_status, "Tahap proyek sekarang, antrian per tahap, angka PRISMA, peringatan, langkah berikutnya.")

    p = tool("log-cari", t_log_cari, "Catat satu pencarian basis data ke log-pencarian.csv (PRISMA-S).")
    p.add_argument("--sumber", required=True, help="nama sumber, mis. Scopus")
    p.add_argument("--string", required=True, help="search string persis seperti dijalankan")
    p.add_argument("--hasil", required=True, type=int, help="jumlah hasil yang dilaporkan basis data")
    p.add_argument("--jenis", default="database", choices=["database", "register", "lain"],
                   help="'lain' = penelusuran sitasi, situs web (kolom kanan diagram PRISMA)")
    p.add_argument("--platform", help="antarmuka, mis. Scopus.com, Ovid, EBSCOhost")
    p.add_argument("--tanggal", help="YYYY-MM-DD; bawaan hari ini")
    p.add_argument("--filter", help="batasan tahun, bahasa, jenis dokumen")
    p.add_argument("--catatan")

    p = tool("impor", t_impor, "Impor ekspor basis data (.ris/.nbib/.bib/.csv/.json) ke rekaman.csv, lalu tandai duplikat.")
    p.add_argument("berkas", help="file ekspor")
    p.add_argument("--sumber", required=True, help="harus sama dengan nama sumber di log-pencarian")
    p.add_argument("--tanpa-dedup", action="store_true")

    tool("dedup", t_dedup, "Tandai ulang duplikat: DOI sama, atau judul (>=20 huruf) + tahun sama. Rekaman pertama dipertahankan.")

    p = tool("antrian", t_antrian, "Daftar rekaman yang menunggu keputusan di satu tahap.")
    p.add_argument("--tahap", required=True, choices=["ta", "ambil", "ft", "kualitas", "ekstraksi", "sahkan"])
    p.add_argument("--batas", type=int, default=20)
    p.add_argument("--mulai", type=int, default=0)

    p = tool("putus", t_putus, "Catat keputusan penyaringan. ta: include|exclude|unclear; ambil: didapat|tidak_didapat; "
                               "ft: include|exclude. Exclude wajib kode dari protokol. Mengosongkan 'disahkan'.")
    p.add_argument("--id")
    p.add_argument("--tahap", choices=["ta", "ambil", "ft"])
    p.add_argument("--keputusan")
    p.add_argument("--kode", help="kode eksklusi, mis. E2")
    p.add_argument("--alasan")
    p.add_argument("--batch", help="file JSON: [{id, tahap, keputusan, kode, alasan}, ...]")
    p.add_argument("--sebagian", action="store_true", help="tulis yang valid meski ada yang galat")

    p = tool("sahkan", t_sahkan, "Tandai keputusan sudah diperiksa peneliti. Jalankan HANYA setelah peneliti menyetujui.")
    p.add_argument("--oleh", required=True, help="nama/inisial peneliti")
    p.add_argument("--id", action="append", help="boleh diulang; tanpa --id wajib --semua")
    p.add_argument("--semua", action="store_true")

    p = tool("nilai", t_nilai, "Simpan uji kualitas satu studi final ke kualitas.csv; total dihitung otomatis.")
    p.add_argument("--id", required=True)
    p.add_argument("--skor", required=True, help="mis. C1=ya,C2=sebagian,C3=tidak (atau 1/0.5/0)")
    p.add_argument("--kuartil", help="Q1-Q4/unindexed; dicatat terpisah, tidak masuk total")
    p.add_argument("--catatan")

    p = tool("ekstrak", t_ekstrak, "Simpan/timpa kolom ekstraksi satu studi final ke ekstraksi.csv. Kunci baru jadi kolom baru.")
    p.add_argument("--id", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--data", help='objek JSON, mis. {"metode":"survei","RQ1":"... (hlm. 5)"}')
    g.add_argument("--data-file", help="file berisi objek JSON")

    p = tool("rekap", t_rekap, "Hitung alur PRISMA 2020 (diagram Mermaid), tabel per sumber/tahun, alasan eksklusi, peringatan.")
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.add_argument("--bahasa", choices=["id", "en"], default="id")
    p.add_argument("--simpan", action="store_true", help="tulis juga ke prisma.md")

    p = tool("ekspor", t_ekspor, "Ekspor rekaman ke RIS atau BibTeX (tanpa url). tahap: final | ft | semua.")
    p.add_argument("--format", choices=["ris", "bib"], default="bib")
    p.add_argument("--tahap", choices=["final", "ft", "semua"], default="final")
    p.add_argument("--keluar", help="file tujuan; tanpa ini dicetak ke stdout")
    return ap


def daftar_tools(ap: argparse.ArgumentParser) -> list[dict]:
    sub = next(x for x in ap._actions if isinstance(x, argparse._SubParsersAction))
    out = []
    for nama, p in sub.choices.items():
        if nama == "tools":
            continue
        props, wajib = {}, []
        for act in p._actions:
            if isinstance(act, argparse._HelpAction):
                continue
            key = act.dest
            sch = {"type": "boolean" if act.nargs == 0 else ("integer" if act.type is int else "string")}
            if act.choices:
                sch["enum"] = list(act.choices)
            if act.help:
                sch["description"] = act.help
            if act.default not in (None, False, argparse.SUPPRESS):
                sch["default"] = act.default
            if isinstance(act, argparse._AppendAction):
                sch = {"type": "array", "items": {"type": "string"}, "description": act.help or ""}
            flag = act.option_strings[-1] if act.option_strings else key
            sch["flag"] = flag
            props[key] = sch
            if act.required or not act.option_strings:
                wajib.append(key)
        out.append({"name": nama, "description": p.description,
                    "inputSchema": {"type": "object", "properties": props, "required": wajib}})
    return out


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = bangun_parser()
    a = ap.parse_args(argv)
    if not a.tool:
        ap.print_help()
        return 0
    try:
        hasil = {"versi": VERSI, "tools": daftar_tools(ap)} if a.tool == "tools" else a.fn(a)
    except (Galat, json.JSONDecodeError, FileNotFoundError) as e:
        print(json.dumps({"ok": False, "galat": str(e)}, ensure_ascii=False))
        return 1
    if isinstance(hasil, str):
        print(hasil, end="")
    else:
        print(json.dumps(hasil, ensure_ascii=False, indent=2))
        if isinstance(hasil, dict) and hasil.get("ok") is False:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

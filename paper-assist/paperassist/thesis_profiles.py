"""Curated thesis/manuscript formatting profiles (model-free).

Complements :mod:`paperassist.journal_profiles` (which targets *journal*
submissions) with the space it does not cover: **thesis-style documents**
(skripsi / tesis / disertasi), including Indonesian campus guidelines.

Each entry is a deterministic, citable summary of a published guideline,
not a legal substitute for the institution's current handbook. Entries carry
an actionable ``latex_preamble`` so the formatting can be applied directly.

Sourced 2026-11-15. National-language (Indonesian) profiles are marked with
``scope="indonesia"``; the campus-agnostic baseline uses ``scope="generic"``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

THESIS_PROFILE_SCHEMA = "paperassist.thesis-profiles/v1"


@dataclass(frozen=True)
class ThesisProfile:
    profile_id: str
    name: str
    institution: str
    scope: str  # "indonesia" | "international" | "generic"
    degree_levels: tuple[str, ...]  # skripsi | tesis | disertasi
    document_class: str
    class_options: str
    body_font: str
    body_font_size_pt: float
    line_spacing: float
    margins_cm: Mapping[str, float]
    paper_size: str = "A4"
    paragraph_indent_cm: float = 1.0
    first_line_indent_cm: float | None = None
    abstract_layout: str = ""
    citation_style: str = ""
    page_numbering: str = ""
    chapter_numbering: str = ""
    front_matter: tuple[str, ...] = ()
    latex_preamble: str = ""
    common_requirements: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    match_tokens: tuple[str, ...] = ()
    match_classes: tuple[str, ...] = ()
    requires_institution_token: bool = False
    # Whole-document word range the guide sets, when it sets one.
    word_range: tuple[int, int] | None = None
    # ReferencePolicy fields the guide sets (recent_years, min_recent_share,
    # min_primary_share, min_entries); a caller's reference_policy overrides it.
    reference_policy: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

_TELKOM_PREAMBLE = r"""\documentclass[12pt,a4paper]{report}
\usepackage[T1]{fontenc}
\usepackage[indonesian]{babel}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\usepackage[a4paper,left=4cm,top=3cm,right=2.5cm,bottom=2.5cm]{geometry}
\usepackage{setspace}
\onehalfspacing
\setlength{\parindent}{1cm}
\usepackage{titlesec}
\titleformat{\chapter}[display]
  {\normalfont\large\bfseries\centering}
  {\MakeUppercase{\chaptertitlename}\ \thechapter}{2ex}{\large\MakeUppercase}
\titlespacing*{\chapter}{0pt}{0pt}{2.5ex}
\usepackage{booktabs,longtable,array}
\usepackage[hidelinks]{hyperref}
"""

PROFILES: tuple[ThesisProfile, ...] = (
    ThesisProfile(
        profile_id="id-telkom-tesis",
        name="Tesis Magister Universitas Telkom (panduan umum)",
        institution="Telkom University",
        scope="indonesia",
        degree_levels=("tesis",),
        document_class="report",
        class_options="12pt,a4paper",
        body_font="Times New Roman",
        body_font_size_pt=12,
        line_spacing=1.5,
        margins_cm={"left": 4.0, "top": 3.0, "right": 2.5, "bottom": 2.5},
        paper_size="A4",
        paragraph_indent_cm=1.0,
        abstract_layout=(
            "Abstrak ditulis dalam bahasa Indonesia dan Inggris (masing-masing "
            "maksimum 500 kata, 5 alinea, spasi tunggal, huruf miring untuk "
            "versi Inggris)."
        ),
        citation_style="APA (rujuk www.apa.org); gaya author-year",
        page_numbering=(
            "Bagian awal angka Romawi kecil (i, ii, iii, ...) tanpa nomor pada "
            "halaman judul dan persetujuan; Bab I dan seterusnya angka Arab "
            "mulai 1, menerus sampai lampiran."
        ),
        chapter_numbering="BAB I, BAB II, ... (angka Romawi besar) di halaman baru",
        front_matter=(
            "halaman judul",
            "halaman persetujuan pembimbing",
            "lembar pernyataan",
            "kata pengantar",
            "abstrak (Indonesia dan Inggris)",
            "daftar isi",
            "daftar tabel",
            "daftar gambar",
            "daftar lampiran",
        ),
        latex_preamble=_TELKOM_PREAMBLE,
        common_requirements=(
            "Isi naskah 12 pt; judul cover 18 pt bold; nama lembaga 16 pt kapital bold.",
            "Judul isi 12 pt kapital bold; subjudul 12 pt bold kapital di awal kata.",
            "Jarak baris 1,5; jarak tajuk bab ke teks 2,5 spasi; penunjuk bab ke "
            "tajuk 2 spasi; tajuk subbab ke baris pertama 1,5 spasi.",
            "Alinea menjorok 1 cm dari margin kiri; jarak antaralinea 1,5 spasi.",
            "Teks ke tabel/gambar/grafik 3 spasi; setiap tajuk di halaman baru.",
            "Kertas A4 80 gram; sampul karton Buffalo biru dongker Omega 11.",
            "Panjang naskah 40.000-100.000 kata (ketentuan MM).",
        ),
        notes=(
            "Panduan bersifat umum tingkat universitas; tiap fakultas/prodi "
            "(MTI, MSI, MEE, MSF, MM) menerbitkan pedoman dan template sendiri.",
            "LaTeX tidak diwajibkan; format resmi berbasis Word/gaya cetak. "
            "Template LaTeX yang beredar berlabel unofficial.",
            "Angka margin dan spasi di atas berasal dari Panduan Penulisan Tesis "
            "Magister Manajemen Telkom; prodi lain mengikuti pola yang sama namun "
            "wajib dikonfirmasi ke pembimbing.",
        ),
        sources=(
            "https://docplayer.info/31779740-Panduan-penulisan-tesis-magister-manajemen-universitas-telkom.html",
            "https://mis.telkomuniversity.ac.id/download/",
            "https://msf.telkomuniversity.ac.id/dokumen-mk-tesis/",
            "https://mie.telkomuniversity.ac.id (Panduan Penulisan Tesis via linktr.ee/prodimti)",
        ),
        aliases=("telkom", "telkom university", "tel-u", "telkom tesis", "mti telkom"),
        match_tokens=("universitas telkom", "telkom university", "tel-u"),
        match_classes=("report",),
        requires_institution_token=True,
    ),
    ThesisProfile(
        profile_id="id-thesis-generic",
        name="Tesis Indonesia (kerangka umum)",
        institution="(kampus-agnostik)",
        scope="indonesia",
        degree_levels=("skripsi", "tesis", "disertasi"),
        document_class="report",
        class_options="12pt,a4paper",
        body_font="Times New Roman",
        body_font_size_pt=12,
        line_spacing=1.5,
        margins_cm={"left": 4.0, "top": 3.0, "right": 2.5, "bottom": 2.5},
        paper_size="A4",
        paragraph_indent_cm=1.0,
        abstract_layout=(
            "Abstrak dua bahasa (Indonesia dan Inggris), satu halaman, spasi "
            "tunggal, maksimum sekitar 500 kata."
        ),
        citation_style="APA author-year (default)",
        page_numbering="Romawi kecil untuk bagian awal, angka Arab untuk isi.",
        chapter_numbering="BAB I, BAB II, ... di halaman baru",
        front_matter=(
            "halaman judul",
            "halaman pengesahan",
            "kata pengantar",
            "abstrak",
            "daftar isi",
            "daftar tabel",
            "daftar gambar",
        ),
        latex_preamble=_TELKOM_PREAMBLE,
        common_requirements=(
            "Gaya cetak lazim prodi Indonesia: TNR 12 pt, spasi 1,5, A4.",
            "Margin kiri lebih lebar (4 cm) untuk penjilidan.",
            "Setiap bab dimulai di halaman baru.",
        ),
        notes=(
            "Baseline ini adalah konvensi umum, bukan aturan resmi kampus mana pun. "
            "Ganti dengan profil kampus bila tersedia.",
        ),
        sources=("Konvensi umum pedoman tesis program magister Indonesia.",),
        aliases=("thesis", "tesis", "skripsi", "disertasi", "thesis indonesia"),
        match_tokens=("tesis", "skripsi", "disertasi"),
        match_classes=("report",),
    ),
    ThesisProfile(
        profile_id="intl-thesis-generic",
        name="International thesis / dissertation (generic)",
        institution="(campus-agnostic)",
        scope="generic",
        degree_levels=("master", "phd", "thesis", "dissertation"),
        document_class="report",
        class_options="12pt,a4paper",
        body_font="Times New Roman",
        body_font_size_pt=12,
        line_spacing=2.0,
        margins_cm={"left": 3.0, "top": 2.5, "right": 2.5, "bottom": 2.5},
        paper_size="A4",
        paragraph_indent_cm=1.0,
        abstract_layout="Single abstract, double-spaced, usually <= 350 words.",
        citation_style="APA 7th or institution-specific author-year",
        page_numbering="Roman numerals for front matter, Arabic for body.",
        chapter_numbering="Chapter 1, Chapter 2, ... on a new page",
        front_matter=(
            "title page",
            "declaration",
            "acknowledgements",
            "abstract",
            "table of contents",
            "list of figures",
            "list of tables",
        ),
        latex_preamble=_TELKOM_PREAMBLE,
        common_requirements=(
            "Double-spaced body text is the most common international default.",
            "Wide left margin only where binding is required.",
        ),
        notes=(
            "Institution-specific rules override this baseline; many universities "
            "publish their own .cls or Word template.",
        ),
        sources=("Common international graduate-school formatting conventions.",),
        aliases=("international thesis", "dissertation", "master thesis", "phd thesis"),
        match_tokens=("dissertation", "master thesis", "phd thesis"),
        match_classes=("report",),
    ),
)

_DOC_CLASS_RE = re.compile(r"\\documentclass\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")


def _norm(s: str) -> str:
    return " ".join(str(s or "").lower().split())


def list_thesis_profiles(scope: str | None = None) -> list[dict[str, Any]]:
    """Return profiles, optionally filtered by scope (``all``/``*`` = no filter)."""
    s = _norm(scope) if scope else ""
    items = PROFILES
    if s and s not in {"all", "*"}:
        items = tuple(p for p in PROFILES if p.scope == s)
    return [p.to_dict() for p in items]


def _haystack(p: ThesisProfile) -> str:
    return _norm(
        " ".join(
            [
                p.profile_id,
                p.name,
                p.institution,
                p.scope,
                p.document_class,
                " ".join(p.degree_levels),
                " ".join(p.aliases),
                " ".join(p.match_tokens),
            ]
        )
    )


def lookup_thesis_profiles(query: str, *, limit: int = 10) -> dict[str, Any]:
    """Lookup by id/name/alias (exact first), then scored token overlap."""
    q = _norm(query)
    if not q:
        raise ValueError("query is required")
    exact: list[ThesisProfile] = []
    scored: list[tuple[int, ThesisProfile]] = []
    tokens = [t for t in re.split(r"[^a-z0-9\-]+", q) if t]
    for p in PROFILES:
        hay = _haystack(p)
        if q == _norm(p.profile_id) or q == _norm(p.name) or q in {_norm(a) for a in p.aliases}:
            exact.append(p)
            continue
        score = sum(1 for t in tokens if t in hay)
        if q in hay:
            score += 2
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].profile_id))
    matches = exact + [p for _, p in scored[:limit]]
    return {
        "schema": THESIS_PROFILE_SCHEMA,
        "query": query,
        "exact": bool(exact),
        "count": min(len(matches), limit),
        "matches": [p.to_dict() for p in matches[:limit]],
    }


def detect_thesis_profiles(text: str, *, limit: int = 10) -> dict[str, Any]:
    """Heuristic detection from LaTeX source (documentclass + tokens)."""
    src = text or ""
    m = _DOC_CLASS_RE.search(src)
    doc_class = (m.group(1).strip() if m else "") or None
    low = src.lower()
    hits: list[tuple[int, ThesisProfile, list[str]]] = []
    for p in PROFILES:
        score = 0
        reasons: list[str] = []
        # Campus-specific profiles need their institution named in the source;
        # otherwise a bare \documentclass{report} falls back to the generic baseline.
        if p.requires_institution_token and not any(
            tok.lower() in low for tok in p.match_tokens
        ):
            continue
        if doc_class and doc_class.lower() in {c.lower() for c in p.match_classes}:
            score += 5
            reasons.append(f"documentclass={doc_class}")
        for tok in p.match_tokens:
            if tok.lower() in low:
                score += 1
                reasons.append(f"token:{tok}")
        if score > 0:
            hits.append((score, p, reasons))
    hits.sort(key=lambda x: (-x[0], x[1].profile_id))
    return {
        "schema": THESIS_PROFILE_SCHEMA,
        "documentclass": doc_class,
        "count": min(len(hits), limit),
        "matches": [
            {**p.to_dict(), "score": s, "reasons": r} for s, p, r in hits[:limit]
        ],
    }


def format_thesis_profile_report(result: Mapping[str, Any]) -> str:
    """Human-readable, copy-pasteable report incl. ready-to-use preamble."""
    lines: list[str] = []
    schema = result.get("schema", THESIS_PROFILE_SCHEMA)
    if "matches" in result and "documentclass" in result:
        lines.append(f"Thesis profile detection ({schema})")
        lines.append(f"documentclass: {result.get('documentclass') or '(not found)'}")
    elif "matches" in result:
        lines.append(f"Thesis profile lookup ({schema})")
        lines.append(f"query: {result.get('query', '')!r} exact={result.get('exact')}")
    else:
        lines.append(f"Thesis profiles ({schema})")
        lines.append(f"scope: {result.get('scope', 'all')} count={result.get('count', 0)}")
    items = result.get("matches") or result.get("profiles") or []
    if not items:
        lines.append("No profiles matched.")
        return "\n".join(lines)
    for i, p in enumerate(items, 1):
        lines.append("")
        score = f" score={p['score']} reasons={','.join(p.get('reasons') or [])}" if "score" in p else ""
        lines.append(
            f"{i}. [{p['scope']}] {p['name']} ({p['profile_id']}){score}"
        )
        lines.append(
            f"   {p['body_font']} {p['body_font_size_pt']:g} pt | "
            f"spacing {p['line_spacing']:g} | {p['paper_size']} | "
            f"margins L/T/R/B = "
            f"{p['margins_cm']['left']:g}/{p['margins_cm']['top']:g}/"
            f"{p['margins_cm']['right']:g}/{p['margins_cm']['bottom']:g} cm | "
            f"\\documentclass[{p['class_options']}]{{{p['document_class']}}}"
        )
        if p.get("abstract_layout"):
            lines.append(f"   abstract: {p['abstract_layout']}")
        if p.get("citation_style"):
            lines.append(f"   citations: {p['citation_style']}")
        if p.get("page_numbering"):
            lines.append(f"   pages: {p['page_numbering']}")
        for req in p.get("common_requirements") or ():
            lines.append(f"   - {req}")
        for note in p.get("notes") or ():
            lines.append(f"   note: {note}")
        if p.get("sources"):
            lines.append(f"   sources: {'; '.join(p['sources'])}")
        if p.get("latex_preamble"):
            lines.append("   LaTeX preamble:")
            lines.extend("   " + ln for ln in p["latex_preamble"].rstrip().splitlines())
    return "\n".join(lines)


def thesis_profile(profile_id: str = "id-thesis-generic") -> ThesisProfile:
    """Return one profile by id, raising on unknown ids."""
    for p in PROFILES:
        if p.profile_id == profile_id:
            return p
    known = ", ".join(p.profile_id for p in PROFILES)
    raise ValueError(f"unknown thesis profile {profile_id!r}; known: {known}")


def thesis_preamble(profile_id: str = "id-thesis-generic") -> str:
    """Return the ready-to-use LaTeX preamble for a profile id."""
    return thesis_profile(profile_id).latex_preamble

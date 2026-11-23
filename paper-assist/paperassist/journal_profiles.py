"""Curated journal/profile format references (Indonesia and international).

This module is model-free: it provides deterministic lookup, lightweight
heuristics, and citable references for common manuscript templates so tools
and users can choose formatting targets without guessing. Entries are
summaries, not legal substitutes for a journal's current author guidelines.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

PROFILE_SCHEMA = "paperassist.journal-profiles/v1"

@dataclass(frozen=True)
class JournalProfile:
    profile_id: str
    name: str
    publisher: str
    scope: str  # "indonesia" | "international" | "generic"
    document_class: str | None
    template_formats: tuple[str, ...] = ()
    abstract_layout: str = ""
    common_requirements: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    match_tokens: tuple[str, ...] = ()
    match_classes: tuple[str, ...] = ()
    # Declarations the quality rubric requires for this venue. Empty means the
    # generic default (competing interests, funding, data availability, AI use).
    # Always confirm against the specific journal's guide for authors.
    required_declarations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

PROFILES: tuple[JournalProfile, ...] = (
    JournalProfile(
        profile_id="latex-article-default",
        name="LaTeX article (standard class)",
        publisher="LaTeX Project",
        scope="generic",
        document_class="article",
        template_formats=("tex",),
        abstract_layout=(
            "Default abstract uses \\small text inside a quotation environment "
            "(left/right inset narrower than body text); not full \\textwidth."
        ),
        common_requirements=(
            "Single-column by default; title via \\maketitle.",
            "No journal-mandated section order beyond author content.",
        ),
        notes=(
            "This is the baseline many authors start from; journals often "
            "redefine abstract width/style in their own class or template.",
        ),
        sources=(
            "Local class definition: article.cls (LaTeX2e, e.g. v1.4n) — "
            "abstract wraps \\quotation; quotation sets \\rightmargin=\\leftmargin.",
        ),
        aliases=("article", "latex article", "standar article"),
        match_tokens=("article", "latex article"),
        match_classes=("article",),
    ),
    JournalProfile(
        profile_id="id-jtim-sekawan",
        name="JTIM - Jurnal Teknologi Informasi dan Multimedia (Sekawan Institute)",
        publisher="Sekawan Institute / Politeknik Negeri Banyuwangi (journal host)",
        scope="indonesia",
        document_class=None,
        template_formats=("docx", "tex", "overleaf"),
        abstract_layout=(
            "Template-driven (Word/LaTeX); bilingual abstract (Indonesian and "
            "English) as specified by current author guidelines/template."
        ),
        common_requirements=(
            "Provides official templates: Indonesian/English in Word and LaTeX.",
            "IMRAD-style structure (Introduction, Methodology, Results and Discussion, "
            "Conclusion) per author guidelines.",
            "Abstract guidance: typically 150–250 words per language with keywords "
            "(verify current template).",
            "A4 layout and specific typography/margins defined by template.",
        ),
        notes=(
            "Accredited Indonesian journal (SINTA-listed; check current rank on "
            "SINTA/journal site). Always follow the latest template on the journal site.",
        ),
        sources=(
            "https://journal.sekawan-org.id/index.php/jtim/en/aguid/index",
        ),
        aliases=("jtim", "jurnal teknologi informasi dan multimedia", "sekawan jtim"),
        match_tokens=("jtim", "sekawan", "teknologi informasi dan multimedia"),
        match_classes=(),
    ),
    JournalProfile(
        profile_id="id-sinta-generic",
        name="Jurnal ilmiah Indonesia terindeks SINTA (pedoman umum, non-tunggal)",
        publisher="Beragam pengelola jurnal (universitas/asosiasi)",
        scope="indonesia",
        document_class=None,
        template_formats=("docx", "tex", "odt"),
        abstract_layout=(
            "Tidak seragam nasional: setiap jurnal menentukan lebar/gaya abstrak "
            "di template masing-masing (Word/LaTeX). Banyak yang meminta abstrak "
            "Indonesia dan/atau Inggris."
        ),
        common_requirements=(
            "Umum: judul, identitas/afiliasi penulis, abstrak + kata kunci, "
            "pendahuluan/metode/hasil-pembahasan/kesimpulan, daftar pustaka.",
            "Gaya sitasi dan batasan panjang sangat bervariasi antar jurnal.",
            "Gunakan template resmi jurnal tujuan; SINTA adalah indeks, bukan "
            "satu format tata letak tunggal.",
        ),
        notes=(
            "Untuk kepatuhan format, rujuk laman 'Author Guidelines' jurnal target "
            "dan peringkat/metadata di https://sinta.kemdiktisaintek.go.id/journals.",
        ),
        sources=(
            "https://sinta.kemdiktisaintek.go.id/journals",
            "https://jurnalsinta.id/index.php/sinta/author_guidelines",
        ),
        aliases=("sinta", "jurnal sinta", "jurnal indonesia"),
        match_tokens=("sinta", "jurnal indonesia", "indonesian journal"),
        match_classes=(),
    ),
    JournalProfile(
        profile_id="intl-elsevier-elsarticle",
        name="Elsevier (elsarticle class)",
        publisher="Elsevier",
        scope="international",
        document_class="elsarticle",
        template_formats=("tex",),
        abstract_layout=(
            "Abstract via \\begin{abstract}...\\end{abstract}; visual width/placement "
            "depends on class options (preprint, review, 1p/3p/5p, one/two column). "
            "Do not assume it matches plain article's quotation inset."
        ),
        common_requirements=(
            "Common options include preprint/review/final and layout 1p,3p,5p; "
            "numbered or authoryear citations via natbib options/bibliography style.",
            "Journal-specific requirements (sections, highlights, keywords, "
            "declarations) vary by target Elsevier journal.",
        ),
        notes=(
            "Select the exact target journal on Elsevier's guide for authors; "
            "elsarticle provides the base class, not every journal's front-matter rules.",
        ),
        required_declarations=("competing_interests", "funding", "data_availability", "ai_use"),
        sources=(
            "https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions",
            "CTAN: https://ctan.org/pkg/elsarticle",
        ),
        aliases=("elsevier", "elsarticle"),
        match_tokens=("elsevier", "elsarticle"),
        match_classes=("elsarticle",),
    ),
    JournalProfile(
        profile_id="intl-ieee-ieeetran",
        name="IEEE (IEEEtran class)",
        publisher="IEEE",
        scope="international",
        document_class="IEEEtran",
        template_formats=("tex", "docx"),
        abstract_layout=(
            "Conference/journal layouts differ; many two-column journal/conference "
            "templates render abstract/keywords in a full-width block spanning "
            "columns (template-specific), unlike standard article quotation inset."
        ),
        common_requirements=(
            "Use official IEEEtran/template for the target venue; conference vs "
            "Transactions/Journals have different front matter and column rules.",
            "Typical: Index Terms/Keywords, IEEE citation style (numbered).",
        ),
        notes=(
            "Always verify against the specific IEEE journal/conference author "
            "instructions (page limits, biography, open access, etc.).",
        ),
        sources=(
            "https://template-selector.ieee.org/",
            "CTAN: https://ctan.org/pkg/ieeetran",
        ),
        aliases=("ieee", "ieeetran", "ieee transactions", "ieee conference"),
        match_tokens=("ieee", "ieeetran"),
        match_classes=("IEEEtran", "ieeeconf", "IEEEconf"),
    ),
    JournalProfile(
        profile_id="intl-springer-nature-snjnl",
        name="Springer Nature journals (sn-jnl class)",
        publisher="Springer Nature",
        scope="international",
        document_class="sn-jnl",
        template_formats=("tex",),
        abstract_layout=(
            "Defined by sn-jnl class and target journal style; abstract may be "
            "structured or unstructured depending on journal (not the same as "
            "plain article quotation)."
        ),
        common_requirements=(
            "Choose appropriate reference style/options (e.g. sn-basic, sn-mathphys, "
            "sn-vancouver) per journal instructions.",
            "Declarations/availability statements and section requirements vary by "
            "journal/portfolio.",
        ),
        notes=(
            "Springer Nature provides journal-specific submission guidelines; use "
            "the template and instructions for the exact target journal.",
        ),
        required_declarations=("competing_interests", "funding", "author_contributions", "data_availability", "ai_use"),
        sources=(
            "https://www.springernature.com/gp/authors/campaigns/latex-author-support",
            "CTAN: https://ctan.org/pkg/sn-jnl",
        ),
        aliases=("springer", "springer nature", "sn-jnl", "snjnl"),
        match_tokens=("springer", "sn-jnl", "snjnl"),
        match_classes=("sn-jnl",),
    ),
    JournalProfile(
        profile_id="intl-acm-acmart",
        name="ACM (acmart class)",
        publisher="Association for Computing Machinery (ACM)",
        scope="international",
        document_class="acmart",
        template_formats=("tex",),
        abstract_layout=(
            "Abstract/CCS concepts/keywords formatted by acmart for the chosen "
            "format (sigconf, manuscript, etc.), distinct from plain article."
        ),
        common_requirements=(
            "Select correct acmart format and rights/metadata per venue.",
            "ACM reference format and required metadata (CCS concepts, keywords) "
            "are venue/template specific.",
        ),
        notes=(
            "Follow the target ACM venue's call for papers/submission template.",
        ),
        sources=(
            "https://www.acm.org/publications/proceedings-template",
            "CTAN: https://ctan.org/pkg/acmart",
        ),
        aliases=("acm", "acmart"),
        match_tokens=("acm", "acmart"),
        match_classes=("acmart",),
    ),
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def list_profiles(scope: str | None = None) -> list[dict[str, Any]]:
    s = _norm(scope) if scope else ""
    items = PROFILES
    if s and s not in {"all", "*"}:
        items = tuple(p for p in PROFILES if p.scope == s)
    return [p.to_dict() for p in items]


def _profile_haystack(p: JournalProfile) -> str:
    parts = [
        p.profile_id,
        p.name,
        p.publisher,
        p.scope,
        p.document_class or "",
        " ".join(p.aliases),
        " ".join(p.match_tokens),
    ]
    return _norm(" ".join(parts))


def lookup_profiles(query: str, *, limit: int = 10) -> dict[str, Any]:
    q = _norm(query)
    if not q:
        raise ValueError("query is required")
    # exact id or exact alias/name match first
    exact: list[JournalProfile] = []
    scored: list[tuple[int, JournalProfile]] = []
    tokens = [t for t in re.split(r"[^a-z0-9\-]+", q) if t]
    for p in PROFILES:
        hay = _profile_haystack(p)
        if q == _norm(p.profile_id) or q == _norm(p.name) or q in {_norm(a) for a in p.aliases}:
            exact.append(p)
            continue
        score = 0
        for t in tokens:
            if t and t in hay:
                score += 1
        # phrase bonus
        if q in hay:
            score += 2
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].profile_id))
    matches = exact + [p for _, p in scored if p not in exact]
    suggestions = [p for _, p in scored if p not in exact][: max(0, limit)]
    result_matches = [p.to_dict() for p in matches[: max(1, limit)]]
    return {
        "schema": PROFILE_SCHEMA,
        "query": query,
        "count": len(result_matches),
        "matches": result_matches,
        "suggestions": [p.to_dict() for p in suggestions],
        "exact": len(exact) > 0,
    }


_DOC_CLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}")


def detect_profiles(text: str, *, limit: int = 10) -> dict[str, Any]:
    """Heuristic detection from LaTeX source (documentclass/classes/tokens)."""
    src = text or ""
    m = _DOC_CLASS_RE.search(src)
    doc_class = (m.group(1).strip() if m else "") or None
    low = src.lower()
    hits: list[tuple[int, JournalProfile, list[str]]] = []
    for p in PROFILES:
        score = 0
        reasons: list[str] = []
        if doc_class and p.match_classes:
            for c in p.match_classes:
                if c.lower() == doc_class.lower():
                    score += 5
                    reasons.append(f"documentclass={doc_class}")
        if (
            doc_class
            and p.document_class
            and p.document_class.lower() == doc_class.lower()
            and f"documentclass={doc_class}" not in reasons
        ):
            score += 5
            reasons.append(f"documentclass={doc_class}")
        for tok in p.match_tokens:
            if tok and tok.lower() in low:
                score += 1
                reasons.append(f"token:{tok}")
        if score > 0:
            hits.append((score, p, reasons))
    hits.sort(key=lambda x: (-x[0], x[1].profile_id))
    return {
        "schema": PROFILE_SCHEMA,
        "documentclass": doc_class,
        "count": min(len(hits), limit),
        "matches": [
            {**p.to_dict(), "score": s, "reasons": r} for s, p, r in hits[:limit]
        ],
    }


def format_profile_report(result: Mapping[str, Any]) -> str:
    lines: list[str] = []
    schema = result.get("schema", PROFILE_SCHEMA)
    if "matches" in result and "documentclass" in result:
        lines.append(f"Journal profile detection ({schema})")
        lines.append(f"documentclass: {result.get('documentclass') or '(not found)'}")
        for i, m in enumerate(result.get("matches") or [], 1):
            lines.append(
                f"{i}. [{m.get('scope')}] {m.get('name')} ({m.get('profile_id')}) "
                f"score={m.get('score')} reasons={','.join(m.get('reasons') or [])}"
            )
            if m.get("abstract_layout"):
                lines.append(f"   abstract: {m.get('abstract_layout')}")
        if not result.get("matches"):
            lines.append("No matching profiles detected.")
        return "\n".join(lines)

    if "matches" in result:
        lines.append(f"Journal profile lookup ({schema})")
        lines.append(f"query: {result.get('query')!r} exact={result.get('exact')}")
        for i, m in enumerate(result.get("matches") or [], 1):
            lines.append(f"{i}. [{m.get('scope')}] {m.get('name')} ({m.get('profile_id')})")
            if m.get("document_class"):
                lines.append(f"   class: {m.get('document_class')}")
            if m.get("abstract_layout"):
                lines.append(f"   abstract: {m.get('abstract_layout')}")
            reqs = m.get("common_requirements") or ()
            if reqs:
                lines.append(f"   requirements: {reqs[0]}")
            srcs = m.get("sources") or ()
            if srcs:
                lines.append(f"   source: {srcs[0]}")
        if not result.get("matches"):
            lines.append("No profiles matched.")
        return "\n".join(lines)

    # list
    items = result.get("profiles") or result.get("items") or []
    lines.append(f"Journal profiles ({schema}) count={len(items)}")
    for p in items:
        lines.append(f"- [{p.get('scope')}] {p.get('name')} ({p.get('profile_id')})")
    return "\n".join(lines)

"""Thesis checks: what an examiner looks at that a journal editor does not.

A skripsi, tesis or disertasi is judged on more than its argument. Before an
examiner reads Chapter 3, the front matter must carry an approval page and an
originality statement, Chapter 1 must state the problem, the objectives and
their scope, the research questions must be answered one by one in the
conclusion, and the layout must follow the campus guide. Each check here is a
presence test, a count or a comparison with a :mod:`paperassist.thesis_profiles`
profile, never a judgement on the research.

* :func:`resolve_document_kind` tells a thesis from a journal article.
* :func:`check_thesis` returns the front matter found and missing, the
  Chapter 1 elements, research-question alignment and layout mismatches.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .thesis_extras import (
    check_abstracts,
    check_citation_style,
    check_floats,
    list_items,
    trace_research_questions,
)
from .thesis_profiles import PROFILES, ThesisProfile, detect_thesis_profiles, thesis_profile

DOCUMENT_KINDS = ("article", "thesis")
# A proposal (seminar proposal) carries Chapters 1-3; the final thesis
# (seminar hasil, sidang) carries results and conclusions too.
THESIS_STAGES = ("proposal", "final")
_PROPOSAL_ALIASES = {"proposal", "usulan", "usulan penelitian", "seminar proposal", "praproposal"}
_FINAL_ALIASES = {"final", "full", "hasil", "seminar hasil", "sidang", "ujian"}
PROPOSAL_FRONT_MATTER: tuple[str, ...] = ("title_page", "approval_page", "table_of_contents")
_PROPOSAL_WORDS_RE = re.compile(
    r"\bproposal (?:tesis|skripsi|disertasi|penelitian)\b|\busulan penelitian\b"
    r"|\bthesis proposal\b|\bresearch proposal\b|\bseminar proposal\b",
    re.IGNORECASE,
)
_LATE_CHAPTER_RE = re.compile(r"hasil|pembahasan|kesimpulan|simpulan|penutup|result|conclusion|discussion", re.I)


def resolve_thesis_stage(value: str | None, text: str) -> str:
    """``proposal`` or ``final``; ``auto`` reads the title block, then whether
    any results or conclusion chapter exists."""

    raw = str(value or "auto").strip().lower()
    if raw in _PROPOSAL_ALIASES:
        return "proposal"
    if raw in _FINAL_ALIASES:
        return "final"
    if raw != "auto":
        raise ValueError(f"unknown thesis_stage: {value!r}; use proposal, final or auto")
    if _PROPOSAL_WORDS_RE.search((text or "")[:_HEAD_WINDOW]):
        return "proposal"
    late = [m for m in _NUMBERED_CHAPTER_RE.finditer(text or "") if _LATE_CHAPTER_RE.search(m.group(1))]
    return "final" if late else "proposal"

_THESIS_ALIASES = {"thesis", "tesis", "skripsi", "disertasi", "dissertation", "thesis_report"}
_ARTICLE_ALIASES = {"article", "paper", "journal", "artikel", "jurnal"}

# A thesis names itself near its title, opens chapters with "BAB I", or
# carries an approval page; a \chapter in a report or book class is the
# structural signal when the words are missing.
_THESIS_WORDS_RE = re.compile(
    r"\b(?:skripsi|tesis|disertasi|undergraduate thesis|master'?s? thesis|doctoral thesis"
    r"|phd thesis|dissertation)\b|lembar pengesahan|halaman pengesahan|lembar persetujuan"
    r"|halaman persetujuan|persetujuan pembimbing|\bBAB\s+(?:I|1)\b",
    re.IGNORECASE,
)
_DOCUMENTCLASS_RE = re.compile(r"\\documentclass\s*(?:\[([^\]]*)\])?\s*\{([^}]+)\}")
_CHAPTER_RE = re.compile(r"\\chapter\*?\s*\{([^{}]*)\}")
_NUMBERED_CHAPTER_RE = re.compile(r"\\chapter\s*\{([^{}]*)\}")
_HEADING_RE = re.compile(
    r"\\(chapter|section|subsection|subsubsection)\*?\s*\{([^{}]*)\}"
)
_HEAD_WINDOW = 4000


def resolve_document_kind(value: str | None, text: str) -> str:
    """``thesis`` or ``article`` from an explicit value or the manuscript.

    ``auto`` (or nothing) reads the opening: the words skripsi/tesis/
    disertasi/dissertation, "BAB I", or an approval page mark a thesis, as
    does a report or book class with numbered chapters.
    """

    raw = str(value or "auto").strip().lower()
    if raw in _THESIS_ALIASES:
        return "thesis"
    if raw in _ARTICLE_ALIASES:
        return "article"
    if raw != "auto":
        raise ValueError(f"unknown document_kind: {value!r}; use article, thesis or auto")
    source = text or ""
    head = source[:_HEAD_WINDOW]
    match = _DOCUMENTCLASS_RE.search(head)
    doc_class = (match.group(2).strip().lower() if match else "")
    chapters = len(_NUMBERED_CHAPTER_RE.findall(source))
    if _THESIS_WORDS_RE.search(head) and (chapters >= 2 or doc_class in ("report", "book")):
        return "thesis"
    if doc_class in ("report", "book", "memoir", "scrreprt", "scrbook") and chapters >= 3:
        return "thesis"
    if "thesis" in doc_class or doc_class.endswith("thesis") or "tesis" in doc_class:
        return "thesis"
    return "article"


# --------------------------------------------------------------- front matter
# Each item: what it is, and how its heading or text reads in Indonesian and
# English templates.
FRONT_MATTER_PATTERNS: dict[str, str] = {
    "title_page": r"\\begin\{titlepage\}|\\maketitle|halaman judul|title page|\\title\s*\{",
    "approval_page": (
        r"lembar pengesahan|halaman pengesahan|lembar persetujuan|halaman persetujuan"
        r"|persetujuan pembimbing|approval (?:page|sheet)|certificate of approval|approved by"
    ),
    "originality_statement": (
        r"pernyataan (?:keaslian|orisinalitas|bebas plagia\w*)|lembar pernyataan"
        r"|halaman pernyataan|surat pernyataan|declaration of (?:originality|authorship)"
        r"|statement of (?:originality|authorship)|author'?s declaration|\bdeclaration\b"
    ),
    "preface": (
        r"kata pengantar|prakata|ucapan terima kasih|acknowledge?ments?|\bpreface\b"
    ),
    "abstract": r"\\begin\{abstract\}|\babstrak\b|\bintisari\b|\babstract\b",
    "abstract_english": r"\babstract\b",
    "table_of_contents": r"\\tableofcontents|daftar isi|table of contents",
    "list_of_tables": r"\\listoftables|daftar tabel|list of tables",
    "list_of_figures": r"\\listoffigures|daftar gambar|list of figures",
    "publication_consent": (
        r"persetujuan publikasi|pernyataan persetujuan publikasi|publication (?:consent|agreement)"
        r"|repository (?:agreement|licen[cs]e)"
    ),
    "ai_use": (
        r"penggunaan (?:ai|kecerdasan (?:buatan|artifisial)|generative ai)"
        r"|(?:use|usage) of (?:generative )?(?:ai|artificial intelligence)|ai[- ]assisted"
        r"|tidak menggunakan (?:ai|kecerdasan)|no (?:generative )?ai (?:tools? )?(?:was|were) used"
    ),
}

FRONT_MATTER_LABELS: dict[str, str] = {
    "title_page": "title page (halaman judul)",
    "approval_page": "approval page (lembar pengesahan/persetujuan)",
    "originality_statement": "originality statement (pernyataan keaslian)",
    "preface": "preface or acknowledgements (kata pengantar)",
    "abstract": "abstract (abstrak)",
    "abstract_english": "English abstract",
    "table_of_contents": "table of contents (daftar isi)",
    "list_of_tables": "list of tables (daftar tabel)",
    "list_of_figures": "list of figures (daftar gambar)",
    "publication_consent": "publication consent (persetujuan publikasi)",
    "ai_use": "AI-use statement",
}

DEFAULT_THESIS_FRONT_MATTER: tuple[str, ...] = (
    "title_page",
    "approval_page",
    "originality_statement",
    "abstract",
    "table_of_contents",
)
RECOMMENDED_THESIS_FRONT_MATTER: tuple[str, ...] = ("preface", "ai_use", "publication_consent")

# A profile lists its front matter in prose ("halaman persetujuan pembimbing",
# "abstrak (Indonesia dan Inggris)"); these map it to the items above.
_PROFILE_FRONT_MATTER: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"judul|title page", ("title_page",)),
    (r"pengesahan|persetujuan pembimbing|approval", ("approval_page",)),
    (r"pernyataan|declaration|originality", ("originality_statement",)),
    (r"kata pengantar|prakata|acknowledg|preface", ("preface",)),
    (r"abstrak.*(?:inggris|english)|abstract.*english", ("abstract", "abstract_english")),
    (r"abstra", ("abstract",)),
    (r"daftar isi|contents", ("table_of_contents",)),
    (r"daftar tabel|list of tables", ("list_of_tables",)),
    (r"daftar gambar|list of figures", ("list_of_figures",)),
)

_INDONESIAN_RE = re.compile(
    r"\\usepackage\[[^\]]*(?:indonesian|bahasa)[^\]]*\]\{babel\}|\b(?:penelitian|yang|dengan|adalah)\b",
    re.IGNORECASE,
)


def front_matter_region(text: str) -> str:
    """The document up to its first numbered chapter (or ``\\mainmatter``)."""

    end = len(text)
    mainmatter = text.find("\\mainmatter")
    if mainmatter >= 0:
        end = mainmatter
    for match in _NUMBERED_CHAPTER_RE.finditer(text):
        title = match.group(1).strip().lower()
        # A numbered "Abstrak" chapter is still front matter.
        if re.search(r"abstra|intisari|kata pengantar|pengesahan|pernyataan", title):
            continue
        end = min(end, match.start())
        break
    return text[:end]


def _back_region(text: str) -> str:
    """Appendices and statements placed after the last chapter."""

    appendix = re.search(r"\\appendix\b|\\chapter\*?\s*\{\s*lampiran", text, re.IGNORECASE)
    return text[appendix.start():] if appendix else ""


def required_front_matter(profile: ThesisProfile | None, *, indonesian: bool) -> tuple[str, ...]:
    items: list[str] = []
    if profile and profile.front_matter:
        for entry in profile.front_matter:
            lowered = entry.lower()
            for pattern, names in _PROFILE_FRONT_MATTER:
                if re.search(pattern, lowered):
                    items.extend(name for name in names if name not in items)
                    break
        for name in ("approval_page", "originality_statement"):
            # Every thesis guide asks for both, even when a profile folds them
            # into the title-page description.
            if name not in items and profile.scope == "indonesia":
                items.append(name)
    else:
        items = list(DEFAULT_THESIS_FRONT_MATTER)
    if indonesian and "abstract_english" not in items:
        # Indonesian theses carry an English abstract next to the Abstrak.
        items.append("abstract_english")
    return tuple(items)


# -------------------------------------------------------------- Chapter 1
# The elements an Indonesian thesis guide asks of BAB I, with their usual
# English names. Each is found as a heading anywhere in the opening chapter.
CHAPTER_ONE_ELEMENTS: dict[str, str] = {
    "background": r"latar belakang|background",
    "problem_statement": r"rumusan masalah|perumusan masalah|identifikasi masalah|problem statement|research questions?|pertanyaan penelitian",
    "objectives": r"tujuan|objectives?|aims?\b",
    "benefits": r"manfaat|kegunaan|significance|contributions?|kontribusi",
    "scope": r"batasan|ruang lingkup|lingkup|scope|delimitation",
    "outline": r"sistematika|outline of the thesis|thesis (?:outline|organi[sz]ation)|struktur (?:penulisan|tesis)",
}
REQUIRED_CHAPTER_ONE: tuple[str, ...] = ("background", "problem_statement", "objectives", "scope")

_ITEM_RE = re.compile(r"\\item\b")
_NUMBERED_LINE_RE = re.compile(r"(?m)^\s*(?:\d+[.)]|[a-e][.)])\s+\S")


def _chapters(text: str) -> list[tuple[str, str]]:
    """``(title, body)`` for each numbered chapter, in order."""

    matches = list(_NUMBERED_CHAPTER_RE.finditer(text))
    out: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        out.append((match.group(1).strip(), text[match.end():end]))
    return out


def _subheading_bodies(body: str) -> list[tuple[str, str]]:
    matches = [m for m in _HEADING_RE.finditer(body) if m.group(1) != "chapter"]
    out: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        out.append((match.group(2).strip(), body[match.end():end]))
    return out


def _count_items(body: str) -> int:
    items = len(_ITEM_RE.findall(body))
    return items or len(_NUMBERED_LINE_RE.findall(body))


def _chapter_one(chapters: Sequence[tuple[str, str]]) -> tuple[str, str] | None:
    for title, body in chapters:
        if re.search(r"pendahuluan|introduction", title, re.IGNORECASE):
            return title, body
    return chapters[0] if chapters else None


def _conclusion_chapter(chapters: Sequence[tuple[str, str]]) -> tuple[str, str] | None:
    for title, body in reversed(chapters):
        if re.search(r"kesimpulan|simpulan|penutup|conclusion", title, re.IGNORECASE):
            return title, body
    return None


# ------------------------------------------------------------------ layout
_FONT_SIZE_RE = re.compile(r"(\d{2})pt")
_PAPER_RE = re.compile(r"\b(a4|letter|b5|a5)paper\b|paper\s*=\s*(a4|letter|b5|a5)", re.IGNORECASE)
_SPACING_RE = re.compile(
    r"\\(onehalfspacing|doublespacing|singlespacing)\b"
    r"|\\linespread\s*\{\s*([\d.]+)\s*\}|\\setstretch\s*\{\s*([\d.]+)\s*\}"
    r"|\\begin\{spacing\}\s*\{\s*([\d.]+)\s*\}"
)
_GEOMETRY_RE = re.compile(r"\\(?:usepackage|geometry)\s*(?:\[([^\]]*)\])?\s*\{geometry\}|\\geometry\s*\{([^}]*)\}")
_MARGIN_RE = re.compile(r"\b(left|right|top|bottom|inner|outer)\s*=\s*([\d.]+)\s*(cm|mm|in)\b")

# \linespread is a factor on the font's own spacing: 1.3 gives the "one and a
# half" spacing in Word terms, 1.6 double. setspace commands state the Word value.
_LINESPREAD_TO_SPACING = ((1.25, 1.5), (1.55, 2.0))


def _spacing(text: str) -> float | None:
    match = _SPACING_RE.search(text)
    if not match:
        return None
    named, spread, stretch, env = match.groups()
    if named:
        return {"onehalfspacing": 1.5, "doublespacing": 2.0, "singlespacing": 1.0}[named]
    if spread:
        value = float(spread)
        for floor, spacing in reversed(_LINESPREAD_TO_SPACING):
            if value >= floor:
                return spacing
        return 1.0
    return float(stretch or env)


def _margins(text: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for match in _GEOMETRY_RE.finditer(text):
        options = match.group(1) or match.group(2) or ""
        for side, value, unit in _MARGIN_RE.findall(options):
            cm = float(value) * {"cm": 1.0, "mm": 0.1, "in": 2.54}[unit]
            key = {"inner": "left", "outer": "right"}.get(side, side)
            found[key] = round(cm, 2)
    return found


def check_layout(text: str, profile: ThesisProfile) -> list[dict[str, Any]]:
    """Compare the preamble with the profile; return one entry per mismatch."""

    head = text[: text.find("\\begin{document}")] if "\\begin{document}" in text else text[:_HEAD_WINDOW]
    issues: list[dict[str, Any]] = []
    match = _DOCUMENTCLASS_RE.search(head)
    options = (match.group(1) or "") if match else ""
    size = _FONT_SIZE_RE.search(options)
    if size and float(size.group(1)) != profile.body_font_size_pt:
        issues.append({"item": "font size", "found": f"{size.group(1)} pt",
                       "expected": f"{profile.body_font_size_pt:g} pt"})
    elif not size and profile.body_font_size_pt != 10:
        issues.append({"item": "font size", "found": "10 pt (LaTeX default)",
                       "expected": f"{profile.body_font_size_pt:g} pt"})
    paper = _PAPER_RE.search(options + " " + head)
    if paper:
        stated = (paper.group(1) or paper.group(2)).lower()
        if stated != profile.paper_size.lower():
            issues.append({"item": "paper size", "found": stated.upper(),
                           "expected": profile.paper_size})
    elif profile.paper_size.upper() != "LETTER":
        issues.append({"item": "paper size", "found": "letter (LaTeX default)",
                       "expected": profile.paper_size})
    spacing = _spacing(head)
    if spacing is None and profile.line_spacing != 1.0:
        issues.append({"item": "line spacing", "found": "single (not set)",
                       "expected": f"{profile.line_spacing:g}"})
    elif spacing is not None and abs(spacing - profile.line_spacing) > 0.05:
        issues.append({"item": "line spacing", "found": f"{spacing:g}",
                       "expected": f"{profile.line_spacing:g}"})
    margins = _margins(head)
    for side, expected in profile.margins_cm.items():
        found = margins.get(side)
        if found is None:
            issues.append({"item": f"{side} margin", "found": "not set",
                           "expected": f"{expected:g} cm"})
        elif abs(found - expected) > 0.05:
            issues.append({"item": f"{side} margin", "found": f"{found:g} cm",
                           "expected": f"{expected:g} cm"})
    return issues


# ------------------------------------------------------------------ result
@dataclass(frozen=True)
class ThesisIssue:
    check: str
    severity: str
    message: str
    remedy: str

    def to_dict(self) -> dict[str, str]:
        return {"check": self.check, "severity": self.severity,
                "message": self.message, "remedy": self.remedy}


@dataclass(frozen=True)
class ThesisCheck:
    profile_id: str | None
    stage: str
    front_matter_required: tuple[str, ...]
    front_matter_present: tuple[str, ...]
    front_matter_recommended_missing: tuple[str, ...] = ()
    chapters: tuple[str, ...] = ()
    chapter_one: Mapping[str, bool] = field(default_factory=dict)
    research_questions: int = 0
    objectives: int = 0
    conclusion_points: int = 0
    layout: tuple[Mapping[str, Any], ...] = ()
    words: int = 0
    word_range: tuple[int, int] | None = None
    issues: tuple[ThesisIssue, ...] = ()
    # Each research question followed to the method, results and conclusion.
    trace: tuple[Mapping[str, Any], ...] = ()
    abstracts: Mapping[str, Any] = field(default_factory=dict)
    floats: Mapping[str, Any] = field(default_factory=dict)
    citations: Mapping[str, Any] = field(default_factory=dict)

    @property
    def front_matter_missing(self) -> tuple[str, ...]:
        return tuple(n for n in self.front_matter_required if n not in self.front_matter_present)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "stage": self.stage,
            "front_matter": {
                "required": list(self.front_matter_required),
                "present": list(self.front_matter_present),
                "missing": list(self.front_matter_missing),
                "recommended_missing": list(self.front_matter_recommended_missing),
            },
            "chapters": list(self.chapters),
            "chapter_one": dict(self.chapter_one),
            "alignment": {
                "research_questions": self.research_questions,
                "objectives": self.objectives,
                "conclusion_points": self.conclusion_points,
            },
            "layout_mismatches": [dict(item) for item in self.layout],
            "words": self.words,
            "word_range": list(self.word_range) if self.word_range else None,
            "trace": [dict(row) for row in self.trace],
            "abstracts": dict(self.abstracts),
            "floats": dict(self.floats),
            "citations": dict(self.citations),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def resolve_thesis_profile(value: str | Mapping[str, Any] | None, text: str) -> ThesisProfile | None:
    """The profile named by ``value`` (an id, or a mapping with ``profile_id``),
    or the best one detected from the source; ``None`` when nothing matches."""

    if isinstance(value, Mapping):
        value = value.get("profile_id")
    if value and str(value).strip().lower() != "auto":
        return thesis_profile(str(value).strip())
    detected = detect_thesis_profiles(text, limit=1)["matches"]
    if detected:
        wanted = detected[0]["profile_id"]
        return next(p for p in PROFILES if p.profile_id == wanted)
    return None


def _word_count(text: str) -> int:
    body = re.sub(r"(?<!\\)%.*$", " ", text, flags=re.M)
    body = re.sub(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?", " ", body)
    return len(re.findall(r"[A-Za-z\u00C0-\u024F0-9'’-]+", body))


def check_thesis(
    text: str,
    *,
    profile: str | Mapping[str, Any] | ThesisProfile | None = "auto",
    required_front_matter_items: Sequence[str] | None = None,
    stage: str | None = "auto",
) -> ThesisCheck:
    """Run every thesis check on a (flattened) LaTeX thesis.

    At the ``proposal`` stage only the title page, approval page and table of
    contents are required, and the conclusion is not checked against the
    research questions.
    """

    resolved = profile if isinstance(profile, ThesisProfile) else resolve_thesis_profile(profile, text)
    resolved_stage = resolve_thesis_stage(stage, text)
    proposal = resolved_stage == "proposal"
    indonesian = bool(_INDONESIAN_RE.search(text[:20000]))
    front = front_matter_region(text) + "\n" + _back_region(text)
    unknown = set(required_front_matter_items or ()) - set(FRONT_MATTER_PATTERNS)
    if unknown:
        raise ValueError(f"unknown front matter items: {sorted(unknown)}")
    required = (
        tuple(required_front_matter_items)
        if required_front_matter_items is not None
        else PROPOSAL_FRONT_MATTER
        if proposal
        else required_front_matter(resolved, indonesian=indonesian)
    )
    present = [
        name for name, pattern in FRONT_MATTER_PATTERNS.items()
        if re.search(pattern, front, re.IGNORECASE)
    ]
    # "Abstract" alone in an English thesis is its only abstract.
    if "abstract_english" in present and not indonesian and "abstract" not in present:
        present.append("abstract")
    recommended_missing = () if proposal else tuple(
        name for name in RECOMMENDED_THESIS_FRONT_MATTER
        if name not in required and name not in present
    )
    issues: list[ThesisIssue] = []
    for name in required:
        if name not in present:
            issues.append(ThesisIssue(
                check="front_matter", severity="warning",
                message=f"front matter lacks the {FRONT_MATTER_LABELS[name]}",
                remedy="add it before Chapter 1 as the campus guide prescribes",
            ))

    chapters = _chapters(text)
    chapter_titles = tuple(title for title, _ in chapters
                           if not re.search(r"abstra|intisari", title, re.IGNORECASE))
    elements: dict[str, bool] = {}
    research_questions = objectives = conclusion_points = 0
    questions: list[str] = []
    first = _chapter_one(chapters)
    if first:
        subs = _subheading_bodies(first[1])
        for name, pattern in CHAPTER_ONE_ELEMENTS.items():
            elements[name] = any(re.search(pattern, title, re.IGNORECASE) for title, _ in subs)
        for title, body in subs:
            if re.search(CHAPTER_ONE_ELEMENTS["problem_statement"], title, re.IGNORECASE):
                research_questions += _count_items(body)
                questions.extend(list_items(body))
            elif re.search(CHAPTER_ONE_ELEMENTS["objectives"], title, re.IGNORECASE):
                objectives += _count_items(body)
        for name in REQUIRED_CHAPTER_ONE:
            if not elements.get(name):
                label = name.replace("_", " ")
                issues.append(ThesisIssue(
                    check="chapter_one", severity="warning",
                    message=f"Chapter 1 has no {label} subsection",
                    remedy=f"add a {label} subsection to the introduction chapter",
                ))
    last = _conclusion_chapter(chapters)
    if last:
        for title, body in _subheading_bodies(last[1]) or [(last[0], last[1])]:
            if re.search(r"kesimpulan|simpulan|conclusion", title, re.IGNORECASE):
                conclusion_points += _count_items(body)
    if research_questions and objectives and research_questions != objectives:
        issues.append(ThesisIssue(
            check="alignment", severity="warning",
            message=(f"{research_questions} research questions but {objectives} objectives "
                     "in Chapter 1"),
            remedy="give each research question one objective, in the same order",
        ))
    if (not proposal and research_questions and conclusion_points
            and conclusion_points < research_questions):
        issues.append(ThesisIssue(
            check="alignment", severity="warning",
            message=(f"the conclusion answers {conclusion_points} points for "
                     f"{research_questions} research questions"),
            remedy="answer every research question in the conclusion, one point each",
        ))

    trace: list[dict[str, Any]] = []
    if questions:
        trace, found = trace_research_questions(text, questions, stage=resolved_stage)
        issues.extend(ThesisIssue("trace", sev, msg, fix) for sev, msg, fix in found)
    abstracts: dict[str, Any] = {}
    if not proposal:
        abstracts, found = check_abstracts(
            text, layout=resolved.abstract_layout if resolved else "", indonesian=indonesian
        )
        issues.extend(ThesisIssue("abstract", sev, msg, fix) for sev, msg, fix in found)
    floats, found = check_floats(text)
    issues.extend(ThesisIssue("floats", sev, msg, fix) for sev, msg, fix in found)
    citations, found = check_citation_style(text, expected=resolved.citation_style if resolved else "")
    issues.extend(ThesisIssue("citations", sev, msg, fix) for sev, msg, fix in found)

    layout: list[dict[str, Any]] = check_layout(text, resolved) if resolved else []
    for item in layout:
        issues.append(ThesisIssue(
            check="layout", severity="info",
            message=f"{item['item']} is {item['found']}; the profile expects {item['expected']}",
            remedy=f"set it in the preamble (profile {resolved.profile_id if resolved else ''})",
        ))
    words = _word_count(text)
    word_range = resolved.word_range if resolved else None
    if word_range and not word_range[0] <= words <= word_range[1]:
        issues.append(ThesisIssue(
            check="length", severity="info",
            message=f"the thesis has about {words} words; the guide asks {word_range[0]}-{word_range[1]}",
            remedy="check the length rule of the campus guide",
        ))
    if word_range and proposal:
        # A length rule is for the finished thesis.
        issues = [issue for issue in issues if issue.check != "length"]
    return ThesisCheck(
        profile_id=resolved.profile_id if resolved else None,
        stage=resolved_stage,
        front_matter_required=required,
        front_matter_present=tuple(present),
        front_matter_recommended_missing=recommended_missing,
        chapters=chapter_titles,
        chapter_one=elements,
        research_questions=research_questions,
        objectives=objectives,
        conclusion_points=conclusion_points,
        layout=tuple(layout),
        words=words,
        word_range=word_range,
        issues=tuple(issues),
        trace=tuple(trace),
        abstracts=abstracts,
        floats=floats,
        citations=citations,
    )


__all__ = [
    "CHAPTER_ONE_ELEMENTS",
    "DEFAULT_THESIS_FRONT_MATTER",
    "DOCUMENT_KINDS",
    "FRONT_MATTER_LABELS",
    "FRONT_MATTER_PATTERNS",
    "PROPOSAL_FRONT_MATTER",
    "THESIS_STAGES",
    "resolve_thesis_stage",
    "ThesisCheck",
    "ThesisIssue",
    "check_layout",
    "check_thesis",
    "front_matter_region",
    "required_front_matter",
    "resolve_document_kind",
    "resolve_thesis_profile",
]

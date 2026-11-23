"""Thesis checks an examiner applies across chapters.

* :func:`trace_research_questions`: each research question from Chapter 1 is
  followed to the method chapter, the results chapter and the conclusion.
* :func:`check_abstracts`: the Abstrak and the English Abstract against the
  profile's length rule and against each other (keywords, numbers).
* :func:`check_floats`: tables captioned above, figures below, numbered per
  chapter (Tabel 3.1), and referenced in the text before they appear.
* :func:`check_citation_style`: one citation style, the one the guide names.

Every check is a presence test, a count or a text match. A trace that finds no
section for a question means the words of the question do not appear there,
not that the question is unanswered; the finding says which, so the student
can label the section (RQ1, rumusan masalah 1) when the wording differs.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from typing import Any

_HEADING_RE = re.compile(r"\\(chapter|section|subsection|subsubsection)\*?\s*\{([^{}]*)\}")
_NUMBERED_CHAPTER_RE = re.compile(r"\\chapter\s*\{([^{}]*)\}")
_ITEM_SPLIT_RE = re.compile(r"\\item\b(?:\s*\[[^\]]*\])?")
_NUMBERED_LINE_RE = re.compile(r"(?m)^\s*(?:\d+[.)]|[a-e][.)])\s+")
_LIST_ENV_RE = re.compile(r"\\(?:begin|end)\{(?:enumerate|itemize|description)\}")
_WORD_RE = re.compile(r"[a-z\u00c0-\u024f]+")

_METHOD_TITLE = re.compile(r"metode|metodologi|method|rancangan penelitian|research design", re.I)
_RESULTS_TITLE = re.compile(r"hasil|pembahasan|result|discussion|pengujian|evaluasi|evaluation|temuan|findings", re.I)
_CONCLUSION_TITLE = re.compile(r"kesimpulan|simpulan|penutup|conclusion", re.I)

_ORDINALS_ID = ("pertama", "kedua", "ketiga", "keempat", "kelima", "keenam")
_ORDINALS_EN = ("first", "second", "third", "fourth", "fifth", "sixth")

# Words every research question shares: question words, connectives and the
# verbs of a question, in Indonesian and English.
_STOPWORDS = frozenset(
    ["bagaimana", "apakah", "seberapa", "sejauh", "mana", "manakah", "berapa", "mengapa", "kenapa", "yang", "dengan", "dalam", "untuk", "pada", "dari", "oleh", "atau", "serta", "antara", "terhadap", "tersebut", "adalah", "dapat", "akan", "sebagai", "secara", "lebih", "bila", "jika", "agar", "sehingga", "karena", "penelitian", "masalah", "rumusan", "tujuan", "mengetahui", "menganalisis", "menentukan", "merancang", "membangun", "mengembangkan", "mengukur", "menguji", "mengevaluasi", "besar", "kecil", "tinggi", "rendah", "dibanding", "dibandingkan", "perbandingan", "pengaruh", "what", "which", "whether", "does", "extent", "their", "there", "these", "those", "with", "from", "into", "about", "between", "under", "using", "based", "study", "research", "question", "questions"]
)


def _strip(text: str) -> str:
    text = re.sub(r"(?<!\\)%.*$", " ", text, flags=re.M)
    text = re.sub(r"\\(?:cite\w*|ref|label|eqref|autoref|cref)\*?(?:\[[^\]]*\])*\{[^{}]*\}", " ", text)
    text = re.sub(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"[{}$&_^~]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _chapters(text: str) -> list[tuple[str, str]]:
    matches = list(_NUMBERED_CHAPTER_RE.finditer(text))
    out: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        out.append((match.group(1).strip(), text[match.end():end]))
    return out


def _units(title: str, body: str) -> list[tuple[str, str]]:
    """The chapter's subsections as ``(heading, body)``; the chapter itself when
    it has none."""

    matches = [m for m in _HEADING_RE.finditer(body) if m.group(1) != "chapter"]
    if not matches:
        return [(title, body)]
    out = [(title, body[:matches[0].start()])] if body[:matches[0].start()].strip() else []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        out.append((match.group(2).strip(), body[match.end():end]))
    return out


def list_items(body: str) -> list[str]:
    """The items of the first list in ``body`` (``\\item`` or numbered lines)."""

    if _ITEM_SPLIT_RE.search(body):
        parts = _ITEM_SPLIT_RE.split(body)[1:]
        return [_strip(_LIST_ENV_RE.split(part)[0]) for part in parts if _strip(part)]
    starts = list(_NUMBERED_LINE_RE.finditer(body))
    items: list[str] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        chunk = body[match.end():end].split("\n\n")[0]
        if _strip(chunk):
            items.append(_strip(chunk))
    return items


def _keywords(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) >= 5 and w not in _STOPWORDS}


def _label_pattern(index: int) -> re.Pattern[str]:
    n = index + 1
    ordinal_id = _ORDINALS_ID[index] if index < len(_ORDINALS_ID) else str(n)
    ordinal_en = _ORDINALS_EN[index] if index < len(_ORDINALS_EN) else str(n)
    return re.compile(
        rf"\b(?:RQ|RM|PP|Q)\s*-?\s*{n}\b"
        rf"|\b(?:rumusan masalah|pertanyaan penelitian|tujuan(?: penelitian)?)\s+(?:ke-?\s*)?{n}\b"
        rf"|\b(?:rumusan masalah|pertanyaan penelitian|tujuan(?: penelitian)?)\s+(?:yang\s+)?{ordinal_id}\b"
        rf"|\bresearch question\s+{n}\b|\b{ordinal_en}\s+research question\b",
        re.IGNORECASE,
    )


def trace_research_questions(
    text: str, questions: Sequence[str], *, stage: str
) -> tuple[list[dict[str, Any]], list[tuple[str, str, str]]]:
    """Follow each question to the method, results and conclusion chapters.

    A section answers a question when it carries the question's label (RQ1,
    rumusan masalah 1, "tujuan pertama") or most of its distinctive words, the
    ones it does not share with every other question. Returns the trace rows
    and ``(severity, message, remedy)`` issues.
    """

    chapters = _chapters(text)
    targets: dict[str, list[tuple[str, str]]] = {"method": [], "results": [], "conclusion": []}
    for title, body in chapters:
        if _CONCLUSION_TITLE.search(title):
            targets["conclusion"].extend(_units(title, body))
        elif _METHOD_TITLE.search(title):
            targets["method"].extend(_units(title, body))
        elif _RESULTS_TITLE.search(title):
            targets["results"].extend(_units(title, body))
    keyword_sets = [_keywords(q) for q in questions]
    shared = set.intersection(*keyword_sets) if len(keyword_sets) > 1 else set()
    unit_words = {
        stage_name: [(heading, _keywords(heading + " " + _strip(body)), heading + " " + body)
                     for heading, body in units]
        for stage_name, units in targets.items()
    }
    rows: list[dict[str, Any]] = []
    issues: list[tuple[str, str, str]] = []
    checked = ("method",) if stage == "proposal" else ("method", "results", "conclusion")
    for index, question in enumerate(questions):
        distinctive = (keyword_sets[index] - shared) or keyword_sets[index]
        need = max(1, math.ceil(0.6 * len(distinctive)))
        label = _label_pattern(index)
        row: dict[str, Any] = {"rq": index + 1, "question": question[:160]}
        for stage_name in ("method", "results", "conclusion"):
            found = None
            for heading, words, raw in unit_words[stage_name]:
                if label.search(raw) or (distinctive and len(distinctive & words) >= need):
                    found = heading
                    break
            row[stage_name] = found
            if stage_name in checked and targets[stage_name] and found is None:
                where = {"method": "the method chapter", "results": "the results chapter",
                         "conclusion": "the conclusion"}[stage_name]
                issues.append((
                    "warning",
                    f"research question {index + 1} is not traced to {where}",
                    f"address it there by name (RQ{index + 1} or 'rumusan masalah {index + 1}') "
                    "or with the terms of the question",
                ))
        rows.append(row)
    return rows, issues


# ---------------------------------------------------------------- abstracts
_ABSTRACT_HEAD_RE = re.compile(
    r"\\(?:chapter|section)\*?\s*\{\s*(abstrak|intisari|abstract)\s*\}|\\begin\{abstract\}",
    re.IGNORECASE,
)
_ABSTRACT_END_RE = re.compile(
    r"\\end\{abstract\}|\\(?:chapter|section)\*?\s*\{|\\tableofcontents|\\listof|\\mainmatter|\\newpage|\\clearpage"
)
_KEYWORDS_RE = re.compile(r"(?:kata[\s~-]*kunci|keywords?)\s*[:：.]?\s*(?:\}\s*)?(.+)", re.IGNORECASE)
_NUMBER_RE = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*(?![\w])")
_EN_RE = re.compile(r"\b(?:the|and|of|this|was|were|with)\b", re.IGNORECASE)
_ID_RE = re.compile(r"\b(?:yang|dan|dengan|ini|untuk|pada|dari)\b", re.IGNORECASE)


def abstract_limits(layout: str) -> tuple[int | None, int | None]:
    """``(max words, max paragraphs)`` stated in a profile's ``abstract_layout``."""

    words = re.search(r"maks\w*(?:\s+sekitar)?\s+(\d+)\s+kata|<=\s*(\d+)\s+words|at most\s+(\d+)\s+words",
                      layout or "", re.IGNORECASE)
    paragraphs = re.search(r"(\d+)\s+(?:alinea|paragra)", layout or "", re.IGNORECASE)
    max_words = int(next(g for g in words.groups() if g)) if words else None
    return max_words, int(paragraphs.group(1)) if paragraphs else None


def _abstracts(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for match in _ABSTRACT_HEAD_RE.finditer(text):
        end = _ABSTRACT_END_RE.search(text, match.end())
        body = text[match.end(): end.start() if end else match.end() + 6000]
        if not _strip(body):
            continue
        title = (match.group(1) or "").lower()
        if title in ("abstrak", "intisari"):
            lang = "id"
        elif title == "abstract":
            lang = "en"
        else:
            plain = _strip(body)
            lang = "en" if len(_EN_RE.findall(plain)) > len(_ID_RE.findall(plain)) else "id"
        found.setdefault(lang, body)
    return found


def _keyword_list(body: str) -> list[str]:
    match = _KEYWORDS_RE.search(body)
    if not match:
        return []
    return [k.strip(" .") for k in re.split(r"[,;]", _strip(match.group(1))) if k.strip(" .")]


def _numbers(body: str) -> set[str]:
    plain = _strip(_KEYWORDS_RE.sub(" ", body))
    out: set[str] = set()
    for raw in _NUMBER_RE.findall(plain):
        # 0,85 and 0.85 are one number; so are 1.500 and 1,500.
        value = raw.replace(",", ".").rstrip(".")
        if value:
            out.add(value)
    return out


def check_abstracts(
    text: str, *, layout: str = "", indonesian: bool = True
) -> tuple[dict[str, Any], list[tuple[str, str, str]]]:
    """Length against the profile, and the two abstracts against each other."""

    bodies = _abstracts(text)
    max_words, max_paragraphs = abstract_limits(layout)
    summary: dict[str, Any] = {"max_words": max_words, "max_paragraphs": max_paragraphs}
    issues: list[tuple[str, str, str]] = []
    names = {"id": "Abstrak", "en": "English abstract"}
    for lang, body in bodies.items():
        prose = _KEYWORDS_RE.sub(" ", body)
        words = len(re.findall(r"[A-Za-z\u00c0-\u024f0-9'-]+", _strip(prose)))
        paragraphs = len([p for p in re.split(r"\n\s*\n", prose) if _strip(p)])
        keywords = _keyword_list(body)
        summary[lang] = {"words": words, "paragraphs": paragraphs, "keywords": len(keywords)}
        if max_words and words > max_words:
            issues.append(("warning", f"the {names[lang]} has {words} words; the guide allows {max_words}",
                           "shorten it to the limit the campus guide sets"))
        if max_paragraphs and paragraphs > max_paragraphs:
            issues.append(("info", f"the {names[lang]} has {paragraphs} paragraphs; the guide allows {max_paragraphs}",
                           "merge paragraphs to the limit the campus guide sets"))
        if not keywords:
            issues.append(("info", f"the {names[lang]} has no keyword line",
                           "end it with 'Kata kunci:' or 'Keywords:' as the guide prescribes"))
    if "id" in bodies and "en" in bodies:
        id_kw, en_kw = summary["id"]["keywords"], summary["en"]["keywords"]
        if id_kw and en_kw and id_kw != en_kw:
            issues.append(("warning", f"the Abstrak has {id_kw} keywords but the English abstract {en_kw}",
                           "translate the same keywords, one for one"))
        only_id = sorted(_numbers(bodies["id"]) - _numbers(bodies["en"]))
        only_en = sorted(_numbers(bodies["en"]) - _numbers(bodies["id"]))
        summary["numbers_only_in_id"] = only_id[:10]
        summary["numbers_only_in_en"] = only_en[:10]
        if only_id or only_en:
            sample = ", ".join((only_id + only_en)[:5])
            issues.append(("warning", f"the two abstracts report different numbers ({sample})",
                           "make the English abstract a translation of the Abstrak, numbers included"))
    return summary, issues


# ------------------------------------------------------------------ floats
_FLOAT_RE = re.compile(r"\\begin\{(table|figure)\*?\}(.*?)\\end\{\1\*?\}", re.DOTALL)
_COUNTER_FLAT_RE = re.compile(
    r"\\counterwithout\*?\s*\{(figure|table)\}\s*\{chapter\}"
    r"|\\renewcommand\s*\{?\\the(figure|table)\}?\s*\{\s*\\arabic\s*\{\s*(?:figure|table)\s*\}\s*\}"
)
_REF_RE = re.compile(r"\\(?:ref|autoref|cref|Cref|vref)\s*\{([^{}]*)\}")


def check_floats(text: str) -> tuple[dict[str, Any], list[tuple[str, str, str]]]:
    """Caption placement, per-chapter numbering, and text references before the float."""

    issues: list[tuple[str, str, str]] = []
    misplaced: list[tuple[str, str]] = []
    late: list[str] = []
    refs: dict[str, int] = {}
    for match in _REF_RE.finditer(text):
        for key in match.group(1).split(","):
            refs.setdefault(key.strip(), match.start())
    floats = list(_FLOAT_RE.finditer(text))
    for index, match in enumerate(floats, start=1):
        kind, body = match.group(1), match.group(2)
        label = re.search(r"\\label\s*\{([^{}]*)\}", body)
        name = label.group(1) if label else f"{kind} {index}"
        caption = body.find("\\caption")
        content = re.search(r"\\begin\{(?:tabular|tabularx|longtable|tabulary)" if kind == "table"
                            else r"\\includegraphics|\\begin\{tikzpicture\}", body)
        if caption >= 0 and content and (
            (kind == "table" and caption > content.start())
            or (kind == "figure" and caption < content.start())
        ):
            misplaced.append((name, kind))
        if label and label.group(1) in refs and refs[label.group(1)] > match.start():
            late.append(name)
    for name, kind in misplaced[:6]:
        place = "below the table" if kind == "table" else "above the figure"
        issues.append(("warning", f"{name}: caption is {place}",
                       "put table captions above the table and figure captions below the figure"))
    if late:
        issues.append(("info", f"{len(late)} table(s)/figure(s) are first referenced after they appear "
                               f"({', '.join(late[:4])})",
                       "mention each table and figure in the text before it appears"))
    flat = sorted({m.group(1) or m.group(2) for m in _COUNTER_FLAT_RE.finditer(text)})
    for kind in flat:
        issues.append(("warning", f"{kind}s are numbered through the document, not per chapter",
                       f"keep the report class numbering ({'Tabel' if kind == 'table' else 'Gambar'} 3.1, 3.2)"))
    summary = {"floats": len(floats), "caption_misplaced": [name for name, _ in misplaced], "referenced_after": late,
               "numbered_through": flat}
    return summary, issues


# --------------------------------------------------------------- citations
_DECLARED_STYLE_RE = re.compile(
    r"\\bibliographystyle\s*\{([^}]+)\}|\\usepackage\s*\[([^\]]*)\]\s*\{biblatex\}"
)
_AUTHOR_YEAR_STYLES = re.compile(
    r"^(?:apa\w*|apalike|plainnat|abbrvnat|agsm|dcu|kluwer|chicago\w*|harvard\w*|authoryear\w*"
    r"|authortitle\w*|ext-authoryear\w*|apacite|elsarticle-harv|spbasic|mla\w*)$",
    re.IGNORECASE,
)
_NUMERIC_STYLES = re.compile(
    r"^(?:ieee\w*|plain|unsrt|abbrv|numeric\w*|vancouver|acm\w*|splncs\w*|elsarticle-num\w*"
    r"|nature|alpha|siam|ama|phys\w*|spmpsci)$",
    re.IGNORECASE,
)
_HAND_NUMERIC_RE = re.compile(r"(?<![\\\w])\[(?:\d{1,3})(?:\s*[,\u2013-]\s*\d{1,3})*\](?!\s*\{)")
_HAND_AUTHOR_YEAR_RE = re.compile(
    r"\([A-Z][A-Za-z'\-]+(?:\s+et\s+al\.?|\s+(?:&|and|dan)\s+[A-Z][A-Za-z'\-]+)?,\s*(?:19|20)\d\d[a-z]?(?:[;,][^)]*)?\)"
    r"|\b[A-Z][a-z'\-]+(?:\s+et\s+al\.?|\s+(?:&|and|dan)\s+[A-Z][a-z'\-]+)?\s+\((?:19|20)\d\d[a-z]?\)"
)
_NON_PROSE_RE = re.compile(
    r"\\begin\{(tabular\*?|table\*?|longtable|verbatim|lstlisting|equation\*?|align\*?|thebibliography)\}.*?\\end\{\1\}",
    re.DOTALL,
)


def style_family(name: str) -> str | None:
    """``author-year``, ``numeric`` or ``None`` for a style name or guide wording."""

    lowered = (name or "").lower()
    if not lowered:
        return None
    if re.search(r"\bapa\b|author[- ]?year|harvard|chicago|\bmla\b", lowered):
        return "author-year"
    if re.search(r"\bieee\b|numeric|numerik|vancouver|\bacm\b", lowered):
        return "numeric"
    return None


def _declared(text: str) -> tuple[str | None, str | None]:
    for match in _DECLARED_STYLE_RE.finditer(text):
        if match.group(1):
            name = match.group(1).strip()
        else:
            style = re.search(r"(?:^|,)\s*(?:bib)?style\s*=\s*([\w-]+)", match.group(2) or "")
            if not style:
                continue
            name = style.group(1)
        if _AUTHOR_YEAR_STYLES.match(name):
            return name, "author-year"
        if _NUMERIC_STYLES.match(name):
            return name, "numeric"
        return name, None
    return None, None


def check_citation_style(
    text: str, *, expected: str = ""
) -> tuple[dict[str, Any], list[tuple[str, str, str]]]:
    """The declared and hand-written citation styles against the guide's."""

    want = style_family(expected)
    declared_name, declared = _declared(text)
    body = text[text.find("\\begin{document}"):] if "\\begin{document}" in text else text
    prose = _NON_PROSE_RE.sub(" ", re.sub(r"(?<!\\)%.*$", " ", body, flags=re.M))
    numeric = len(_HAND_NUMERIC_RE.findall(prose))
    author_year = len(_HAND_AUTHOR_YEAR_RE.findall(prose))
    issues: list[tuple[str, str, str]] = []
    if want and declared and declared != want:
        issues.append(("warning", f"bibliography style '{declared_name}' is {declared}; the guide asks for {want}",
                       f"switch to an {want} style ({'apalike or biblatex-apa' if want == 'author-year' else 'IEEEtran'})"))
    if numeric >= 2 and author_year >= 2:
        issues.append(("warning", f"citations mix numeric [n] ({numeric}) and author-year ({author_year}) forms",
                       "use one citation style throughout, through \\cite rather than typed citations"))
    elif want:
        wrong = numeric if want == "author-year" else author_year
        if wrong >= 2 and (declared is None or declared == want):
            other = "numeric [n]" if want == "author-year" else "author-year"
            issues.append(("warning", f"{wrong} typed {other} citations; the guide asks for {want}",
                           "cite through \\cite with the guide's style"))
    summary = {"expected": want, "declared_style": declared_name, "declared": declared,
               "typed_numeric": numeric, "typed_author_year": author_year}
    return summary, issues


__all__ = [
    "abstract_limits",
    "check_abstracts",
    "check_citation_style",
    "check_floats",
    "list_items",
    "style_family",
    "trace_research_questions",
]

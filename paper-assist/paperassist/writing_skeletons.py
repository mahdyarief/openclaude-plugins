"""LaTeX skeletons for paper and thesis packs, including the protected blocks."""

from __future__ import annotations

from .writing_content import (
    THESIS_BARE_SECTIONS,
    THESIS_PROPOSAL_SECTIONS,
    _document_kind,
    _slug,
    _thesis_stage,
)


def _declarations_block() -> str:
    from .protected_blocks import PROTECTED_END, PROTECTED_START

    # Author-owned and protected: the harness can neither write nor alter these
    # statements. They stay commented until the authors fill them in, so the
    # quality audit reports them missing rather than accepting a template.
    return (
        f"{PROTECTED_START}\n"
        "% Declarations: author-owned, filled in by the authors before submission.\n"
        "% Uncomment and complete what the target journal requires.\n"
        "% \\section*{Declarations}\n"
        "% \\paragraph{Competing interests} The authors declare ...\n"
        "% \\paragraph{Funding} This work was supported by ... (grant ...).\n"
        "% \\paragraph{Data availability} The data are available at ...\n"
        "% \\paragraph{Author contributions (CRediT)} A: Conceptualization, ...\n"
        "% \\paragraph{Use of generative AI} During the preparation of this work the\n"
        "%   authors used [tool] for [purpose]. The authors reviewed and edited the\n"
        "%   content and take full responsibility for it.\n"
        f"{PROTECTED_END}\n"
    )


_DECLARATIONS_BLOCK = _declarations_block()


def _method_outline_comment(research_design: str | None) -> str:
    """Suggested Method subsections for ``research_design``, as LaTeX comments.

    They are comments, not headings: the Method task replaces its TODO marker,
    and empty headings left below the drafted prose would only be noise. The
    agent sees the outline here and in its brief, and writes the subsections.
    """

    if research_design in (None, "", "auto"):
        return ""
    from .research_designs import get_design

    design = get_design(str(research_design))
    if not design.method_outline:
        return ""
    lines = [f"% Suggested subsections ({design.guideline}):"]
    lines += [f"%   - {name}" for name in design.method_outline]
    return "\n".join(lines) + "\n"


def _skeleton(title: str, protected_body: str = "", research_design: str | None = None) -> str:
    safe_title = str(title or "").strip() or "Untitled Research Manuscript"
    from .protected_blocks import PROTECTED_END, PROTECTED_START

    protected = (
        f"{PROTECTED_START}\n"
        f"{protected_body or '% Author-supplied experimental setup and results remain unchanged.'}\n"
        f"{PROTECTED_END}\n"
    )
    return (
        "\\documentclass{article}\n"
        "\\usepackage[T1]{fontenc}\n"
        "\\usepackage{graphicx}\n"
        "\\title{" + safe_title + "}\n"
        "\\author{}\n"
        "\\date{}\n"
        "\\begin{document}\n"
        "\\maketitle\n"
        "\\begin{abstract}\n"
        "% TODO(agent): title-and-abstract\n"
        "\\end{abstract}\n"
        "\\section{Introduction}\n"
        "% TODO(agent): section-introduction\n"
        "\\section{Related Work}\n"
        "% TODO(agent): section-related-work\n"
        "\\section{Background}\n"
        "% TODO(agent): section-background\n"
        "\\section{Method}\n"
        "% TODO(agent): section-method\n"
        + _method_outline_comment(research_design)
        + protected
        + "\\section{Discussion}\n"
        "% TODO(agent): section-discussion\n"
        "\\section{Limitations}\n"
        "% TODO(agent): section-limitations\n"
        "\\section{Conclusion}\n"
        "% TODO(agent): section-conclusion\n"
        + _DECLARATIONS_BLOCK
        + "\\bibliographystyle{plain}\n"
        "\\bibliography{references}\n"
        "\\end{document}\n"
    )


def skeleton_document(
    title: str, protected_body: str = "", research_design: str | None = None
) -> str:
    return _skeleton(title, protected_body, research_design)


_THESIS_CHAPTER_ONE_OUTLINE = (
    "% Suggested subsections (pedoman tesis umum):\n"
    "%   - Latar Belakang\n"
    "%   - Rumusan Masalah (satu butir per pertanyaan penelitian)\n"
    "%   - Tujuan Penelitian (satu tujuan per rumusan masalah, urutan sama)\n"
    "%   - Manfaat Penelitian\n"
    "%   - Batasan Masalah\n"
    "%   - Sistematika Penulisan"
)
_THESIS_CLOSING_OUTLINE = (
    "% Suggested subsections:\n"
    "%   - Kesimpulan (jawab setiap rumusan masalah, satu butir masing-masing)\n"
    "%   - Keterbatasan Penelitian\n"
    "%   - Saran"
)
_PROPOSAL_SCHEDULE_OUTLINE = (
    "\n%   - Jadwal Penelitian (tahapan dan waktu pelaksanaan)"
)
_DEFAULT_THESIS_PREAMBLE = (
    "\\documentclass[12pt]{report}\n"
    "\\usepackage[T1]{fontenc}\n"
    "\\usepackage[indonesian]{babel}\n"
    "\\usepackage{graphicx}\n"
)


def _thesis_preamble(profile_id: str | None) -> str:
    """The campus profile's preamble, or the generic report preamble."""

    if not profile_id or str(profile_id).strip().lower() in ("", "auto", "none"):
        return _DEFAULT_THESIS_PREAMBLE
    from .thesis_profiles import thesis_profile

    preamble = thesis_profile(str(profile_id).strip()).latex_preamble.rstrip("\n") + "\n"
    if "{graphicx}" not in preamble:
        preamble += "\\usepackage{graphicx}\n"
    return preamble


def _thesis_skeleton(
    title: str,
    *,
    thesis_type: str = "thesis",
    protected_body: str = "",
    research_design: str | None = None,
    thesis_profile_id: str | None = None,
    thesis_stage: str = "final",
) -> str:
    """Generic thesis skeleton (document_kind="thesis").

    ``thesis_stage="proposal"`` gives the seminar-proposal document: Chapters
    1-3, an approval page and a research schedule in the method outline.

    The structure is intentionally institution/language agnostic: front matter,
    chapter headings, and a generic bibliography. It generalises from common
    thesis conventions (illustrated by the Telkom S2 example the user supplied)
    without depending on any single template.
    """

    safe_title = str(title or "").strip() or "Judul Tesis"
    from .protected_blocks import PROTECTED_END, PROTECTED_START

    protected = (
        f"{PROTECTED_START}\n"
        f"{protected_body or '% Data/eksperimen yang disediakan penulis tetap tidak berubah.'}\n"
        f"{PROTECTED_END}\n"
    )
    outline = _method_outline_comment(research_design).rstrip("\n")

    proposal = thesis_stage == "proposal"

    def chapter_outline(name: str) -> str:
        lowered = name.lower()
        if "metod" in lowered:
            return outline + (_PROPOSAL_SCHEDULE_OUTLINE if proposal else "")
        if "pendahuluan" in lowered:
            return _THESIS_CHAPTER_ONE_OUTLINE
        if "kesimpulan" in lowered:
            return _THESIS_CLOSING_OUTLINE
        return ""

    chapter_block = "\n".join(
        f"\\chapter{{{name}}}\\label{{ch:{_slug(name)}}}\n% TODO(agent): section-{_slug(name)}"
        + (f"\n{chapter_outline(name).lstrip(chr(10))}" if chapter_outline(name) else "")
        for name in (THESIS_PROPOSAL_SECTIONS if proposal else THESIS_BARE_SECTIONS)
    )
    preamble = _thesis_preamble(thesis_profile_id)
    type_note = {
        "skripsi": "Skripsi (Sarjana)",
        "tesis": "Tesis (Magister)",
        "disertasi": "Disertasi (Doktor)",
    }.get(thesis_type, "Tesis")
    if proposal:
        type_note = "Proposal " + type_note
    # Author-owned pages: signatures and a signed statement, never written by
    # the harness. Research OS checks that they exist.
    author_pages = (
        "\\chapter*{Lembar Persetujuan}\n"
        "% Diisi penulis: persetujuan pembimbing untuk seminar proposal.\n"
        if proposal
        else "\\chapter*{Lembar Pengesahan}\n"
        "% Diisi penulis: nama, NIM, judul, tanda tangan pembimbing dan penguji.\n"
        "\\chapter*{Pernyataan Keaslian}\n"
        "% Diisi penulis: pernyataan bahwa karya ini asli dan bebas plagiarisme, bertanda tangan.\n"
        "\\chapter*{Kata Pengantar}\n"
        "% Diisi penulis.\n"
    )
    english_abstract = (
        ""
        if proposal
        else "\\chapter*{Abstract}\n"
        "% English abstract: terjemahan makna Abstrak, diisi setelah Abstrak final.\n"
    )
    return (
        preamble
        + "\\title{" + safe_title + "}\n"
        "\\author{}\n"
        "\\date{}\n"
        "\\begin{document}\n"
        "\\begin{titlepage}\n"
        f"% {type_note} -- judul, nama penulis, dan lembar pengesahan diisi sesuai pedoman kampus.\n"
        "\\maketitle\n"
        "\\end{titlepage}\n"
        + author_pages
        + "\\begin{abstract}\n"
        "% TODO(agent): abstract\n"
        "\\end{abstract}\n"
        + english_abstract
        + "\\tableofcontents\n"
        "\\listoffigures\n"
        "\\listoftables\n"
        + chapter_block
        + "\n"
        + protected
        + "\\bibliographystyle{plain}\n"
        "\\bibliography{references}\n"
        "\\end{document}\n"
    )


def skeleton_document_kind(
    title: str,
    *,
    document_kind: str = "paper",
    thesis_type: str = "thesis",
    protected_body: str = "",
    research_design: str | None = None,
    thesis_profile_id: str | None = None,
    thesis_stage: str = "final",
) -> str:
    """Dispatch skeleton by document kind; thesis uses the chapter scaffold."""

    if _document_kind({"document_kind": document_kind}) == "thesis":
        return _thesis_skeleton(
            title,
            thesis_type=thesis_type,
            protected_body=protected_body,
            research_design=research_design,
            thesis_profile_id=thesis_profile_id,
            thesis_stage=_thesis_stage({"thesis_stage": thesis_stage, "thesis_type": thesis_type}),
        )
    return _skeleton(title, protected_body, research_design)

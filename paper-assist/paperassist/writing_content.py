"""Writing-pack content: schemas, section lists, depth profiles, briefs and acceptance rules."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

WRITING_PACK_SCHEMA = "paperassist.writing-pack/v1"


WRITING_TASK_SCHEMA = "paperassist.writing-task/v1"


WRITING_PACK_ROOT = ".paperassist/writing"


WRITING_PLAN_FILENAME = "plan.json"


WRITING_BRIEF_FILENAME = "agent-brief.md"


WRITING_DRAFT_FILENAME = "draft.tex"


WRITING_CITATIONS_FILENAME = "citations.json"


WRITING_REFERENCES_FILENAME = "references.json"


WRITING_SOURCE_FILENAME = "source.tex"


WRITING_CONTEXT_FILENAME = "context.json"


WRITING_CONTEXT_BRIEF_FILENAME = "context-brief.md"


WRITING_TASKS_DIRNAME = "tasks"


DEPTH_LEVELS = ("shallow", "standard", "deep")


DEFAULT_DEPTH = "standard"


# Depth controls how much scaffolding the harness receives per section. It is a
# generic policy: the same levels apply to any document kind or topic.
DEPTH_PROFILES: dict[str, dict[str, Any]] = {
    "shallow": {
        "min_words_per_section": 250,
        "require_evidence_tasks": False,
        "require_provenance_task": False,
        "require_argument_map": False,
        "cite_rounds_cap": 1,
    },
    "standard": {
        "min_words_per_section": 500,
        "require_evidence_tasks": False,
        "require_provenance_task": True,
        "require_argument_map": False,
        "cite_rounds_cap": 3,
    },
    "deep": {
        "min_words_per_section": 900,
        "require_evidence_tasks": True,
        "require_provenance_task": True,
        "require_argument_map": True,
        "cite_rounds_cap": 5,
    },
}


DEFAULT_SECTIONS = (
    "Introduction",
    "Background",
    "Method",
    "Experimental Setup",
    "Results",
    "Discussion",
    "Limitations",
    "Conclusion",
)


# Experimental Setup and Results are author-owned: they live inside the
# protected experiment block, and the import gate rejects new results outside
# it. Paper packs therefore skip them by default; the Discussion restates them.
EXPERIMENTAL_SECTIONS = frozenset({"Experimental Setup", "Results"})


REFINE_SECTIONS = (
    "Abstract",
    "Related Work",
    *DEFAULT_SECTIONS,
)


# Generic thesis mode (document_kind="thesis"). The chapter list is intentionally
# institution/topic agnostic and fully overridable via payload["sections"]; what
# follows is a sensible default for a local-language thesis (e.g. Indonesia).
THESIS_DEFAULT_SECTIONS: tuple[str, ...] = (
    "Pendahuluan",
    "Tinjauan Pustaka",
    "Metodologi Penelitian",
    "Hasil dan Pembahasan",
    "Kesimpulan dan Saran",
)


# A thesis proposal (seminar proposal) carries Chapters 1-3 only.
THESIS_PROPOSAL_SECTIONS: tuple[str, ...] = (
    "Pendahuluan",
    "Tinjauan Pustaka",
    "Metodologi Penelitian",
)


THESIS_BARE_SECTIONS: tuple[str, ...] = (
    "Abstrak",
    "Pendahuluan",
    "Tinjauan Pustaka",
    "Metodologi Penelitian",
    "Hasil dan Pembahasan",
    "Kesimpulan dan Saran",
)


SECTION_BRIEFS: dict[str, str] = {
    "Abstract": """
- TL;DR of the paper
- What are we trying to do and why is it relevant?
- Why is this hard?
- How do we solve it (i.e. our contribution)?
- How do we verify that we solved it (e.g. Experiments and results)

One continuous paragraph, no line breaks inside the abstract.
""",
    "Introduction": """
- Longer version of the Abstract, i.e. of the entire paper
- What are we trying to do and why is it relevant?
- Why is this hard?
- How do we solve it (i.e. our contribution)?
- How do we verify that we solved it (e.g. Experiments and results)?
- List the contributions as bullet points
- Extra space? Future work.
""",
    "Related Work": """
- Academic siblings of our work: alternative attempts at the same problem.
- Compare and contrast: how does each approach differ in assumptions or method?
- Describing another paper is not enough; state why a method applies or not.
- Only discuss the most relevant work; keep the section concise.
""",
    "Background": """
- Academic ancestors: concepts and prior work required to understand the method.
- Usually includes a Problem Setting subsection with notation and assumptions.
- If the paper introduces a novel problem setting, give it its own section.
""",
    "Method": """
- What we do and why, using the formalism introduced in the Problem Setting
  and building on the Background concepts.
""",
    "Experimental Setup": """
- Author-owned: written inside the protected experiment block, not by the harness.
- How the claims are tested: dataset, metrics, hyperparameters, implementation.
- Do not invent hardware details.
""",
    "Results": """
- Author-owned: written inside the protected experiment block, not by the harness.
- Only results that were actually run and saved in notes/logs; never invent.
- Compare against baselines with statistics and confidence intervals.
""",
    "Discussion": """
- Interpret the results in the protected experiment block: what they mean for
  the research question and how they compare with the cited prior work.
- Restate a number only if it appears verbatim in the protected block; otherwise
  refer to its tables and figures with \\ref. New numbers are rejected.
- Separate what the results show from what they suggest.
""",
    "Limitations": """
- Threats to internal, external and construct validity of this specific study.
- What the data, sample, metrics or setting cannot support; no generic caveats.
- How future work could remove each limitation.
""",
    "Conclusion": """
- Brief recap of the entire paper.
- Future work as the natural continuation of the presented results.
""",
    # --- Generic thesis chapters (document_kind="thesis") -------------------
    # Naming follows a common local-thesis convention; the guidance is
    # topic- and institution-agnostic so it generalises beyond one example.
    "Abstrak": """
- Nyatakan latar belakang, tujuan/pertanyaan penelitian, pendekatan/metodologi, temuan utama, dan implikasinya.
- Gunakan bahasa ringkas dan informatif; jangan menyisipkan hasil atau angka yang tidak ada dalam draf/sumber.
- Jaga konsistensi dengan abstrak bahasa Inggris bila ada; terjemahkan makna, bukan kata per kata.
""",
    "Pendahuluan": """
- Mulai dari konteks umum lalu persempit ke fokus penelitian.
- Rumuskan masalah/pertanyaan, tujuan, ruang lingkup/batasan, serta kontribusi atau manfaat secara proporsional.
- Akhiri dengan sistematika penulisan bila relevan; hindari klaim tanpa dukungan bukti.
""",
    "Tinjauan Pustaka": """
- Sintesis konsep, teori, dan studi terdahulu yang relevan; kelompokkan berdasarkan tema/pendekatan, bukan per makalah.
- Bandingkan temuan, metode, dan keterbatasan studi sebelumnya untuk memposisikan penelitian ini.
- Identifikasi celah (gap) penelitian secara eksplisit; gunakan hanya sitasi dari daftar yang diizinkan.
""",
    "Metodologi Penelitian": """
- Jelaskan desain/pendekatan, objek/data/sumber, prosedur, instrumen, dan teknik analisis secara runtut.
- Nyatakan asumsi, parameter, dan alasan pemilihan metode; pisahkan desain dari hasil.
- Sertakan validitas, etika, atau keterbatasan metodologis bila relevan, tanpa mengarang detail pelaksanaan.
""",
    "Hasil dan Pembahasan": """
- Sajikan temuan dari bukti yang tersedia dalam draf/data/protected block; jangan mengarang angka atau eksperimen.
- Bahas makna temuan, kaitkan dengan tujuan/pertanyaan penelitian dan literatur, lalu jelaskan keterbatasan.
- Bedakan fakta temuan dari interpretasi/implikasi.
""",
    "Kesimpulan dan Saran": """
- Ringkas jawaban atas tujuan/pertanyaan penelitian dari temuan yang didukung draf.
- Nyatakan keterbatasan secara jujur; berikan saran/pekerjaan lanjut yang konkret dan realistis.
- Jangan menambah klaim, hasil, atau generalisasi baru yang tidak didukung.
""",
}


ERROR_LIST = """- Unenclosed math symbols
- Only reference figures that exist in the workspace
- LaTeX syntax errors
- Numerical results that do not come from explicit experiments and logs
- Repeatedly defined figure labels
- References that are not in the bibliography; do not invent citations
- Unnecessary verbosity, repetition, or unclear text
- Notes content that has not been included yet
- Relevant figures that have not been included in the text
- Mismatched \\begin{...} / \\end{...} pairs
- Duplicate headers or \\end{document}
- Unescaped specials such as shakespeare\\_char
"""


REFINEMENT_INSTRUCTIONS = (
    "Criticize and refine only the {section} that was just written. Make this "
    "complete in one pass; do not leave placeholders.\n\nPay particular "
    "attention to fixing any errors such as:\n" + ERROR_LIST
)


# WritingEngine._validate_candidate enforces these mechanically: complete
# document, byte-identical protected blocks, results outside the protected block
# only when it backs them, allowed citation keys, no unsafe TeX or includes, no
# secrets, and no chat-assistant residue. "Nothing invented" beyond that is a
# review rule the Research OS audit checks afterwards.
ACCEPTANCE_RULES: tuple[str, ...] = (
    "The returned document is one complete LaTeX document.",
    "Every PAPERASSIST protected block (experiment and declarations) is preserved byte-for-byte.",
    "No experiment, metric, hardware detail, or comparison is invented; a number "
    "outside the protected block must already appear inside it.",
    "Only citation keys present in the allowed list are used.",
    "No shell commands, file includes, or new bibliography entries are added.",
    "No secret-like content, chat-assistant residue, or writing-process narration "
    "in the prose; AI-use, funding, competing-interest, data-availability and "
    "contribution statements belong to the author-owned Declarations block.",
)


class WritingPackError(RuntimeError):
    pass


def _slug(value: object) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return cleaned or "untitled"


def _document_kind(payload: Mapping[str, Any]) -> str:
    """Resolve the document kind from payload, defaulting to a journal paper.

    Only ``"thesis"`` is special-cased; anything else falls back to the paper
    scaffold. This keeps the mode general and avoids locking behaviour to one
    institution, language, or example document.
    """

    kind = str(payload.get("document_kind") or "").strip().lower()
    if kind in {"thesis", "tesis", "dissertation", "disertasi", "skripsi"}:
        return "thesis"
    return "paper"


def _thesis_stage(payload: Mapping[str, Any]) -> str:
    """``proposal`` when the payload asks for a thesis proposal, else ``final``."""

    stage = str(payload.get("thesis_stage") or "").strip().lower()
    thesis_type = str(payload.get("thesis_type") or "").strip().lower()
    if stage in {"proposal", "usulan", "seminar proposal"} or thesis_type == "proposal":
        return "proposal"
    return "final"


# Chapter -> section label used in the working skeleton. This mapping is the
# single place where the generic thesis framework names its structure; override
# by passing payload["sections"].
_THESIS_CHAPTER_SECTIONS: dict[str, str] = {
    "Pendahuluan": "section-pendahuluan",
    "Tinjauan Pustaka": "section-tinjauan-pustaka",
    "Metodologi Penelitian": "section-metodologi-penelitian",
    "Hasil dan Pembahasan": "section-hasil-dan-pembahasan",
    "Kesimpulan dan Saran": "section-kesimpulan-dan-saran",
}


def _simplify_thesis_section(section: str) -> str:
    """Lower, slugify, and strip non-alphanumerics from a chapter name.

    Keeps the generic framework usable regardless of the language or naming a
    given campus uses: callers pass their own chapter titles via
    payload["sections"] and this produces a stable task id.
    """

    return re.sub(r"[^a-z0-9]+", "-", section.strip().lower()).strip("-")


def _depth_profile(payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    raw = str(payload.get("depth") or DEFAULT_DEPTH).strip().lower()
    level = raw if raw in DEPTH_PROFILES else DEFAULT_DEPTH
    profile = dict(DEPTH_PROFILES[level])
    override = payload.get("min_words_per_section")
    if isinstance(override, int) and not isinstance(override, bool) and override > 0:
        profile["min_words_per_section"] = override
    return level, profile


_EM_DASH_RULE = (
    "- Prose style: never use an em dash (---, \\textemdash, or the character). "
    "Use a comma, a colon, a semicolon, or a full stop instead. An en dash (--) "
    "is allowed only inside a numeric range such as 2015--2026."
)


_INDONESIAN_STYLE_RULE = (
    "- Gaya bahasa Indonesia: hindari pembuka generik dan kalimat pengisi, "
    "misalnya \"dalam dunia yang semakin...\", \"di era digital\", "
    "\"tidak dapat dipungkiri\", \"perlu diingat bahwa\", "
    "\"memainkan peran penting\", dan \"secara komprehensif dapat disimpulkan\". "
    "Ganti dengan klaim yang spesifik dan dapat dirujuk. Pertahankan istilah "
    "teknis baku; jangan menghindari kata akademik yang memang diperlukan "
    "hanya karena terdengar umum. Jangan menyisipkan penanda Markdown seperti "
    "**tebal** di dalam naskah LaTeX."
)


def _prose_style_rule(allow_em_dash: bool) -> str:
    rules = [_INDONESIAN_STYLE_RULE]
    if not allow_em_dash:
        rules.append(_EM_DASH_RULE)
    return "\n" + "\n".join(rules)


def _as_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if value is None:
        return default
    return default

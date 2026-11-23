"""Deterministic reporting checks that sit beside the quality dimensions.

Each check here answers one question a journal editor or reviewer asks before
reading the argument, and each is grounded in a published reporting standard:

* paper type: which reporting standard applies at all (an empirical study is
  not judged on its search strategy, a review is not judged on hyperparameters);
* PRISMA 2020 flow arithmetic: the counts in the flow diagram must add up
  (identified minus removed equals screened, and so on down to included);
* declarations: competing interests, funding, data availability, author
  contributions (CRediT, ANSI/NISO Z39.104-2022) and AI-use disclosure
  (ICMJE Recommendations, COPE position on authorship and AI tools);
* references: recency, share of primary literature, and citations of retracted
  work against a locally supplied Retraction Watch export;
* locator quotes: whether a ``@locator`` quote really occurs in the bound full
  text of the cited work.

Nothing here performs network access or calls a model. Thresholds are
parameters, not facts: journals and accreditation rubrics differ, so every
default can be overridden by the caller.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .research_designs import ResearchDesign

# "conceptual" covers methodological essays, guides, editorials and position
# papers: no data of their own, so no Method section and no ethics or code.
PAPER_TYPES = ("empirical", "review", "conceptual")

_REVIEW_RE = re.compile(
    r"systematic (?:literature )?review|scoping review|meta-analy|mapping study|"
    r"tinjauan (?:literatur(?:e)? )?sistematis|kajian (?:literatur )?sistematis|"
    r"\bslr\b|\bprisma\b|bibliometri|scientometri|vosviewer|bibliometrix|"
    # Not "critical review": empirical introductions say "a critical review of
    # existing literature reveals ...".
    r"narrative review|integrative review|curated review|"
    r"state[- ]of[- ]the[- ]art review|kajian naratif|tinjauan naratif",
    re.IGNORECASE,
)


_QUESTIONNAIRE_RE = re.compile(
    r"questionnaire|kuesioner|angket|respondent|responden|likert", re.IGNORECASE
)


_ELIGIBILITY_RE = re.compile(
    r"inclusion criteria|exclusion criteria|eligibility criteria|kriteria inklusi|"
    r"kriteria eksklusi|inklusi|eksklusi",
    re.IGNORECASE,
)


def detect_paper_type(text: str, *, study_count: int = 0) -> str:
    """``review`` when the manuscript synthesises studies, else ``empirical``."""

    if study_count > 0:
        return "review"
    from .research_designs import LITERATURE_SURVEY_RE, article_type_label, detection_text

    # An essay, guide or editorial says what it is near its title.
    if article_type_label(text):
        return "conceptual"
    head = detection_text(text)
    mentions = len(_REVIEW_RE.findall(head))
    # "A Survey on X" is a literature review unless the paper has respondents.
    if len(_QUESTIONNAIRE_RE.findall(head)) < 2:
        mentions += len(LITERATURE_SURVEY_RE.findall(head))
    if mentions >= 2:
        return "review"
    # One review marker plus eligibility criteria is a review's method.
    if mentions == 1 and _ELIGIBILITY_RE.search(head):
        return "review"
    return "empirical"


def resolve_paper_type(value: str | None, text: str, *, study_count: int = 0) -> str:
    """The design family, ``review`` or ``empirical``.

    ``value`` may also name a specific research design (``rct``, ``ptk``,
    ``scoping_review``...); its family is returned.
    """

    choice = str(value or "auto").strip().lower()
    aliases = {"slr": "review", "systematic-review": "review", "experimental": "empirical"}
    choice = aliases.get(choice, choice)
    if choice == "auto":
        return detect_paper_type(text, study_count=study_count)
    if choice in PAPER_TYPES:
        return choice
    from .research_designs import get_design

    try:
        return get_design(choice).family
    except ValueError:
        raise ValueError(
            f"paper_type must be auto, {', '.join(PAPER_TYPES)} or a research design key"
        ) from None


def resolve_research_design(
    value: str | None,
    text: str,
    *,
    study_count: int = 0,
    paper_type: str | None = "auto",
) -> ResearchDesign:
    """The research design whose reporting standard applies.

    An explicit ``value`` wins. Otherwise ``paper_type`` (which may itself be a
    design key) fixes the family, and the most specific design of that family
    the manuscript names is chosen; without one, the family's general design
    (systematic review or general empirical study) applies.
    """

    from .research_designs import detect_research_design, get_design

    choice = str(value or "auto").strip().lower()
    if choice not in ("", "auto"):
        return get_design(choice)
    type_choice = str(paper_type or "auto").strip().lower()
    if type_choice not in ("", "auto", *PAPER_TYPES, "slr", "systematic-review", "experimental"):
        return get_design(type_choice)
    family = resolve_paper_type(paper_type, text, study_count=study_count)
    return get_design(detect_research_design(text, family=family))


# --------------------------------------------------------------------------
# PRISMA 2020 flow arithmetic
# --------------------------------------------------------------------------

# Canonical flow fields and the key names accepted for each. Keys are matched
# after lower-casing and replacing every non-alphanumeric run with ``_``.
_FLOW_FIELDS: dict[str, tuple[str, ...]] = {
    "identified": ("identified", "records_identified", "total_identified",
                   "identified_total", "n_identified", "records_total"),
    "duplicates_removed": ("duplicates_removed", "duplicates", "duplicate_records_removed",
                           "records_removed_duplicates", "removed_duplicates"),
    "automation_removed": ("automation_removed", "automation_excluded",
                           "records_marked_ineligible_by_automation", "removed_automation"),
    "other_removed": ("other_removed", "removed_other_reasons", "records_removed_other"),
    "screened": ("screened", "records_screened", "n_screened", "title_abstract_screened"),
    "excluded_screening": ("excluded_screening", "records_excluded", "screening_excluded",
                           "excluded_title_abstract", "title_abstract_excluded"),
    "sought": ("sought", "reports_sought", "reports_sought_for_retrieval",
               "sought_for_retrieval"),
    "not_retrieved": ("not_retrieved", "reports_not_retrieved"),
    "assessed": ("assessed", "reports_assessed", "assessed_for_eligibility",
                 "full_text_assessed", "fulltext_assessed", "eligibility_assessed"),
    "excluded_fulltext": ("excluded_fulltext", "reports_excluded", "full_text_excluded",
                          "fulltext_excluded", "excluded_eligibility"),
    "included": ("included", "studies_included", "included_studies", "n_included",
                 "total_included", "reports_included"),
}
# Dict-valued breakdowns that must sum to a canonical field.
_FLOW_BREAKDOWNS: dict[str, tuple[str, ...]] = {
    "identified": ("identified_by_database", "identified_by_source", "databases", "sources"),
    "excluded_fulltext": ("exclusion_reasons", "reports_excluded_reasons",
                          "excluded_reasons", "full_text_exclusion_reasons"),
}

# Each identity: (name, target field, minuend, subtrahends).
_FLOW_IDENTITIES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("identification", "screened", "identified",
     ("duplicates_removed", "automation_removed", "other_removed")),
    ("screening", "sought", "screened", ("excluded_screening",)),
    ("retrieval", "assessed", "sought", ("not_retrieved",)),
    ("eligibility", "included", "assessed", ("excluded_fulltext",)),
)


def _norm_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\s*\d[\d.,]*\s*", value):
        digits = re.sub(r"[.,\s]", "", value)
        return int(digits) if digits else None
    return None


def _flatten(node: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(node, Mapping):
        for key, value in node.items():
            name = _norm_key(key)
            if name.startswith("_"):
                continue
            path = f"{prefix}.{name}" if prefix else name
            yield path, value
            yield from _flatten(value, path)


@dataclass(frozen=True)
class FlowIdentity:
    name: str
    expected: int
    reported: int
    formula: str
    # "=" : reported must equal expected; "<=" : reported may not exceed it
    # (nobody can be analysed who was never allocated).
    relation: str = "="

    @property
    def passed(self) -> bool:
        if self.relation == "<=":
            return self.reported <= self.expected
        return self.expected == self.reported

    def describe(self) -> str:
        if self.relation == "<=":
            return f"{self.name}: reported {self.reported} exceeds {self.formula} = {self.expected}"
        return f"{self.name}: {self.formula} = {self.expected}, reported {self.reported}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "formula": self.formula,
            "relation": self.relation,
            "expected": self.expected,
            "reported": self.reported,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class FlowCheck:
    fields: Mapping[str, int] = field(default_factory=dict)
    identities: tuple[FlowIdentity, ...] = ()
    unchecked: tuple[str, ...] = ()
    # Which diagram the counts belong to: "prisma", "consort" or "strobe".
    kind: str = "prisma"

    @property
    def available(self) -> bool:
        return bool(self.fields)

    @property
    def passed(self) -> bool:
        return all(identity.passed for identity in self.identities)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "available": self.available,
            "passed": self.passed,
            "fields": dict(self.fields),
            "identities": [identity.to_dict() for identity in self.identities],
            "unchecked": list(self.unchecked),
        }


def check_prisma_flow(documents: Sequence[Mapping[str, Any]]) -> FlowCheck:
    """Check PRISMA 2020 flow-diagram arithmetic in count documents.

    Only identities whose every term is reported are checked; the others are
    listed as ``unchecked`` rather than guessed. A missing optional removal
    (automation, other reasons) counts as zero once the identity's mandatory
    terms are present.
    """

    values: dict[str, int] = {}
    breakdowns: dict[str, int] = {}
    for document in documents:
        for path, value in _flatten(document):
            leaf = path.rsplit(".", 1)[-1]
            for canonical, names in _FLOW_FIELDS.items():
                number = _as_int(value)
                if number is not None and (leaf in names or path in names):
                    values.setdefault(canonical, number)
            for canonical, names in _FLOW_BREAKDOWNS.items():
                if leaf in names and isinstance(value, Mapping):
                    parts = [_as_int(item) for item in value.values()]
                    if parts and all(part is not None for part in parts):
                        breakdowns.setdefault(canonical, sum(p for p in parts if p is not None))
    identities: list[FlowIdentity] = []
    unchecked: list[str] = []
    optional = {"automation_removed", "other_removed"}
    for name, target, minuend, subtrahends in _FLOW_IDENTITIES:
        mandatory = [target, minuend, *(s for s in subtrahends if s not in optional)]
        if not all(term in values for term in mandatory):
            unchecked.append(name)
            continue
        expected = values[minuend] - sum(values.get(term, 0) for term in subtrahends)
        formula = f"{minuend} - " + " - ".join(
            term for term in subtrahends if term in values
        )
        identities.append(
            FlowIdentity(name=name, expected=expected, reported=values[target], formula=formula)
        )
    for canonical, total in breakdowns.items():
        if canonical in values:
            identities.append(
                FlowIdentity(
                    name=f"{canonical}_breakdown",
                    expected=total,
                    reported=values[canonical],
                    formula=f"sum of {canonical} breakdown",
                )
            )
    return FlowCheck(fields=values, identities=tuple(identities), unchecked=tuple(unchecked))


# --------------------------------------------------------------------------
# Declarations
# --------------------------------------------------------------------------

DECLARATION_PATTERNS: dict[str, str] = {
    "data_availability": (
        r"data availability|availability of data|ketersediaan data|"
        r"data (?:are|is) (?:publicly |openly )?available|data tersedia|dataset tersedia"
    ),
    "code_availability": (
        r"code availability|source code (?:is )?available|kode(?: sumber)? tersedia|"
        r"github\.com|gitlab\.com|zenodo|software availability"
    ),
    "competing_interests": (
        r"competing interests?|conflicts? of interests?|declaration of interests?|"
        r"konflik kepentingan|benturan kepentingan"
    ),
    "funding": (
        r"\bfunding\b|\bfunded\b|\bgrant\b|pendanaan|didanai|\bhibah\b|"
        r"tidak menerima (?:dana|pendanaan)|received no (?:specific )?funding"
    ),
    "author_contributions": (
        r"author contributions?|credit authorship|kontribusi penulis|"
        r"conceptuali[sz]ation|konseptualisasi|writing\s*[-–—]\s*original draft"
    ),
    "ai_use": (
        r"generative (?:ai|artificial intelligence)|ai[- ]assisted|"
        r"(?:use|usage) of (?:ai|artificial intelligence|large language models?)|"
        r"penggunaan (?:ai|kecerdasan (?:buatan|artifisial))|large language model|"
        r"\bllms?\b|chatgpt|\bclaude\b|copilot|no (?:generative )?ai (?:tools? )?(?:was|were) used|"
        r"tidak menggunakan (?:ai|kecerdasan)"
    ),
    "ethics": (
        r"\bethic|\betik\b|informed consent|persetujuan (?:etik|tertulis)|"
        r"institutional review board|\birb\b|komisi etik"
    ),
}

DEFAULT_REQUIRED_DECLARATIONS: tuple[str, ...] = (
    "competing_interests",
    "funding",
    "data_availability",
    "ai_use",
)
RECOMMENDED_DECLARATIONS: tuple[str, ...] = ("author_contributions", "code_availability")

_DECLARATION_TITLE_RE = re.compile(
    r"declaration|statement|pernyataan|acknowledg|ucapan terima kasih|funding|pendanaan|"
    r"competing|conflict|konflik|availability|ketersediaan|contribution|kontribusi|credit|"
    r"ethic|etik|generative ai|use of ai|penggunaan ai|ai-assisted",
    re.IGNORECASE,
)
_ANY_HEADING_RE = re.compile(
    r"\\(?:section|subsection|subsubsection|paragraph|chapter)\*?\s*\{([^{}]*)\}"
)
_THANKS_RE = re.compile(r"\\(?:thanks|funding|ack)\s*\{([^{}]*)\}")
_HUMAN_SUBJECTS_RE = re.compile(
    r"\bparticipants?\b|partisipan|\brespondents?\b|responden|\bpatients?\b|\bpasien\b|"
    r"\binterview|wawancara|\bsurvey|survei|kuesioner|questionnaire|human subjects",
    re.IGNORECASE,
)
_ETHICS_RE = re.compile(DECLARATION_PATTERNS["ethics"], re.IGNORECASE)


def declaration_text(text: str) -> str:
    """The parts of a manuscript that carry declarations.

    A paper about AI mentions "large language models" throughout its body;
    only a heading titled as a declaration (or a ``\\thanks``/``\\funding``
    note) can disclose the authors' own AI use, funding or interests.
    """

    parts: list[str] = [match.group(1) for match in _THANKS_RE.finditer(text)]
    headings = list(_ANY_HEADING_RE.finditer(text))
    for index, match in enumerate(headings):
        if not _DECLARATION_TITLE_RE.search(match.group(1)):
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        end_doc = text.find("\\end{document}", match.end())
        if 0 <= end_doc < end:
            end = end_doc
        parts.append(match.group(1))
        parts.append(text[match.end():end])
    stripped = "\n".join(parts)
    stripped = re.sub(r"(?<!\\)%.*$", " ", stripped, flags=re.M)
    return stripped


@dataclass(frozen=True)
class DeclarationCheck:
    required: tuple[str, ...]
    present: tuple[str, ...]
    missing: tuple[str, ...]
    recommended_missing: tuple[str, ...]
    ethics_expected: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": list(self.required),
            "present": list(self.present),
            "missing": list(self.missing),
            "recommended_missing": list(self.recommended_missing),
            "ethics_expected": self.ethics_expected,
        }


def check_declarations(
    text: str,
    *,
    required: Sequence[str] | None = None,
    paper_type: str = "empirical",
) -> DeclarationCheck:
    unknown = set(required or ()) - set(DECLARATION_PATTERNS)
    if unknown:
        raise ValueError(f"unknown declarations: {sorted(unknown)}")
    region = declaration_text(text)
    present = tuple(
        name
        for name, pattern in DECLARATION_PATTERNS.items()
        if name != "ethics" and re.search(pattern, region, re.IGNORECASE)
    )
    # Ethics approval is usually reported in the method, not a declarations block.
    ethics_expected = paper_type == "empirical" and bool(_HUMAN_SUBJECTS_RE.search(text))
    if ethics_expected and _ETHICS_RE.search(text):
        present = (*present, "ethics")
    needed = list(required) if required is not None else list(DEFAULT_REQUIRED_DECLARATIONS)
    if ethics_expected and "ethics" not in needed:
        needed.append("ethics")
    recommended = [
        name
        for name in RECOMMENDED_DECLARATIONS
        if name not in needed
        and not (name == "code_availability" and paper_type in ("review", "conceptual"))
    ]
    return DeclarationCheck(
        required=tuple(needed),
        present=present,
        missing=tuple(name for name in needed if name not in present),
        recommended_missing=tuple(name for name in recommended if name not in present),
        ethics_expected=ethics_expected,
    )


# --------------------------------------------------------------------------
# References: recency, primary share, retractions
# --------------------------------------------------------------------------

PRIMARY_ENTRY_TYPES = frozenset({"article", "inproceedings", "conference"})
_CITE_RE = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*){0,2}\{([^{}]+)\}")


def cited_keys(text: str) -> list[str]:
    """Citation keys in order of first use (``\\cite``, ``\\citep``, ``\\citet``...)."""

    keys: list[str] = []
    for group in _CITE_RE.findall(text):
        for key in group.split(","):
            key = key.strip()
            if key and key not in keys:
                keys.append(key)
    return keys


@dataclass(frozen=True)
class ReferencePolicy:
    """Thresholds for the reference audit; every value is overridable.

    Defaults are advisory. Indonesian accreditation guidance asks for recent
    primary literature (university handbooks cite five to ten years), but the
    exact share differs per journal, so treat these as a starting point.
    """

    recent_years: int = 10
    min_recent_share: float = 0.6
    min_primary_share: float = 0.6
    reference_year: int | None = None
    # A thesis guide may set a minimum number of cited references.
    min_entries: int = 0

    @classmethod
    def from_payload(cls, raw: Mapping[str, Any] | None) -> ReferencePolicy:
        if not raw:
            return cls()
        allowed = {
            "recent_years", "min_recent_share", "min_primary_share", "reference_year", "min_entries",
        }
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"unknown reference_policy keys: {sorted(unknown)}")
        policy = cls(**{key: raw[key] for key in raw})
        if policy.recent_years <= 0:
            raise ValueError("recent_years must be positive")
        if policy.min_entries < 0:
            raise ValueError("min_entries must not be negative")
        for name in ("min_recent_share", "min_primary_share"):
            if not 0 <= float(getattr(policy, name)) <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
        return policy


def normalize_doi(value: object) -> str:
    doi = str(value or "").strip().lower()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi)
    return doi.rstrip(".")


def load_retraction_dois(csv_text: str) -> dict[str, str]:
    """Map DOI -> nature from a Retraction Watch CSV export (or any CSV with a DOI column).

    Retraction Watch columns are ``OriginalPaperDOI`` and ``RetractionNature``.
    A generic file may use ``doi`` and ``nature``/``status``. Rows without a
    nature are treated as retractions.
    """

    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        return {}
    by_lower = {name.lower(): name for name in reader.fieldnames}
    doi_column = by_lower.get("originalpaperdoi") or by_lower.get("doi")
    nature_column = (
        by_lower.get("retractionnature") or by_lower.get("nature") or by_lower.get("status")
    )
    if doi_column is None:
        raise ValueError("retraction CSV needs an OriginalPaperDOI or doi column")
    found: dict[str, str] = {}
    for row in reader:
        doi = normalize_doi(row.get(doi_column))
        if not doi or doi in {"unavailable", "none", "na"}:
            continue
        nature = str(row.get(nature_column) or "Retraction").strip() if nature_column else "Retraction"
        found.setdefault(doi, nature or "Retraction")
    return found


@dataclass(frozen=True)
class ReferenceAudit:
    entries: int = 0
    with_year: int = 0
    recent: int = 0
    primary: int = 0
    reference_year: int = 0
    policy: ReferencePolicy = field(default_factory=ReferencePolicy)
    retracted: tuple[tuple[str, str, str], ...] = ()
    retraction_db_loaded: bool = False

    @property
    def recent_share(self) -> float:
        return self.recent / self.with_year if self.with_year else 0.0

    @property
    def primary_share(self) -> float:
        return self.primary / self.entries if self.entries else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": self.entries,
            "with_year": self.with_year,
            "recent": self.recent,
            "recent_share": round(self.recent_share, 4),
            "primary": self.primary,
            "primary_share": round(self.primary_share, 4),
            "reference_year": self.reference_year,
            "recent_years": self.policy.recent_years,
            "min_recent_share": self.policy.min_recent_share,
            "min_primary_share": self.policy.min_primary_share,
            "min_entries": self.policy.min_entries,
            "retraction_db_loaded": self.retraction_db_loaded,
            "retracted": [
                {"key": key, "doi": doi, "nature": nature}
                for key, doi, nature in self.retracted
            ],
        }


def audit_references(
    entries: Sequence[Any],
    *,
    cited_keys: Iterable[str] = (),
    policy: ReferencePolicy | None = None,
    retractions: Mapping[str, str] | None = None,
) -> ReferenceAudit:
    """Audit parsed BibTeX entries (``corpus_binder.BibEntry``).

    Only cited entries are audited when any citation is present, because an
    uncited entry never reaches the reference list of a compiled paper.
    """

    from datetime import date

    active = policy or ReferencePolicy()
    cited = set(cited_keys)
    pool = [entry for entry in entries if not cited or entry.key in cited] or list(entries)
    year_now = active.reference_year or date.today().year
    years: list[int] = []
    for entry in pool:
        match = re.search(r"(19|20)\d\d", str(entry.fields.get("year") or entry.fields.get("date") or ""))
        if match:
            years.append(int(match.group(0)))
    recent = sum(1 for year in years if year_now - year <= active.recent_years)
    primary = sum(1 for entry in pool if entry.entry_type in PRIMARY_ENTRY_TYPES)
    retracted: list[tuple[str, str, str]] = []
    if retractions:
        for entry in pool:
            doi = normalize_doi(entry.fields.get("doi"))
            if doi and doi in retractions:
                retracted.append((entry.key, doi, retractions[doi]))
    return ReferenceAudit(
        entries=len(pool),
        with_year=len(years),
        recent=recent,
        primary=primary,
        reference_year=year_now,
        policy=active,
        retracted=tuple(retracted),
        retraction_db_loaded=retractions is not None,
    )


# --------------------------------------------------------------------------
# Locator quote verification
# --------------------------------------------------------------------------

LOCATOR_VERIFIED = "verified"
LOCATOR_NOT_FOUND = "quote_not_found"
LOCATOR_NO_TEXT = "no_source_text"
LOCATOR_NO_QUOTE = "no_quote"


def _normalize_quote(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    # PDF extraction breaks lines and hyphenates; compare on letters and digits.
    stripped = re.sub(r"-\s*\n\s*", "", stripped)
    return re.sub(r"[^0-9a-z]+", " ", stripped.casefold()).strip()


def verify_locator_quotes(
    locators: Sequence[Any], texts_by_key: Mapping[str, str]
) -> dict[str, str]:
    """Status per locator key: verified, quote_not_found, no_source_text or no_quote."""

    normalized = {key: _normalize_quote(body) for key, body in texts_by_key.items()}
    status: dict[str, str] = {}
    for locator in locators:
        if not locator.quote:
            status.setdefault(locator.key, LOCATOR_NO_QUOTE)
            continue
        body = normalized.get(locator.key)
        if body is None:
            status[locator.key] = LOCATOR_NO_TEXT
            continue
        needle = _normalize_quote(locator.quote)
        verdict = LOCATOR_VERIFIED if needle and needle in body else LOCATOR_NOT_FOUND
        # One failing quote for a key is enough to flag it.
        if status.get(locator.key) != LOCATOR_NOT_FOUND:
            status[locator.key] = verdict
    return status


__all__ = [
    "DECLARATION_PATTERNS",
    "DEFAULT_REQUIRED_DECLARATIONS",
    "DeclarationCheck",
    "FlowCheck",
    "FlowIdentity",
    "LOCATOR_NOT_FOUND",
    "LOCATOR_NO_QUOTE",
    "LOCATOR_NO_TEXT",
    "LOCATOR_VERIFIED",
    "PAPER_TYPES",
    "resolve_research_design",
    "PRIMARY_ENTRY_TYPES",
    "RECOMMENDED_DECLARATIONS",
    "ReferenceAudit",
    "ReferencePolicy",
    "audit_references",
    "check_declarations",
    "check_prisma_flow",
    "declaration_text",
    "detect_paper_type",
    "load_retraction_dois",
    "normalize_doi",
    "resolve_paper_type",
    "verify_locator_quotes",
]

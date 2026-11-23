"""Research designs and the reporting standard each one is judged against.

A systematic review, a randomised trial, an interview study and a classroom
action research report fail review for different reasons. This registry maps
each design to the published reporting guideline for it and turns that
guideline into checkable signals:

* ``method_signals``: what the Method section must describe;
* ``repro_signals``: what makes the study repeatable or auditable, anywhere in
  the manuscript;
* ``results_signals``: what the Results must report (statistics for
  quantitative designs, themes and quotes for qualitative ones, per-cycle
  comparison for action research, and so on);
* ``flow``: the flow diagram whose arithmetic is checked: ``"prisma"``
  (records through a review), ``"consort"`` (participants through a trial or
  a non-randomised evaluation) or ``"strobe"`` (participants at each stage of
  an observational study);
* ``method_outline``: suggested Method subsections, in reporting order.

Designs form a small tree (``parent``): a meta-analysis is a systematic review
with pooled effects, classroom action research (PTK) is action research with
success indicators. ``family`` is ``review`` or ``empirical``, which is what
the rest of PaperAssist (declarations, PRISMA flow) keys on.

The signals are heuristics over the LaTeX text, not a checklist assessment:
they show whether an item is mentioned at all, never whether it is done well,
and they cover the items a manuscript text can show, not every checklist item.
Citations point at each guideline's publication; guidelines are revised, so
check the current version on the EQUATOR Network before citing one.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

Signal = tuple[str, str]

DESIGN_FAMILIES = ("review", "empirical", "conceptual")


@dataclass(frozen=True)
class ResearchDesign:
    key: str
    label: str
    family: str
    category: str
    guideline: str
    reference: str
    detect: str = ""
    method_signals: tuple[Signal, ...] = ()
    repro_signals: tuple[Signal, ...] = ()
    results_signals: tuple[Signal, ...] = ()
    flow: str | None = None
    parent: str | None = None
    aliases: tuple[str, ...] = ()
    min_hits: int = 1
    weak_detect: str = ""
    # Designs this one replaces when it is named at least twice (see
    # ``detect_research_design``).
    outranks: tuple[str, ...] = ()
    # A pattern that, found in the title block, adds two hits when the design
    # is named at least once (a "...Bench" or "...Benchmark" title).
    title_boost: str = ""
    notes: str = ""
    url: str = ""
    method_outline: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "family": self.family,
            "category": self.category,
            "parent": self.parent,
            "guideline": self.guideline,
            "reference": self.reference,
            "url": self.url,
            "aliases": list(self.aliases),
            "flow": self.flow,
            "method_items": [name for name, _ in self.method_signals],
            "repro_items": [name for name, _ in self.repro_signals],
            "results_items": [name for name, _ in self.results_signals],
            "method_outline": list(self.method_outline),
            "notes": self.notes,
        }


# Computer-science literature surveys ("RAG for LLMs: A Survey", "In this
# survey, we review ...") are reviews, not questionnaire studies.
LITERATURE_SURVEY_RE = re.compile(
    r"literature survey"
    # Not "brief survey": papers open background sections with one.
    r"|(?:comprehensive|systematic|critical|analytical|thorough|extensive) survey\b"
    r"|[:—–]\s*a\s+(?:\w+\s+)?survey\b"
    r"|\b(?:this|our) survey,?\s+(?:\w+ly\s+)?(?:reviews|examines|covers|summari[sz]es"
    r"|categori[sz]es|explores|surveys|presents|provides|argues|endeavou?rs|maps|traces"
    r"|aims\s+to\s+(?:provide|review|summari[sz]e|give|present|offer))\b"
    r"|\bin this survey,?\s+we\b"
    # A title line "A survey of automated ICD coding" (optionally after the
    # journal's "Review" label); questionnaire titles are screened out by the
    # respondent check in family detection.
    r"|^[ \t]*(?:review[ \t]+)?a[ \t]+(?:[\w-]+[ \t]+)?survey[ \t]+(?:of|on)\b",
    re.IGNORECASE | re.MULTILINE,
)
# How far into the text an article-type label ("RESEARCH ESSAY", "Guest
# Editorial", "Position paper") counts: the title block and abstract.
ARTICLE_TYPE_WINDOW = 3000
# The title block: journal header lines plus the title itself.
TITLE_WINDOW = 600


# --------------------------------------------------------------------------
# Shared signal groups
# --------------------------------------------------------------------------

# Indonesian meN-/peN- prefixes mutate a root's initial consonant: saring ->
# penyaringan, seleksi -> penyeleksian, telusur -> penelusuran. Matching the bare
# root therefore misses the forms academic prose actually uses. The \b-anchored
# English alternatives stay word-initial so "research" is not read as "search".
_SEARCH: Signal = (
    "search strategy",
    r"\b(?:search|query|string)\w*|\b\w*(?:cari|telusur|nelusur)\w*",
)
_DATABASES: Signal = (
    "database enumeration",
    r"\b\w*(?:scopus|pubmed|web of science|ieee|scholar|garuda|database|basis data|pangkalan data|dimensions|openalex|lens\.org)\w*",
)
_SEARCH_DATES: Signal = (
    "search dates",
    r"last searched|search(?:es)? (?:was|were )?(?:conducted|performed|run) (?:on|in|between)|search date|tanggal pencarian|dilakukan pada|hingga (?:\d|januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)|up to (?:\d|january|february|march|april|may|june|july|august|september|october|november|december)|as of",
)
_INCLUSION: Signal = ("inclusion criteria", r"\b\w*(?:inclusion|inklusi|eligib|kriteria)\w*")
_EXCLUSION: Signal = ("exclusion criteria", r"\b\w*(?:exclusion|eksklusi)\w*")
_SCREENING: Signal = (
    "screening process",
    r"\b\w*(?:screen|skrin|saring|yaring|seleksi|yeleksi|tapis)\w*",
)
_INDEPENDENT: Signal = (
    "independent reviewers",
    r"two (?:independent )?reviewers|independent(?:ly)?|dua (?:orang )?(?:reviewer|peninjau|penilai)|secara independen|kappa|inter-rater|antar-?penilai",
)
_EXTRACTION: Signal = (
    "extraction procedure",
    r"\b\w*(?:extraction|ekstraksi|charting|penilaian)\w*",
)
_RISK_OF_BIAS: Signal = (
    "risk-of-bias appraisal",
    r"risk of bias|risiko bias|\brob\s*-?2\b|robins|\bcasp\b|\bjbi\b|\bmmat\b|quadas|newcastle|amstar|critical appraisal|quality (?:appraisal|assessment)|penilaian kualitas",
)
_CERTAINTY: Signal = (
    "certainty of evidence",
    r"certainty of (?:the )?evidence|\bgrade\b (?:approach|framework|assessment)|cerqual|kepastian bukti|confidence in (?:the )?evidence",
)
_SYNTHESIS: Signal = ("synthesis method", r"\b\w*(?:synthesis|sintesis|meta-analy)\w*")

_REVIEW_REPRO: tuple[Signal, ...] = (
    (
        "data availability",
        r"data availability|ketersediaan data|dataset tersedia|extraction (?:form|data) (?:is|are) available",
    ),
    ("protocol or registration", r"protocol|protokol|registr|\bosf\b|prospero"),
    (
        "full search strings",
        r"search strings?|query strings?|string pencarian|full search strateg|appendix|lampiran|supplementary",
    ),
    ("prisma reporting", r"prisma"),
)

_DATA_AVAILABLE: Signal = (
    "data availability",
    r"data availability|ketersediaan data|data (?:are|is) available|dataset tersedia|publicly available|tersedia (?:secara )?(?:publik|terbuka)",
)
_CODE_AVAILABLE: Signal = (
    "code availability",
    r"code availability|source code|kode sumber|github\.com|gitlab\.com|zenodo|repositori",
)
_PARAMETERS: Signal = (
    "parameter settings",
    r"hyperparameter|hiperparameter|random seed|\bseed\b|learning rate|parameter settings?|konfigurasi|configuration",
)
_ENVIRONMENT: Signal = (
    "computing environment",
    r"\bgpu\b|\bcpu\b|hardware|perangkat keras|software version|versi|python \d|pytorch|tensorflow|\br \d|spss|stata|smartpls|amos",
)
_REGISTRATION: Signal = (
    "trial registration",
    r"clinicaltrials\.gov|\bnct\d|isrctn|anzctr|registered|terdaftar|registr",
)
_INSTRUMENT_APPENDIX: Signal = (
    "instrument available",
    r"appendix|lampiran|supplementary|interview guide|pedoman wawancara|kuesioner lengkap|instrument is available",
)
_ETHICS: Signal = (
    "ethics and consent",
    r"ethic|etik|informed consent|persetujuan|irb|institutional review board|komite",
)

# Uncertainty and effect reporting in the results (APA/CONSORT-style practice).
_UNCERTAINTY: Signal = (
    "uncertainty",
    r"confidence interval|interval kepercayaan|\bci\b|standard deviation|simpangan baku|standard error|\bstd\b|\bsd\b|\\pm|±",
)
_EFFECT: Signal = (
    "significance or effect",
    r"p-?value|nilai p|\bp\s*[<=>]|effect size|ukuran efek|cohen|odds ratio|\bor\b\s*=|hazard ratio|risk ratio|mean difference|beda rerata|n-?gain",
)
_SAMPLE: Signal = (
    "sample size",
    r"\bn\s*=\s*\d|sample size|ukuran sampel|jumlah sampel|\d+ (?:participants|partisipan|responden|respondents|samples|sampel|siswa|students|informan)",
)
STATISTICS_SIGNALS: tuple[Signal, ...] = (_UNCERTAINTY, _EFFECT, _SAMPLE)


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

_SYSTEMATIC_METHOD: tuple[Signal, ...] = (
    _SEARCH,
    _DATABASES,
    _SEARCH_DATES,
    _INCLUSION,
    _EXCLUSION,
    _SCREENING,
    _INDEPENDENT,
    _EXTRACTION,
    _RISK_OF_BIAS,
    _CERTAINTY,
    _SYNTHESIS,
)

_GENERAL_EMPIRICAL_METHOD: tuple[Signal, ...] = (
    ("research design", r"\b(?:design|desain|rancangan|approach|pendekatan)\w*"),
    (
        "data or participants",
        r"\b\w*(?:dataset|data set|sampel|sample|participant|partisipan|responden|respondent|subjek|subject|populasi|population|corpus|korpus)\w*",
    ),
    (
        "procedure or instrument",
        r"\b\w*(?:procedure|prosedur|instrumen|instrument|kuesioner|questionnaire|setup|implementasi|implementation|pipeline)\w*",
    ),
    (
        "variables or metrics",
        r"\b\w*(?:metric|metrik|variabel|variable|measure|ukuran|indikator|indicator|evaluat|evaluasi)\w*",
    ),
    (
        "analysis method",
        r"\b\w*(?:analysis|analisis|statistic|statistik|regression|regresi|anova|t-test|uji)\w*",
    ),
    (
        "baseline or comparison",
        r"\b\w*(?:baseline|pembanding|comparison|perbandingan|control group|kelompok kontrol|benchmark)\w*",
    ),
    (
        "validation",
        r"\b\w*(?:validation|validasi|cross-validation|reliabilit|validity|validitas|held-out|test set|data uji)\w*",
    ),
)
_GENERAL_EMPIRICAL_REPRO: tuple[Signal, ...] = (
    _DATA_AVAILABLE,
    _CODE_AVAILABLE,
    _PARAMETERS,
    _ENVIRONMENT,
)

_DESIGNS: tuple[ResearchDesign, ...] = (
    # ---------------------------------------------------------------- reviews
    ResearchDesign(
        key="meta_analysis",
        label="Systematic review with meta-analysis",
        family="review",
        category="evidence synthesis",
        parent="systematic_review",
        guideline="PRISMA 2020 (+ MOOSE for observational studies)",
        reference="Page MJ et al. BMJ 2021;372:n71",
        url="https://www.prisma-statement.org/",
        aliases=("meta-analysis", "metaanalysis", "meta-analisis", "ma"),
        detect=r"meta-?analy|meta-?analisis",
        # Every PRISMA citation spells out "...Systematic Reviews and
        # Meta-Analyses" (stripped before detection), and SLRs mention
        # meta-analysis in passing: one mention is not a pooled analysis.
        min_hits=2,
        method_signals=_SYSTEMATIC_METHOD
        + (
            (
                "effect measure",
                r"effect (?:size|measure)|odds ratio|risk ratio|mean difference|\bsmd\b|hedges|ukuran efek",
            ),
            (
                "synthesis model",
                r"random[- ]effects?|fixed[- ]effects?|efek acak|efek tetap|common[- ]effect",
            ),
            ("heterogeneity", r"heterogen|\bi\^?\{?2|i²|cochran|\btau\b|τ"),
            (
                "reporting bias",
                r"publication bias|reporting bias|bias publikasi|funnel|egger|trim[- ]and[- ]fill",
            ),
            (
                "sensitivity or subgroup analysis",
                r"sensitivity analys|analisis sensitivitas|leave-one-out|subgroup|subgrup|meta-regression|meta-regresi",
            ),
        ),
        repro_signals=_REVIEW_REPRO,
        results_signals=(
            ("pooled estimate with interval", r"pooled|gabungan|overall effect|95\s*\\?%\s*ci|confidence interval|interval kepercayaan"),
            ("heterogeneity statistic", r"\bi\^?\{?2|i²|\btau|τ|q\s*=|cochran"),
            ("forest plot", r"forest plot|forest"),
        ),
        flow="prisma",
    ),
    ResearchDesign(
        key="systematic_review",
        label="Systematic literature review",
        family="review",
        category="evidence synthesis",
        guideline="PRISMA 2020 and PRISMA-S (search reporting)",
        reference="Page MJ et al. BMJ 2021;372:n71; Rethlefsen ML et al. Syst Rev 2021;10:39",
        url="https://www.prisma-statement.org/",
        aliases=("review", "slr", "systematic-review", "systematic literature review"),
        detect=(
            r"systematic (?:literature )?review|tinjauan (?:literatur(?:e)? )?sistematis|"
            r"kajian (?:literatur )?sistematis|\bslr\b|\bprisma\b|mapping study|systematic mapping"
        ),
        method_signals=_SYSTEMATIC_METHOD,
        repro_signals=_REVIEW_REPRO,
        flow="prisma",
    ),
    ResearchDesign(
        key="scoping_review",
        label="Scoping review",
        family="review",
        category="evidence synthesis",
        guideline="PRISMA-ScR (22 items); JBI scoping review methodology",
        reference="Tricco AC et al. Ann Intern Med 2018;169:467-473",
        url="https://www.equator-network.org/reporting-guidelines/prisma-scr/",
        aliases=("scoping", "scoping-review", "evidence map"),
        detect=r"scoping review|scoping study|tinjauan (?:cakupan|pelingkupan)|kajian pelingkupan|evidence map|prisma-scr",
        outranks=("systematic_review",),
        method_signals=(
            (
                "review framework",
                r"arksey|o'?malley|levac|\bjbi\b|peters et al|joanna briggs",
            ),
            (
                "population, concept, context",
                r"\bpcc\b|population,? concept,? (?:and )?context|populasi,? konsep,? (?:dan )?konteks",
            ),
            _SEARCH,
            _DATABASES,
            _SEARCH_DATES,
            _INCLUSION,
            ("selection of sources", r"\b\w*(?:screen|skrin|saring|yaring|seleksi|yeleksi|selection)\w*"),
            ("data charting", r"chart|charting|ekstraksi|extraction form|data items"),
            (
                "collating and summarising",
                r"collat|summari[sz]|mapping|pemetaan|descriptive|deskriptif|narrative summary",
            ),
        ),
        repro_signals=_REVIEW_REPRO,
        results_signals=(
            ("characteristics of sources", r"characteristic|karakteristik|year of publication|tahun terbit|country|negara"),
            ("evidence map or table", r"\\begin\{table|table|tabel|map|peta"),
        ),
        flow="prisma",
        notes=(
            "Critical appraisal is optional in a scoping review (PRISMA-ScR item 12); "
            "its absence is not a defect."
        ),
    ),
    ResearchDesign(
        key="bibliometric",
        label="Bibliometric analysis",
        family="review",
        category="evidence synthesis",
        guideline="BIBLIO (preliminary, 20 items)",
        reference="Montazeri A et al. Syst Rev 2023;12:239",
        url="https://www.equator-network.org/reporting-guidelines/preliminary-guideline-for-reporting-bibliometric-reviews-of-the-biomedical-literature-biblio-a-minimum-requirements/",
        aliases=("bibliometrics", "bibliometrik", "scientometric", "bibliometric-analysis"),
        detect=r"bibliometri|scientometri|saintometri|vosviewer|bibliometrix|biblioshiny|citespace|science mapping",
        outranks=("systematic_review",),
        method_signals=(
            ("data source", r"scopus|web of science|\bwos\b|dimensions|openalex|lens\.org|pubmed|google scholar|garuda"),
            _SEARCH,
            _SEARCH_DATES,
            (
                "time span",
                r"period|periode|time ?span|rentang (?:waktu|tahun)|(?:19|20)\d\d\s*(?:-|–|--|to|hingga|sampai)\s*(?:19|20)\d\d",
            ),
            (
                "document filters",
                r"document type|jenis dokumen|article|language|bahasa|filter|inclusion|inklusi",
            ),
            (
                "data cleaning",
                r"duplicat|duplikat|deduplic|cleaning|pembersihan|thesaurus|normali[sz]",
            ),
            (
                "analysis software",
                r"vosviewer|bibliometrix|biblioshiny|citespace|gephi|scimat|pajek|r package",
            ),
            (
                "bibliometric indicators",
                r"co-?citation|co-?word|co-?occurrence|coupling|co-?authorship|kolaborasi|collaboration|performance analysis|science mapping|h-index|citation count|jumlah sitasi",
            ),
        ),
        repro_signals=(
            ("full search strings", r"search strings?|query strings?|string pencarian|appendix|lampiran|supplementary"),
            _DATA_AVAILABLE,
            ("software version and settings", r"version|versi|threshold|minimum number of|ambang|normali[sz]ation method"),
        ),
        results_signals=(
            ("publication trend", r"annual|tahunan|trend|tren|growth|pertumbuhan"),
            ("most productive sources or authors", r"most (?:productive|cited|influential)|paling (?:produktif|banyak)|top \d+"),
            ("network or cluster map", r"cluster|klaster|network|jaringan|map|peta"),
        ),
        notes="BIBLIO is preliminary and was developed for biomedical literature.",
    ),
    ResearchDesign(
        key="narrative_review",
        label="Narrative or integrative review",
        family="review",
        category="evidence synthesis",
        guideline="SANRA (quality of narrative reviews, 6 items)",
        reference="Baethge C, Goldbeck-Wood S, Mertens S. Res Integr Peer Rev 2019;4:5",
        url="https://researchintegrityjournal.biomedcentral.com/articles/10.1186/s41073-019-0064-8",
        aliases=("narrative", "literature-review", "integrative review", "state of the art"),
        detect=(
            r"(?m)narrative review|integrative review|kajian naratif|tinjauan naratif"
            r"|state[- ]of[- ]the[- ]art review|curated review|"
            + LITERATURE_SURVEY_RE.pattern
        ),
        method_signals=(
            ("justification of importance", r"importan|penting|relevan|gap|celah|motivat"),
            ("aims or questions", r"\baim|objective|tujuan|research question|pertanyaan penelitian"),
            ("literature search description", _SEARCH[1] + "|" + _DATABASES[1]),
            ("selection rationale", r"select|pilih|criteria|kriteria|inclusion|inklusi"),
        ),
        repro_signals=(("search terms listed", r"keyword|kata kunci|search terms?|query"),),
        results_signals=(
            ("evidence-based reasoning", r"\\cite"),
            ("appropriate data presentation", r"\\begin\{table|\\begin\{figure|tabel|gambar|table|figure"),
        ),
    ),
    # ------------------------------------------------------------ quantitative
    ResearchDesign(
        key="rct",
        label="Randomised controlled trial",
        family="empirical",
        category="quantitative",
        guideline="CONSORT 2025 (30 items + flow diagram)",
        flow="consort",
        reference="Hopewell S et al. BMJ 2025;389:e081123",
        url="https://www.consort-spirit.org/",
        aliases=("randomised-trial", "randomized-trial", "randomized controlled trial", "uji klinis"),
        detect=r"randomi[sz]ed (?:controlled |clinical )?trial|\brct\b|uji (?:klinis|acak) (?:acak )?terkontrol|uji klinis acak|\bconsort\b",
        method_signals=(
            ("trial design and allocation ratio", r"parallel|crossover|cluster|factorial|allocation ratio|rasio alokasi|paralel"),
            ("eligibility of participants", r"eligib|inclusion|exclusion|inklusi|eksklusi|kriteria"),
            ("interventions", r"intervention|intervensi|treatment|perlakuan|placebo|plasebo"),
            ("pre-specified outcomes", r"primary outcome|secondary outcome|luaran (?:primer|utama)|outcome"),
            ("sample size calculation", r"sample size calculation|power (?:analysis|calculation)|perhitungan (?:besar )?sampel|g\*power|\bpower\b"),
            ("sequence generation", r"random(?:is|iz)ation|randomly|secara acak|block|stratif|computer-generated"),
            ("allocation concealment", r"allocation concealment|conceal|sealed|opaque|penyembunyian alokasi|central(?:ised|ized)? randomi"),
            ("blinding", r"blind|mask|tersamar|buta"),
            ("statistical methods", r"intention[- ]to[- ]treat|\bitt\b|per[- ]protocol|statistical analys|analisis statistik"),
        ),
        repro_signals=(
            _REGISTRATION,
            ("protocol access", r"protocol|protokol|\bspirit\b"),
            ("data sharing", _DATA_AVAILABLE[1] + r"|data sharing|berbagi data"),
            ("statistical analysis plan", r"statistical analysis plan|\bsap\b|rencana analisis"),
        ),
        results_signals=(
            ("participant flow", r"enrol|randomi[sz]ed|allocated|lost to follow|analy[sz]ed|flow diagram|diagram alir|drop ?out"),
            ("baseline characteristics", r"baseline|karakteristik dasar|demograph|table 1"),
            _UNCERTAINTY,
            _EFFECT,
            ("harms", r"adverse|harm|side effect|efek samping|kejadian tidak diinginkan"),
        ),
    ),
    ResearchDesign(
        key="quasi_experiment",
        label="Quasi-experiment (non-randomised evaluation)",
        family="empirical",
        category="quantitative",
        guideline="TREND statement (22 items)",
        flow="consort",
        reference="Des Jarlais DC, Lyles C, Crepaz N; TREND Group. Am J Public Health 2004;94:361-366",
        aliases=("quasi-experiment", "quasi-experimental", "kuasi-eksperimen", "eksperimen semu"),
        detect=r"quasi[- ]?experiment|kuasi[- ]?eksperimen|eksperimen semu|non-?equivalent (?:control )?group|pretest[- ]posttest|pre-?test[- ]post-?test|interrupted time series",
        method_signals=(
            ("design", r"quasi|kuasi|semu|non-?equivalent|pre-?test|post-?test|time series|deret waktu"),
            ("comparison group", r"control group|kelompok kontrol|kelas kontrol|comparison group|pembanding"),
            ("assignment method", r"assign|penempatan|purposive|cluster|intact|kelas utuh|sampling|pengambilan sampel"),
            ("intervention description", r"intervention|intervensi|treatment|perlakuan|model pembelajaran"),
            ("outcome measures", r"outcome|instrument|instrumen|tes|test|measure|pengukuran"),
            ("baseline equivalence and confounding", r"equivalen|kesetaraan|homogen|confound|covariat|kovariat|ancova|propensity|pretest"),
            ("analysis method", r"t-test|uji[- ]t|ancova|anova|mann|wilcoxon|regress|n-?gain|analisis"),
        ),
        repro_signals=(_DATA_AVAILABLE, _INSTRUMENT_APPENDIX, _ETHICS),
        results_signals=STATISTICS_SIGNALS,
    ),
    ResearchDesign(
        key="observational",
        label="Observational study (cohort, case-control, cross-sectional)",
        family="empirical",
        category="quantitative",
        guideline="STROBE (22 items)",
        flow="strobe",
        reference="von Elm E et al. Lancet 2007;370:1453-1457",
        url="https://www.strobe-statement.org/",
        aliases=("cohort", "case-control", "cross-sectional", "observasional", "potong lintang"),
        detect=r"cohort study|studi kohort|case[- ]control|kasus[- ]kontrol|cross[- ]sectional (?:study|design)|potong lintang|observational study|studi observasional|\bstrobe\b",
        method_signals=(
            ("study design", r"cohort|kohort|case[- ]control|kasus[- ]kontrol|cross[- ]sectional|potong lintang|observational|observasional"),
            ("setting and dates", r"setting|lokasi|tempat|period|periode|recruit|rekrut|(?:19|20)\d\d"),
            ("participants and eligibility", r"participant|partisipan|subjek|subject|eligib|inclusion|inklusi"),
            ("variables: exposures, outcomes, confounders", r"exposure|paparan|outcome|luaran|confound|perancu|covariat|kovariat|variab"),
            ("data sources and measurement", r"data source|sumber data|measure|pengukuran|questionnaire|kuesioner|record|rekam"),
            ("bias", r"\bbias"),
            ("study size", r"study size|sample size|ukuran sampel|besar sampel|jumlah sampel"),
            ("missing data", r"missing data|data hilang|imputation|imputasi|complete[- ]case|incomplete"),
        ),
        repro_signals=(_DATA_AVAILABLE, _ETHICS, _CODE_AVAILABLE),
        results_signals=STATISTICS_SIGNALS
        + (("unadjusted and adjusted estimates", r"adjusted|disesuaikan|crude|kasar|multivariable|multivariat"),),
    ),
    ResearchDesign(
        key="survey",
        label="Survey / questionnaire study",
        family="empirical",
        category="quantitative",
        guideline="CROSS (survey studies); CHERRIES for web surveys",
        reference="Sharma A et al. J Gen Intern Med 2021;36:3179-3187; Eysenbach G. J Med Internet Res 2004;6:e34",
        url="https://www.equator-network.org/reporting-guidelines/a-consensus-based-checklist-for-reporting-of-survey-studies-cross/",
        aliases=("questionnaire", "survei", "kuesioner", "angket"),
        detect=r"survey (?:study|research|design)|penelitian survei|metode survei|online survey|web survey|questionnaire survey|survei daring|survei (?:online|kuantitatif)|cross-sectional survey",
        # Questionnaires are instruments in R&D, PTK and quasi-experiments too:
        # they count towards a survey only when no other empirical design is named.
        weak_detect=r"kuesioner|angket|questionnaire",
        min_hits=2,
        method_signals=(
            ("population and sampling", r"population|populasi|sampling|sampel|purposive|random|stratified|slovin|convenience|snowball"),
            ("sample size justification", r"sample size|ukuran sampel|slovin|krejcie|power|g\*power|hair et al|rule of thumb"),
            ("instrument development", r"questionnaire|kuesioner|angket|likert|instrument|instrumen|adapted from|diadaptasi"),
            ("validity", r"validity|validitas|\bcfa\b|factor analysis|analisis faktor|\bave\b|content validity|validasi"),
            ("reliability", r"reliab|cronbach|alpha|composite reliability|\bcr\b"),
            ("administration mode", r"online|google form|web|daring|luring|face-to-face|tatap muka|paper|distribut|disebar"),
            ("response rate", r"response rate|tingkat (?:respons|pengembalian)|returned|dikembalikan|completed questionnaires"),
            ("analysis method", r"sem\b|pls|regress|regresi|descriptive|deskriptif|path|jalur|anova|chi"),
        ),
        repro_signals=(_INSTRUMENT_APPENDIX, _DATA_AVAILABLE, _ETHICS),
        results_signals=(
            ("respondent profile", r"respondent|responden|demograph|demografi|profil"),
            ("response rate", r"response rate|tingkat (?:respons|pengembalian)"),
            ("measurement model or descriptive statistics", r"mean|rata-rata|loading|outer|cronbach|\bave\b|\bsd\b|standard deviation"),
            _EFFECT,
        ),
    ),
    ResearchDesign(
        key="diagnostic_accuracy",
        label="Diagnostic accuracy study",
        family="empirical",
        category="quantitative",
        guideline="STARD 2015 (30 items + flow diagram)",
        reference="Bossuyt PM et al. BMJ 2015;351:h5527",
        url="https://www.equator-network.org/reporting-guidelines/stard/",
        aliases=("diagnostic", "stard", "akurasi diagnostik"),
        detect=r"diagnostic accuracy|akurasi diagnostik|index test|reference standard|standar acuan|\bstard\b",
        method_signals=(
            ("participants and recruitment", r"participant|partisipan|patient|pasien|recruit|consecutive|berturut"),
            ("index test", r"index test|tes indeks|uji indeks"),
            ("reference standard", r"reference standard|standar acuan|gold standard|baku emas"),
            ("blinding of assessors", r"blind|mask|tersamar|unaware"),
            ("positivity threshold", r"cut-?off|threshold|ambang|positivity"),
            ("accuracy measures", r"sensitivity|specificity|sensitivitas|spesifisitas|\bauc\b|\broc\b|\bppv\b|\bnpv\b|likelihood ratio"),
        ),
        repro_signals=(_REGISTRATION, _DATA_AVAILABLE, _ETHICS),
        results_signals=(
            ("participant flow", r"flow diagram|diagram alir|enrol|excluded|dieksklusi"),
            ("cross tabulation", r"2\s*[x×]\s*2|cross[- ]tab|tabulasi silang|true positive|false positive"),
            ("accuracy with interval", r"(?:sensitivity|specificity|sensitivitas|spesifisitas|auc)[^.]{0,80}(?:ci|interval|±|\\pm)"),
        ),
    ),
    ResearchDesign(
        key="prediction_model",
        label="Prediction model (regression or machine learning)",
        family="empirical",
        category="quantitative",
        guideline="TRIPOD+AI (27 items)",
        reference="Collins GS et al. BMJ 2024;385:e078378",
        url="https://www.tripod-statement.org/",
        aliases=("prognostic", "diagnostic-model", "risk-model", "tripod", "model prediksi"),
        detect=r"prediction model|prognostic model|risk (?:prediction|score) model|clinical prediction|model prediksi|\btripod\b",
        method_signals=(
            ("data source", r"data source|sumber data|registry|registri|electronic health|rekam medis|cohort|kohort|dataset"),
            ("outcome definition", r"outcome|luaran|target variable|variabel target|label"),
            ("predictors", r"predictor|prediktor|feature|fitur|candidate variable"),
            ("sample size", r"sample size|ukuran sampel|events per variable|\bepv\b|riley"),
            ("missing data handling", r"missing|hilang|imput"),
            ("model development and tuning", r"hyperparameter|hiperparameter|tuning|penalis|regulari[sz]|algorithm|algoritma"),
            ("validation strategy", r"internal validation|external validation|validasi (?:internal|eksternal)|cross-validation|bootstrap|temporal validation|held-out"),
            ("performance measures", r"calibration|kalibrasi|discrimination|diskriminasi|c-?statistic|\bauc\b|brier"),
            ("fairness across groups", r"fairness|keadilan|subgroup|subgrup|demographic parity|equal opportunity"),
        ),
        repro_signals=(_CODE_AVAILABLE, _DATA_AVAILABLE, _PARAMETERS),
        results_signals=(
            ("calibration", r"calibration|kalibrasi|calibration (?:plot|slope)"),
            ("discrimination with interval", r"(?:auc|c-?statistic|auroc)[^.]{0,80}(?:ci|interval|±|\\pm)"),
            ("model specification", r"coefficient|koefisien|full model|model specification|intercept|feature importance"),
        ),
    ),
    ResearchDesign(
        key="ml_experiment",
        label="Machine learning / computational experiment",
        family="empirical",
        category="quantitative",
        guideline="REFORMS (32 items, 8 modules); NeurIPS paper checklist",
        reference="Kapoor S et al. Sci Adv 2024;10:eadk3452",
        url="https://reforms.cs.princeton.edu/",
        aliases=("ml", "machine-learning", "deep-learning", "computational", "eksperimen komputasi"),
        detect=r"machine learning|deep learning|neural network|jaringan saraf|pembelajaran mesin|transformer|fine-?tun|\bcnn\b|\blstm\b|\bbert\b|\bllm\b|large language model|random forest|\bsvm\b|xgboost|naive bayes|k-nearest|\bknn\b",
        min_hits=2,
        method_signals=(
            ("dataset and provenance", r"dataset|data set|korpus|corpus|collected|dikumpulkan|kaggle|uci|benchmark"),
            ("data splits", r"train(?:ing)?[ /-]?(?:set|split)|test set|validation set|data (?:latih|uji)|pembagian data|k-?fold|split|80\s*:\s*20|70\s*:\s*30"),
            ("leakage prevention", r"leakage|kebocoran|data snooping|fit(?:ted)? (?:only )?on (?:the )?training|before splitting|sebelum pembagian|stratified|group k-?fold|deduplicat"),
            ("preprocessing", r"preprocess|pra-?pemrosesan|normali[sz]|tokeni[sz]|augment|cleaning|pembersihan"),
            ("model and baselines", r"baseline|pembanding|compared (?:with|to|against)|dibandingkan|state[- ]of[- ]the[- ]art"),
            ("hyperparameter tuning procedure", r"hyperparameter|hiperparameter|grid search|random search|optuna|bayesian optimi[sz]ation|tuning"),
            ("evaluation metrics", r"accuracy|akurasi|precision|presisi|recall|f1|auc|bleu|rouge|mae|rmse|mse|\bmap\b"),
            ("repeated runs", r"seeds?|runs|repeated|diulang|mean (?:over|of)|rata-rata (?:dari|atas)|standard deviation|simpangan baku|\\pm|±"),
        ),
        repro_signals=_GENERAL_EMPIRICAL_REPRO,
        results_signals=(
            ("variance across runs", r"\\pm|±|standard deviation|simpangan baku|\bstd\b|\bsd\b|confidence interval|interval kepercayaan"),
            ("comparison with baselines", r"baseline|pembanding|outperform|mengungguli|compared|dibandingkan"),
            ("ablation or error analysis", r"ablation|ablasi|error analysis|analisis kesalahan|confusion matrix|matriks konfusi|failure case"),
            ("significance of differences", r"significan|signifikan|p-?value|wilcoxon|mcnemar|t-test|bootstrap"),
        ),
    ),
    ResearchDesign(
        key="empirical",
        label="Empirical study (general)",
        family="empirical",
        category="quantitative",
        guideline="General empirical reporting (ACM SIGSOFT General Standard; APA JARS-Quant)",
        reference="Ralph P et al. ACM SIGSOFT Empirical Standards, arXiv:2010.03525",
        url="https://www2.sigsoft.org/EmpiricalStandards/",
        aliases=("experimental", "experiment", "quantitative", "kuantitatif", "eksperimen"),
        method_signals=_GENERAL_EMPIRICAL_METHOD,
        repro_signals=_GENERAL_EMPIRICAL_REPRO,
        results_signals=STATISTICS_SIGNALS,
        notes="Fallback when no specific design is recognised; set research_design explicitly.",
    ),
    # ------------------------------------------------------------- qualitative
    ResearchDesign(
        key="qualitative",
        label="Qualitative study (interviews, focus groups, observation)",
        family="empirical",
        category="qualitative",
        guideline="SRQR (21 items); COREQ (32 items) for interviews and focus groups",
        reference="O'Brien BC et al. Acad Med 2014;89:1245-1251; Tong A et al. Int J Qual Health Care 2007;19:349-357",
        url="https://www.equator-network.org/reporting-guidelines/srqr/",
        aliases=("kualitatif", "interview", "phenomenology", "fenomenologi", "grounded-theory", "ethnography"),
        detect=r"qualitative(?!ly)|kualitatif|phenomenolog|fenomenolog|grounded theory|thematic analysis|analisis tematik|ethnograph|etnograf|semi-?structured interview|wawancara (?:mendalam|semi)|in-?depth interview|focus group|\bfgd\b",
        method_signals=(
            ("qualitative approach and paradigm", r"phenomenolog|fenomenolog|grounded theory|ethnograph|etnograf|narrative|naratif|interpretiv|constructiv|konstruktiv|paradigm|descriptive qualitative|kualitatif deskriptif"),
            ("researcher reflexivity", r"reflexiv|refleksivitas|positionality|posisi peneliti|researcher'?s? role|peran peneliti|peneliti sebagai instrumen"),
            ("context and setting", r"setting|context|konteks|lokasi|site|tempat penelitian"),
            ("sampling strategy", r"purposive|snowball|theoretical sampling|maximum variation|informan|key informant|participant selection|pemilihan (?:informan|partisipan)"),
            ("data collection methods", r"interview|wawancara|focus group|\bfgd\b|observation|observasi|dokumentasi|field ?notes|catatan lapangan"),
            ("data saturation", r"saturation|saturasi|kejenuhan|jenuh"),
            ("analysis approach", r"thematic|tematik|coding|koding|braun|clarke|miles|huberman|spradley|colaizzi|nvivo|atlas\.ti|maxqda|reduksi data|kondensasi data"),
            ("trustworthiness", r"trustworthiness|keabsahan|credibility|kredibilitas|triangulat|member check|audit trail|dependability|transferability|confirmability|peer debriefing"),
        ),
        repro_signals=(_ETHICS, _INSTRUMENT_APPENDIX, ("audio recording and transcription", r"record|rekam|transcri|transkrip|verbatim")),
        results_signals=(
            ("themes or categories", r"theme|tema|categor|kategori|subtheme|subtema"),
            ("participant quotations", r"``|\"|“|informan \w+|participant \w+\d|\bp\d+\b|\bi\d+\b|\(p\d|\(informan"),
            ("links to prior work", r"\\cite"),
        ),
        notes="No statistics are expected; the results are judged on themes backed by quotations.",
    ),
    ResearchDesign(
        key="mixed_methods",
        label="Mixed methods study",
        family="empirical",
        category="mixed methods",
        guideline="GRAMMS (Good Reporting of A Mixed Methods Study)",
        reference="O'Cathain A, Murphy E, Nicholl J. J Health Serv Res Policy 2008;13:92-98",
        url="https://journals.sagepub.com/doi/10.1258/jhsrp.2007.007074",
        aliases=("mixed-methods", "mixed", "metode campuran", "campuran"),
        detect=r"mixed[- ]methods?|metode campuran|penelitian campuran|kombinasi kuantitatif dan kualitatif|explanatory sequential|sequential explanatory|exploratory sequential|sequential exploratory|convergent (?:parallel )?design|concurrent triangulation",
        method_signals=(
            ("justification for mixing", r"rationale|justif|alasan|in order to (?:explain|explore)|untuk (?:menjelaskan|mendalami)|complement"),
            ("mixed methods design type", r"explanatory|exploratory|eksplanatori|eksploratori|convergent|konvergen|concurrent|sequential|sekuensial|embedded|triangulation design"),
            ("priority and sequence", r"priority|prioritas|sequence|urutan|first phase|tahap (?:pertama|kedua)|qual|quan|kuan"),
            ("quantitative strand", r"questionnaire|kuesioner|survey|survei|statistic|statistik|quantitative|kuantitatif"),
            ("qualitative strand", r"interview|wawancara|focus group|qualitative|kualitatif|thematic|tematik"),
            ("integration", r"integrat|integrasi|joint display|mixing|meta-?inferen|merg|menggabungkan|connect"),
        ),
        repro_signals=(_ETHICS, _INSTRUMENT_APPENDIX, _DATA_AVAILABLE),
        results_signals=(
            ("quantitative results", r"mean|rata-rata|percent|persen|%|significan|signifikan"),
            ("qualitative results", r"theme|tema|informan|participant|partisipan"),
            ("integrated findings", r"integrat|integrasi|joint display|confirm|konfirm|diverg|converg|meta-?inferen"),
        ),
    ),
    ResearchDesign(
        key="case_study",
        label="Case study",
        family="empirical",
        category="qualitative",
        guideline="Yin case study design; ACM SIGSOFT Case Study standard",
        reference="Yin RK. Case Study Research and Applications, 6th ed. 2018; Ralph P et al. arXiv:2010.03525",
        aliases=("case-study", "studi kasus", "kasus"),
        detect=r"case study research|case study (?:design|method|approach)|exploratory case study|multiple[- ]case|single[- ]case|metode studi kasus|pendekatan studi kasus|desain studi kasus",
        method_signals=(
            ("case definition and unit of analysis", r"unit of analysis|unit analisis|the case|kasus (?:dalam|yang)|case is"),
            ("case selection rationale", r"select|pilih|chosen|dipilih|rationale|alasan|criteria|kriteria|purposive"),
            ("context description", r"context|konteks|organi[sz]ation|organisasi|company|perusahaan|setting"),
            ("multiple data sources", r"interview|wawancara|document|dokumen|observation|observasi|archival|arsip|artefact|log"),
            ("analysis procedure", r"pattern matching|cross-case|within-case|lintas kasus|chain of evidence|coding|koding|thematic|tematik|explanation building"),
            ("validity tactics", r"triangulat|construct validity|validitas konstruk|member check|case study protocol|protokol studi kasus|database"),
        ),
        repro_signals=(_ETHICS, ("case study protocol", r"case study protocol|protokol|appendix|lampiran")),
        results_signals=(
            ("case narrative or within-case findings", r"finding|temuan|case|kasus"),
            ("evidence from multiple sources", r"interview|wawancara|document|dokumen|observation|observasi"),
        ),
    ),
    # ---------------------------------------------------- design & development
    ResearchDesign(
        key="design_science",
        label="Design science research (artefact building)",
        family="empirical",
        category="design and development",
        guideline="Design Science Research Methodology (DSRM, six activities); Hevner's guidelines",
        reference="Peffers K et al. J Manag Inf Syst 2007;24(3):45-77; Hevner AR et al. MIS Q 2004;28(1):75-105",
        url="https://doi.org/10.2753/MIS0742-1222240302",
        aliases=("dsr", "dsrm", "design-science", "design research", "rekayasa"),
        detect=r"design science|\bdsrm?\b|design research methodology|peffers|hevner|penelitian desain|artefak (?:it|ti|sistem)|it artifact|artifact design",
        # DSR names a methodology; ML and system words name what the artefact
        # is built from. A study that names DSR twice builds an artefact with
        # an LLM, it does not run an ML experiment on one.
        outranks=("ml_experiment", "engineering_research"),
        method_signals=(
            ("problem identification and motivation", r"problem|masalah|motivat|motivasi|identifikasi"),
            ("objectives of a solution", r"objective|tujuan solusi|requirement|kebutuhan|kriteria keberhasilan|success criteria"),
            ("design and development of the artefact", r"artefact|artifact|artefak|prototype|prototipe|architecture|arsitektur|design and development|perancangan|pengembangan"),
            ("demonstration", r"demonstrat|demonstrasi|use case|skenario|scenario|proof of concept|instantiat|studi kasus"),
            ("evaluation", r"evaluat|evaluasi|usability|\bsus\b|user acceptance|\buat\b|\btam\b|black-?box|white-?box|performance|kinerja|expert review"),
            ("grounding in theory", r"kernel theory|justificatory|theory|teori|design principle|prinsip desain"),
        ),
        repro_signals=(_CODE_AVAILABLE, ("artefact specification", r"specification|spesifikasi|diagram|uml|erd|flowchart|appendix|lampiran")),
        results_signals=(
            ("evaluation results against objectives", r"evaluat|evaluasi|score|skor|result|hasil"),
            ("artefact description", r"\\begin\{figure|interface|antarmuka|screenshot|tampilan|module|modul"),
        ),
        notes="Communication, DSRM's sixth activity, is the paper itself.",
    ),
    ResearchDesign(
        key="research_development",
        label="Research and development (R&D) of a product",
        family="empirical",
        category="design and development",
        guideline="R&D models: Borg & Gall (10 steps), ADDIE (5 phases), 4D (Thiagarajan), Plomp",
        reference="Borg WR, Gall MD. Educational Research: An Introduction, 1983/1989; Branch RM. Instructional Design: The ADDIE Approach. Springer 2009; Thiagarajan S et al. 1974",
        aliases=("r&d", "rnd", "penelitian pengembangan", "addie", "4d", "borg-gall", "development research"),
        detect=r"research and development|penelitian (?:dan )?pengembangan|\br\s*&\s*d\b|\brnd\b|borg (?:and|&|dan) gall|\baddie\b|model 4-?d|thiagarajan|plomp|development research",
        method_signals=(
            ("development model", r"borg|gall|addie|4-?d|thiagarajan|plomp|dick (?:and|&|dan) carey|hannafin|rowntree|sugiyono|model pengembangan"),
            ("needs analysis", r"needs analysis|analisis kebutuhan|studi pendahuluan|preliminary|potensi dan masalah|define|pendefinisian|analysis phase|tahap analisis"),
            ("product design", r"desain produk|perancangan|storyboard|flowchart|design phase|tahap desain|prototype|prototipe"),
            ("expert validation", r"validasi ahli|validator|ahli (?:materi|media|bahasa)|expert (?:judg|validation|review)|lembar validasi|aiken"),
            ("revision", r"revisi|perbaikan|revision|refine"),
            ("trial", r"uji coba|try-?out|field test|uji lapangan|uji (?:kelompok )?(?:kecil|terbatas|luas)|small group|one-to-one|implementation|implementasi"),
            ("product quality criteria", r"kelayakan|validity|validitas|kepraktisan|practicality|keefektifan|efektivitas|effectiveness|kevalidan"),
            ("data analysis", r"likert|persentase|percentage|aiken|n-?gain|t-test|uji[- ]t|skala|kategori"),
        ),
        repro_signals=(
            _INSTRUMENT_APPENDIX,
            ("validator identities and expertise", r"validator|ahli|expert|dosen|lecturer|praktisi"),
            _ETHICS,
        ),
        results_signals=(
            ("validation scores", r"validasi|validation|valid|layak|feasib|aiken"),
            ("practicality or user response", r"praktis|practical|respon|response|kepuasan|satisfaction"),
            ("effectiveness", r"efektif|effective|n-?gain|peningkatan|improvement|pretest|posttest"),
            ("revisions made", r"revisi|perbaikan|revision|saran"),
        ),
        notes=(
            "Common in Indonesian education and informatics theses; report which "
            "model was used and which steps were carried out or omitted."
        ),
    ),
    # ------------------------------------------------------------------ action
    ResearchDesign(
        key="classroom_action_research",
        label="Classroom action research (PTK)",
        family="empirical",
        category="action research",
        parent="action_research",
        guideline="Kemmis & McTaggart cycle (plan, act and observe, reflect)",
        reference="Kemmis S, McTaggart R. The Action Research Planner, 1988; Arikunto S. Penelitian Tindakan Kelas",
        aliases=("ptk", "penelitian tindakan kelas", "classroom-action-research", "car"),
        # Not the "PTK" in student numbers such as 23/525636/PTK/15370.
        detect=r"penelitian tindakan kelas|(?<![/\w])ptk(?![/\w])|classroom action research",
        method_signals=(
            ("subjects and setting", r"subjek penelitian|subject|siswa|peserta didik|students|kelas [ivx\d]+|lokasi|sekolah"),
            ("cycle model", r"siklus|cycle|kemmis|mc ?taggart|arikunto|elliott|kurt lewin"),
            ("planning", r"perencanaan|planning|rencana tindakan|\brpp\b|modul ajar|lesson plan"),
            ("action", r"pelaksanaan tindakan|tindakan|acting|action"),
            ("observation", r"observasi|pengamatan|observation|observer|lembar observasi"),
            ("reflection", r"refleksi|reflection|reflect"),
            ("success indicators", r"indikator keberhasilan|kriteria keberhasilan|ketuntasan|\bkkm\b|\bkktp\b|success (?:criteria|indicator)"),
            ("data collection and analysis", r"\btes\b|test|lembar|instrumen|analisis data|deskriptif|persentase|rata-rata"),
        ),
        repro_signals=(_INSTRUMENT_APPENDIX, ("baseline condition", r"pra-?siklus|pre-?cycle|kondisi awal|baseline")),
        results_signals=(
            ("per-cycle comparison", r"siklus (?:i|1)\b[\s\S]{0,400}siklus (?:ii|2)\b|cycle (?:i|1)\b[\s\S]{0,400}cycle (?:ii|2)\b|pra-?siklus"),
            ("indicator attainment", r"tercapai|achieved|ketuntasan klasikal|memenuhi (?:kriteria|indikator)|met the (?:criteria|indicator)"),
            ("reflection outcomes", r"refleksi|reflection|kendala|obstacle|perbaikan"),
        ),
    ),
    ResearchDesign(
        key="action_research",
        label="Action research",
        family="empirical",
        category="action research",
        guideline="Action research cycle; ACM SIGSOFT Action Research standard",
        reference="Kemmis S, McTaggart R 1988; Ralph P et al. arXiv:2010.03525",
        aliases=("action-research", "penelitian tindakan", "participatory action research", "par"),
        detect=r"action research|penelitian tindakan|participatory action",
        method_signals=(
            ("problem and context", r"problem|masalah|context|konteks|organi[sz]ation|organisasi|setting"),
            ("collaboration with practitioners", r"practitioner|praktisi|collaborat|kolaborasi|partner|mitra|participant"),
            ("cycle structure", r"cycle|siklus|iteration|iterasi"),
            ("planning", r"plan|perencanaan|rencana"),
            ("intervention", r"intervention|intervensi|action|tindakan"),
            ("observation and data collection", r"observ|pengamatan|interview|wawancara|data collection|pengumpulan data"),
            ("reflection", r"reflect|refleksi|lessons learned|pembelajaran"),
        ),
        repro_signals=(_ETHICS, _INSTRUMENT_APPENDIX),
        results_signals=(
            ("outcomes per cycle", r"cycle|siklus|iteration|iterasi"),
            ("change achieved", r"improv|peningkatan|change|perubahan"),
        ),
    ),
    # ---------------------------------------------- artefacts and benchmarks
    ResearchDesign(
        key="dataset_benchmark",
        label="Dataset or benchmark paper",
        family="empirical",
        category="quantitative",
        guideline="Datasheets for Datasets; NeurIPS Datasets and Benchmarks track",
        reference="Gebru T et al. Datasheets for Datasets. Commun ACM 2021;64(12):86-92",
        url="https://arxiv.org/abs/1803.09010",
        aliases=("dataset", "benchmark", "corpus", "dataset-paper"),
        # Releasing a resource, not using one: "we introduce a new dataset",
        # "we propose T2ER, a benchmark", not "the MIMIC benchmark dataset" or
        # "codes present in the dataset".
        detect=(
            r"(?:introduce|present|release|construct|build|propose|curate|create)s?\s+"
            r"(?:a|an|our)\s+(?:new\s+|novel\s+|first\s+|large-scale\s+|public\s+|open(?:-source)?\s+)*"
            r"(?:[\w+-]+\s+){0,3}(?:benchmark|dataset|corpus|test suite|test-?bed)\b"
            r"|(?:introduce|propose|present|release)s?\s+[\w+-]+,\s+(?:a|an|the\s+first)\s+"
            r"(?:[\w,-]+\s+){0,5}(?:benchmark|dataset|corpus|test-?bed)\b"
            r"|\bdatasheet\b"
        ),
        title_boost=r"bench(?:mark)?|dataset|corpus|test-?bed",
        # A benchmark paper also trains baselines; named twice (or once with
        # a benchmark title) it is the benchmark.
        outranks=("ml_experiment",),
        method_signals=(
            ("motivation and gap the dataset fills", r"motivat|gap|lack|no (?:existing|public)|limited|kurang"),
            ("data source and collection", r"collect|source|crawl|scrap|sampled|obtained from|dikumpulkan|sumber data"),
            ("annotation or labelling procedure", r"annotat|label|anotasi|pelabelan|guideline"),
            ("annotator agreement", r"agreement|kappa|krippendorff|inter-?annotator|inter-?rater"),
            ("splits and statistics", r"split|train|test set|validation set|statistic|distribution"),
            ("licence and access", r"licen[cs]e|cc-by|cc by|terms of use|access|lisensi"),
            ("intended uses and limitations", r"intended use|limitation|bias|misuse|keterbatasan"),
            ("baseline evaluation", r"baseline|we evaluate|evaluation|benchmark"),
        ),
        repro_signals=(
            ("dataset available", r"huggingface|zenodo|github\.com|figshare|kaggle|physionet|available at|tersedia di"),
            _CODE_AVAILABLE,
            ("datasheet or documentation", r"datasheet|data card|dataset card|documentation|dokumentasi"),
        ),
        results_signals=(
            ("baseline results", r"baseline|accuracy|f1|auc|score|akurasi"),
            ("dataset statistics", r"statistic|distribution|number of|jumlah|average length"),
        ),
        notes="Benchmarks that only report model scores are judged as ML experiments.",
    ),
    ResearchDesign(
        key="engineering_research",
        label="Engineering research (system, tool or architecture)",
        family="empirical",
        category="design and development",
        guideline="ACM SIGSOFT Empirical Standards: Engineering Research",
        reference="Ralph P et al. ACM SIGSOFT Empirical Standards, arXiv:2010.03525",
        url="https://www2.sigsoft.org/EmpiricalStandards/",
        aliases=("engineering", "system-paper", "tool-paper", "architecture", "sistem"),
        detect=(
            r"decision support system|sistem pendukung keputusan|reference architecture"
            r"|system architecture|arsitektur sistem|we (?:design|develop|build|implement|present)\s+"
            r"(?:a|an)\s+(?:[\w+-]+\s+){0,3}(?:system|tool|platform|infrastructure|architecture|prototype)\b"
        ),
        min_hits=2,
        method_signals=(
            ("problem and motivation", r"problem|challenge|motivat|masalah"),
            ("artefact description", r"system|tool|platform|architecture|component|module|sistem|komponen"),
            ("design rationale", r"design decision|rationale|we chose|trade-?off|alasan|requirement|kebutuhan"),
            ("comparison with the state of the art", r"state[- ]of[- ]the[- ]art|existing (?:systems|tools|approaches)|compared|baseline|related work"),
            ("evaluation", r"evaluat|experiment|case study|user study|benchmark|evaluasi|pengujian"),
            ("limitations and threats", r"limitation|threat|keterbatasan|drawback"),
        ),
        repro_signals=(_CODE_AVAILABLE, ("artefact specification", r"diagram|figure|specification|spesifikasi|pseudocode|algorithm")),
        results_signals=(
            ("evaluation results", r"result|hasil|performance|accuracy|latency|throughput|score"),
            ("comparison results", r"compared|outperform|baseline|than|dibanding"),
        ),
    ),
    # ------------------------------------------------------------ conceptual
    # Non-empirical papers, after Wieringa et al. (2006): philosophical papers
    # (a new method, framework or taxonomy) and opinion papers. Neither has a
    # Method section, so their items are looked for across the whole text, and
    # they are detected from the article-type label in the opening only.
    ResearchDesign(
        key="methodological_paper",
        label="Methodological or framework paper",
        family="conceptual",
        category="conceptual",
        guideline=(
            "No consensus reporting guideline; Wieringa et al. criteria for philosophical "
            "papers; MISTIC (in development) for methodological studies in health research"
        ),
        reference=(
            "Wieringa R, Maiden N, Mead N, Rolland C. Requirements Eng 2006;11:102-107; "
            "Lawson DO et al. BMJ Open 2020;10:e040478"
        ),
        url="https://doi.org/10.1007/s00766-005-0021-6",
        aliases=("methodological", "method-paper", "framework-paper", "research-essay", "guide", "metodologis"),
        detect=(
            r"research essay|methodological (?:paper|article|note|contribution|guidance)"
            r"|(?:a|this)\s+(?:practical\s+)?guide\s+(?:to|for)\s+(?:conducting|writing|doing|carrying out|choosing)"
            # Not "research framework": empirical papers "present a research
            # framework" and then test it.
            r"|(?:develops?|proposes?|presents?|introduces?)\s+(?:a|an)\s+(?:[\w-]+\s+){0,3}research\s+"
            r"(?:methodology|method|process(?: model)?|guidelines?)\b"
            r"|choosing\s+an?\s+(?:[\w-]+\s+){0,3}research\s+methodology"
        ),
        method_signals=(
            ("problem or gap in existing methods", r"gap|lack|problem|shortcoming|limitation|challenge|celah|kekurangan"),
            ("grounding in prior literature", r"et al|literature|\(\d{4}\)|\[\d+\]|pustaka"),
            ("the proposed method, framework or taxonomy", r"framework|methodology|guideline|process model|taxonomy|steps|stages|kerangka|tahap"),
            ("illustration or application", r"illustrat|example|case|demonstrat|application|contoh|ilustrasi"),
            ("evaluation or justification", r"evaluat|validat|justif|assess|compar|evaluasi"),
            ("scope and limitations", r"limitation|scope|boundar|keterbatasan|batasan"),
        ),
        results_signals=(
            ("implications or guidance for researchers", r"implication|recommend|guidance|should|implikasi|rekomendasi"),
        ),
        notes="Detected from the article-type label or self-description in the opening.",
    ),
    ResearchDesign(
        key="position_paper",
        label="Position paper, editorial, commentary or perspective",
        family="conceptual",
        category="conceptual",
        guideline="No reporting guideline; Wieringa et al. criteria for opinion papers",
        reference="Wieringa R, Maiden N, Mead N, Rolland C. Requirements Eng 2006;11:102-107",
        url="https://doi.org/10.1007/s00766-005-0021-6",
        aliases=("position", "editorial", "commentary", "perspective", "opinion", "viewpoint", "opini"),
        # Labels, not words: "from the viewpoint of" or "editorial board" in a
        # journal header must not make a research article an opinion piece.
        detect=(
            r"(?m)guest editorial|^[ \t]*editorial\b(?!\s+(?:board|office|team|policy|policies|process|manager|staff))"
            r"|(?:this|in this|our) (?:editorial|commentary|perspective|viewpoint|position paper)\b"
            r"|position paper|perspective article|viewpoint article|opinion paper|^[ \t]*commentary[ \t]*$"
        ),
        method_signals=(
            ("the position or thesis", r"argue|contend|position|we posit|we propose that|claim|berpendapat|argumen"),
            ("supporting evidence", r"et al|evidence|stud(?:y|ies)|data|\[\d+\]|bukti"),
            ("counterarguments considered", r"however|although|critics|counter|on the other hand|namun|meskipun"),
            ("implications or call to action", r"implication|recommend|call for|should|next steps|implikasi|rekomendasi"),
        ),
        notes="Detected from the article-type label in the opening.",
    ),
)

# Suggested Method subsections per design, in the order the guideline reports them.
_METHOD_OUTLINES: dict[str, tuple[str, ...]] = {
    "meta_analysis": ("Eligibility criteria", "Information sources and search strategy",
                      "Selection process", "Data collection", "Risk of bias assessment",
                      "Effect measures", "Synthesis and heterogeneity",
                      "Reporting bias and certainty of evidence"),
    "systematic_review": ("Eligibility criteria", "Information sources and search strategy",
                          "Selection process", "Data collection", "Risk of bias assessment",
                          "Synthesis methods"),
    "scoping_review": ("Protocol and framework", "Eligibility criteria",
                       "Information sources and search", "Selection of sources of evidence",
                       "Data charting", "Collating and summarising the results"),
    "bibliometric": ("Data source and search query", "Data cleaning and deduplication",
                     "Bibliometric indicators", "Science mapping and software"),
    "narrative_review": ("Literature search", "Selection of literature", "Synthesis approach"),
    "rct": ("Trial design", "Participants", "Interventions", "Outcomes", "Sample size",
            "Randomisation and allocation concealment", "Blinding", "Statistical methods"),
    "quasi_experiment": ("Research design", "Participants and group assignment",
                         "Intervention", "Instruments", "Data analysis and prerequisite tests"),
    "observational": ("Study design", "Setting", "Participants", "Variables",
                      "Data sources and measurement", "Bias", "Study size",
                      "Statistical methods"),
    "survey": ("Population and sample", "Instrument", "Validity and reliability",
               "Data collection and response rate", "Data analysis"),
    "diagnostic_accuracy": ("Participants", "Index test", "Reference standard",
                            "Blinding", "Analysis"),
    "prediction_model": ("Data source", "Outcome", "Predictors", "Sample size",
                         "Missing data", "Model development", "Validation and performance",
                         "Fairness"),
    "ml_experiment": ("Datasets and splits", "Models and baselines",
                      "Training and hyperparameters", "Evaluation protocol",
                      "Implementation and compute"),
    "empirical": ("Research design", "Participants or data", "Procedure", "Data analysis"),
    "qualitative": ("Approach and paradigm", "Researcher reflexivity",
                    "Setting and participants", "Data collection", "Data analysis",
                    "Trustworthiness", "Ethics"),
    "mixed_methods": ("Design and rationale", "Quantitative strand", "Qualitative strand",
                      "Integration"),
    "case_study": ("Case and unit of analysis", "Case selection", "Data sources",
                   "Analysis", "Validity"),
    "design_science": ("Problem identification and motivation", "Objectives of the solution",
                       "Design and development", "Demonstration", "Evaluation"),
    "research_development": ("Development model", "Needs analysis", "Product design",
                             "Expert validation", "Trial", "Data analysis"),
    "classroom_action_research": ("Setting and subjects", "Cycle procedure",
                                  "Success indicators", "Instruments and data analysis"),
    "action_research": ("Context and partners", "Cycle structure", "Data collection",
                        "Reflection"),
    "dataset_benchmark": ("Motivation", "Data sources and collection", "Annotation",
                          "Quality control and agreement", "Splits and statistics",
                          "Licence, access and intended use", "Baselines"),
    "engineering_research": ("Problem and requirements", "Design and architecture",
                             "Implementation", "Evaluation", "Comparison with existing systems"),
    "methodological_paper": ("Problem with current practice", "Foundations",
                             "The proposed method or framework", "Illustration or application",
                             "Evaluation or justification", "Scope and limitations"),
    "position_paper": ("The position", "Background", "Arguments and evidence",
                       "Counterarguments", "Implications"),
}
_DESIGNS = tuple(
    replace(design, method_outline=_METHOD_OUTLINES.get(design.key, design.method_outline))
    for design in _DESIGNS
)

DESIGNS: Mapping[str, ResearchDesign] = {design.key: design for design in _DESIGNS}
RESEARCH_DESIGNS: tuple[str, ...] = tuple(DESIGNS)

_REVIEW_FAMILY_DEFAULT = "systematic_review"
_EMPIRICAL_FAMILY_DEFAULT = "empirical"
_FAMILY_DEFAULTS = {
    "review": _REVIEW_FAMILY_DEFAULT,
    "empirical": _EMPIRICAL_FAMILY_DEFAULT,
    "conceptual": "position_paper",
}


def _alias_table() -> dict[str, str]:
    table: dict[str, str] = {}
    for design in _DESIGNS:
        for name in (design.key, *design.aliases):
            normalised = re.sub(r"[\s_-]+", "_", name.strip().lower())
            table.setdefault(normalised, design.key)
    return table


_ALIASES = _alias_table()


def get_design(key: str) -> ResearchDesign:
    normalised = re.sub(r"[\s_-]+", "_", str(key).strip().lower())
    found = _ALIASES.get(normalised)
    if found is None:
        raise ValueError(
            f"unknown research_design {key!r}; choose one of: " + ", ".join(RESEARCH_DESIGNS)
        )
    return DESIGNS[found]


# Guideline names spelled out in full mention other designs by accident: every
# PRISMA citation says "Systematic Reviews and Meta-Analyses".
_GUIDELINE_EXPANSIONS = re.compile(
    r"preferred reporting items for systematic reviews? and meta-?analy[sz]e?s"
    r"(?:\s+extension for scoping reviews)?",
    re.IGNORECASE,
)


# Mentions that deny a design are not evidence for it ("a meta-analysis was not
# conducted", "Synthesis Without Meta-analysis", "rather than an exhaustive
# systematic review").
_NEGATED_MENTIONS = re.compile(
    r"(?:synthesis\s+)?without\s+meta-?analy\w*"
    r"|meta-?analy\w*\s+(?:was|were|could|is)\s+not\s+(?:be\s+)?"
    r"(?:conducted|performed|feasible|possible|undertaken|done|appropriate)"
    r"|(?:\bno|not\s+(?:conduct|perform)(?:ed)?\s+a|did\s+not\s+(?:conduct|perform)\s+a)\s+meta-?analy\w*"
    r"|rather\s+than\s+(?:an?\s+)?(?:\w+\s+)?systematic\s+(?:literature\s+)?review"
    r"|not\s+(?:meant\s+to\s+be\s+|intended\s+(?:to\s+be\s+|as\s+))?an?\s+(?:\w+\s+)?"
    r"systematic\s+(?:literature\s+)?(?:review|survey)"
    r"|tidak\s+dilakukan\s+meta-?analisis|meta-?analisis\s+tidak\s+dilakukan"
    # Sugiyono's textbook "Metode Penelitian Kuantitatif, Kualitatif, dan R&D",
    # cited in most Indonesian theses, is not an R&D design.
    r"|kualitatif,?\s+(?:dan|and)\s+r\s*&\s*d\b"
    # Other people's reviews: "a 2025 systematic review by du Preez et al.",
    # "recent systematic review evidence", "previous scoping reviews".
    r"|(?:previous|prior|earlier|existing|recent|another|other|several|many|past)\s+"
    r"(?:\w+\s+){0,2}(?:systematic|scoping|literature|narrative)\s+(?:literature\s+)?reviews?"
    r"|(?:systematic|scoping|narrative)\s+(?:literature\s+)?reviews?\s+(?:by|from)\s+\w+",
    re.IGNORECASE,
)
# The reference list names other people's designs ("Systematic review of
# discharge coding accuracy"); detection stops at the last references heading.
_REFERENCES_HEADING = re.compile(
    r"^[ \t]*(?:[IVX\d]+\.?[ \t]*)?(?:references|bibliography|daftar pustaka|referensi"
    r"|literature cited|works cited)[ \t]*$"
    r"|\\begin\{thebibliography\}|\\bibliography\{|\\printbibliography",
    re.IGNORECASE | re.MULTILINE,
)
def detection_text(text: str) -> str:
    """The text design and family detection read: the body before the
    reference list, at most 20,000 characters, with spelled-out guideline names
    and denied designs removed."""

    headings = list(_REFERENCES_HEADING.finditer(text))
    # The last heading, so a thesis table of contents listing "Daftar Pustaka"
    # does not cut the whole thesis; only when it sits past the opening.
    if headings and headings[-1].start() > len(text) * 0.3:
        text = text[: headings[-1].start()]
    head = text[:DETECTION_WINDOW]
    # A thesis states its design in the method chapter (BAB III), which sits
    # well past the opening window; read that chapter too.
    method = _METHOD_CHAPTER_RE.search(text)
    if method and method.start() >= DETECTION_WINDOW:
        following = _CHAPTER_HEADING_RE.search(text, method.end())
        end = following.start() if following else len(text)
        head += "\n" + text[method.start():min(end, method.start() + DETECTION_WINDOW)]
    head = _GUIDELINE_EXPANSIONS.sub(" ", head)
    return _NEGATED_MENTIONS.sub(" ", head)


DETECTION_WINDOW = 20000
_CHAPTER_HEADING_RE = re.compile(r"\\chapter\*?\s*\{")
_METHOD_CHAPTER_RE = re.compile(
    r"\\chapter\s*\{[^{}]*(?:metode|metodologi|method|research design|rancangan penelitian)[^{}]*\}",
    re.IGNORECASE,
)


_detection_text = detection_text


def _matches(design: ResearchDesign, head: str) -> tuple[list[str], list[str]]:
    """Phrases matching ``design``'s strong and weak detection patterns."""

    strong = [m.group(0) for m in re.finditer(design.detect, head, re.IGNORECASE)] if design.detect else []
    weak = (
        [m.group(0) for m in re.finditer(design.weak_detect, head, re.IGNORECASE)]
        if design.weak_detect
        else []
    )
    return strong, weak


def _counted_hits(head: str) -> tuple[dict[str, int], dict[str, tuple[list[str], list[str]]]]:
    matches = {design.key: _matches(design, head) for design in _DESIGNS}
    strong_named = {
        key for key, (strong, _) in matches.items()
        if len(strong) >= DESIGNS[key].min_hits
    }
    hits: dict[str, int] = {}
    for design in _DESIGNS:
        strong, weak = matches[design.key]
        # Weak evidence (an instrument, not a design) counts only when no other
        # design of the same family names itself.
        rivals = any(
            key != design.key and DESIGNS[key].family == design.family for key in strong_named
        )
        count = len(strong) + (0 if rivals else len(weak))
        if count and design.title_boost and re.search(
            design.title_boost, head[:TITLE_WINDOW], re.IGNORECASE
        ):
            count += 2
        if count and count >= design.min_hits:
            hits[design.key] = count
    return hits, matches


def article_type_label(text: str) -> str | None:
    """The conceptual design an article-type label in the opening names, if any.

    Methodological essays and editorials are not studies, and their bodies
    discuss the designs they are about (an essay on design science names DSR
    on every page), so only a label or self-description near the title counts.
    """

    head = detection_text(text)[:ARTICLE_TYPE_WINDOW]
    found = {
        design.key: len(re.findall(design.detect, head, re.IGNORECASE))
        for design in _DESIGNS
        if design.family == "conceptual" and design.detect
    }
    found = {key: count for key, count in found.items() if count}
    if not found:
        return None
    order = {key: index for index, key in enumerate(RESEARCH_DESIGNS)}
    return min(found, key=lambda key: (-found[key], order[key]))


def design_hits(text: str) -> dict[str, int]:
    """How often each design names itself in the opening of the manuscript."""

    return _counted_hits(_detection_text(text))[0]


def detect_research_design(text: str, *, family: str) -> str:
    """The most specific design of ``family`` that the manuscript names.

    A child design wins over its parent whenever it is named at all (a
    meta-analysis always also calls itself a systematic review); otherwise the
    design named most often wins, ties broken by registry order, which lists
    the more specific designs first.
    """

    if family == "conceptual":
        return article_type_label(text) or _FAMILY_DEFAULTS["conceptual"]
    hits = {
        key: count for key, count in design_hits(text).items() if DESIGNS[key].family == family
    }
    if not hits:
        return _FAMILY_DEFAULTS.get(family, _EMPIRICAL_FAMILY_DEFAULT)
    # A scoping review or bibliometric analysis that selects its records with
    # PRISMA is not thereby a systematic review: named twice, it outranks one.
    for key in list(hits):
        # A design another one outranked cannot outrank in turn.
        if hits.get(key, 0) >= 2:
            for beaten in DESIGNS[key].outranks:
                hits.pop(beaten, None)
    order = {key: index for index, key in enumerate(RESEARCH_DESIGNS)}
    children = [key for key in hits if DESIGNS[key].parent in hits]
    if children:
        return min(children, key=lambda key: (-hits[key], order[key]))
    return min(hits, key=lambda key: (-hits[key], order[key]))


def explain_detection(text: str, *, family: str) -> dict[str, Any]:
    """Why ``detect_research_design`` chose what it chose, for a human to check.

    Lists every candidate design of ``family`` with its hit count and the
    distinct phrases that matched, and rates the choice: ``low`` when nothing
    specific was named (the family's general design applies) or when the
    runner-up is named as often, ``medium`` for a single mention, ``high``
    otherwise. A low rating is the cue to set ``research_design`` by hand.
    """

    chosen = detect_research_design(text, family=family)
    counted_hits, matches = _counted_hits(_detection_text(text))
    candidates: list[dict[str, Any]] = []
    for design in _DESIGNS:
        if design.family != family:
            continue
        strong, weak = matches[design.key]
        found = strong + weak
        if not found:
            continue
        phrases: list[str] = []
        for phrase in found:
            normalised = " ".join(phrase.lower().split())
            if normalised not in phrases:
                phrases.append(normalised)
        candidates.append(
            {
                "key": design.key,
                "label": design.label,
                "hits": counted_hits.get(design.key, len(found)),
                "counted": design.key in counted_hits,
                "min_hits": design.min_hits,
                "matched": phrases[:5],
            }
        )
    candidates.sort(key=lambda item: (item["key"] != chosen, -item["hits"]))
    counted = [item for item in candidates if item["counted"]]
    chosen_hits = next((item["hits"] for item in counted if item["key"] == chosen), 0)
    rivals = [
        item["hits"]
        for item in counted
        if item["key"] != chosen
        and DESIGNS[chosen].parent != item["key"]
        and item["key"] not in DESIGNS[chosen].outranks
    ]
    if not chosen_hits:
        confidence = "low"
        reason = f"no specific {family} design is named; the general standard applies"
    elif rivals and max(rivals) >= chosen_hits:
        confidence = "low"
        reason = "another design is named as often; check which one the study follows"
    elif chosen_hits == 1:
        confidence = "medium"
        reason = "the design is named once"
    else:
        confidence = "high"
        reason = f"the design is named {chosen_hits} times"
    return {
        "family": family,
        "chosen": chosen,
        "confidence": confidence,
        "reason": reason,
        "candidates": candidates,
    }


def design_catalogue() -> list[dict[str, Any]]:
    return [design.to_dict() for design in _DESIGNS]


def design_method_brief(design: ResearchDesign) -> str:
    """Writing guidance for the Method section of ``design``."""

    lines = [
        f"- Reporting standard for this {design.label.lower()}: {design.guideline} "
        f"({design.reference}).",
        "- The Method must state each of: "
        + "; ".join(name for name, _ in design.method_signals)
        + ".",
    ]
    if design.repro_signals:
        lines.append(
            "- Somewhere in the paper, report: "
            + "; ".join(name for name, _ in design.repro_signals)
            + "."
        )
    if design.results_signals:
        lines.append(
            "- The Results are expected to show: "
            + "; ".join(name for name, _ in design.results_signals)
            + " (author-owned; describe only what the authors supplied)."
        )
    if design.method_outline:
        lines.append(
            "- Suggested Method subsections, in order: "
            + "; ".join(design.method_outline)
            + "."
        )
    if design.notes:
        lines.append(f"- Note: {design.notes}")
    return "\n".join(lines)


__all__ = [
    "DESIGNS",
    "DESIGN_FAMILIES",
    "RESEARCH_DESIGNS",
    "STATISTICS_SIGNALS",
    "ResearchDesign",
    "design_catalogue",
    "design_hits",
    "design_method_brief",
    "detect_research_design",
    "explain_detection",
    "article_type_label",
    "detection_text",
    "LITERATURE_SURVEY_RE",
    "get_design",
]

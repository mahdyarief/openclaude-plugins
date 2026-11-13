"""Systematic Literature Review (SLR) engine for journal-scout-mcp.

In-memory state machine for the PRISMA-style stages that are usually kept
loose on disk (collect, screening, full-text decisions, quality appraisal):

    identify -> screening -> eligibility (full-text) -> included

The engine keeps everything in RAM keyed by a stable record id so an agent
can advance a review step by step through MCP calls without managing files.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from .utils import normalize_doi, normalize_title

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


def _stable_id(paper: Dict[str, Any], fallback: str) -> str:
    """Build a deterministic record id from DOI (preferred) or normalized title."""
    doi = normalize_doi(paper.get("doi"))
    if doi:
        return "doi:" + doi.replace("/", "_").replace(".", "_").lower()
    title = normalize_title(paper.get("title") or "")
    base = title or fallback
    return "title:" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


@dataclass
class SLRState:
    """All review state in one place."""

    studies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # id -> {stage, decision, code, reason, reviewer, where, updated_at}
    screening: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # id -> {decision, code, why, where, updated_at}
    full_text: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # id -> {class, items, yes, risk, updated_at}
    appraisal: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # id -> extracted fields dict
    extraction: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    # --- id helpers -------------------------------------------------------

    def _ensure(self, record: Dict[str, Any]) -> str:
        rid = record.get("id") or _stable_id(record, record.get("title", ""))
        record["id"] = rid
        if rid in self.studies:
            existing = self.studies[rid]
            for key, value in record.items():
                if key == "sources":
                    merged = set(existing.get("sources", []))
                    merged.update(value or [])
                    existing["sources"] = sorted(merged)
                elif value not in (None, "", []) and not existing.get(key):
                    existing[key] = value
            return rid
        self.studies[rid] = record
        return rid

    # --- stages -----------------------------------------------------------

    def import_records(
        self, records: Iterable[Dict[str, Any]], dedup: bool = True
    ) -> Dict[str, Any]:
        """Import papers; dedupe by DOI then normalized title when ``dedup``."""
        imported = 0
        deduped = 0
        seen: Dict[str, str] = {}  # key -> id
        for record in records:
            rid = self._ensure(record)
            imported += 1
            if dedup:
                key = None
                doi = record.get("doi")
                if doi:
                    key = "doi:" + normalize_doi(doi)
                if key is None:
                    key = "title:" + normalize_title(record.get("title") or "")
                if key in seen:
                    deduped += 1
                    continue
                seen[key] = rid
        return {
            "imported": imported,
            "deduplicated": deduped,
            "total": len(self.studies),
        }

    def screening_decision(
        self,
        record_id: str,
        decision: str,
        code: str,
        reason: str,
        reviewer: str = "agent",
        where: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a title/abstract screening decision (include / exclude / unclear)."""
        decision = decision.lower()
        if decision not in {"include", "exclude", "unclear"}:
            raise ValueError("decision must be include / exclude / unclear")
        if record_id not in self.studies:
            raise KeyError(f"unknown record id: {record_id}")
        self.screening[record_id] = {
            "stage": "screening",
            "decision": decision,
            "code": code.upper(),
            "reason": reason,
            "reviewer": reviewer,
            "where": where,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.screening[record_id]

    def full_text_decision(
        self,
        record_id: str,
        decision: str,
        code: str,
        why: str,
        where: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a full-text eligibility decision (include / exclude)."""
        decision = decision.lower()
        if decision not in {"include", "exclude"}:
            raise ValueError("decision must be include / exclude")
        if record_id not in self.studies:
            raise KeyError(f"unknown record id: {record_id}")
        self.full_text[record_id] = {
            "stage": "full_text",
            "decision": decision,
            "code": code.upper(),
            "why": why,
            "where": where,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.full_text[record_id]

    def appraisal_decision(
        self,
        record_id: str,
        cls: str,
        items: Dict[str, str],
        risk: str = "low",
    ) -> Dict[str, Any]:
        """Record quality appraisal for an included full-text study."""
        if record_id not in self.studies:
            raise KeyError(f"unknown record id: {record_id}")
        yes = sum(1 for v in items.values() if str(v).strip().upper() in {"Y", "YES", "1", "TRUE"})
        self.appraisal[record_id] = {
            "stage": "appraisal",
            "class": cls,
            "items": items,
            "yes": yes,
            "risk": risk.lower(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.appraisal[record_id]

    def extraction_record(
        self,
        record_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Store extracted study fields (year, class, scores, metrics, ...)."""
        if record_id not in self.studies:
            raise KeyError(f"unknown record id: {record_id}")
        self.extraction[record_id] = {
            "stage": "extraction",
            "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.extraction[record_id]

    # --- PRISMA flow ------------------------------------------------------

    def prisma(self) -> Dict[str, Any]:
        """PRISMA 2020 flow counts from current state."""
        total = len(self.studies)
        screened = len(self.screening)
        advanced_include = sum(1 for v in self.screening.values() if v["decision"] == "include")
        advanced_exclude = sum(1 for v in self.screening.values() if v["decision"] == "exclude")
        advanced_unclear = sum(1 for v in self.screening.values() if v["decision"] == "unclear")

        ft_total = len(self.full_text)
        ft_include = sum(1 for v in self.full_text.values() if v["decision"] == "include")
        ft_exclude = sum(1 for v in self.full_text.values() if v["decision"] == "exclude")

        appraised = len(self.appraisal)
        extracted = len(self.extraction)

        return {
            "identified": total,
            "screened": screened,
            "screening_decisions": {
                "include": advanced_include,
                "exclude": advanced_exclude,
                "unclear": advanced_unclear,
            },
            "full_text_reports_assessed": ft_total,
            "full_text_decisions": {
                "include": ft_include,
                "exclude": ft_exclude,
            },
            "quality_appraised": appraised,
            "extracted": extracted,
            "included_final": ft_include,
        }

    # --- summary ----------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Full review snapshot for an agent or report."""
        prisma = self.prisma()
        studies_by_source: Dict[str, int] = {}
        for study in self.studies.values():
            for src in study.get("sources", []):
                studies_by_source[src] = studies_by_source.get(src, 0) + 1

        screening_codes: Dict[str, int] = {}
        for v in self.screening.values():
            screening_codes[v["code"]] = screening_codes.get(v["code"], 0) + 1

        ft_codes: Dict[str, int] = {}
        for v in self.full_text.values():
            ft_codes[v["code"]] = ft_codes.get(v["code"], 0) + 1

        risk_counts: Dict[str, int] = {}
        for v in self.appraisal.values():
            risk_counts[v["risk"]] = risk_counts.get(v["risk"], 0) + 1

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "meta": self.meta,
            **prisma,
            "studies_by_source": studies_by_source,
            "screening_codes": screening_codes,
            "full_text_codes": ft_codes,
            "risk_distribution": risk_counts,
            "records": [
                {
                    "id": rid,
                    "title": st.get("title"),
                    "year": st.get("year"),
                    "venue": st.get("venue"),
                    "doi": st.get("doi"),
                    "screening": self.screening.get(rid),
                    "full_text": self.full_text.get(rid),
                    "appraisal": self.appraisal.get(rid),
                    "extraction": self.extraction.get(rid),
                }
                for rid, st in self.studies.items()
            ],
        }

    def reset(self) -> None:
        """Clear all review state."""
        self.studies.clear()
        self.screening.clear()
        self.full_text.clear()
        self.appraisal.clear()
        self.extraction.clear()
        self.meta.clear()


# Module-level singleton so tools share state across calls.
STATE = SLRState()


def slr_import_records(records: List[Dict[str, Any]], dedup: bool = True) -> Dict[str, Any]:
    return STATE.import_records(records, dedup=dedup)


def slr_screening(
    record_id: str,
    decision: str,
    code: str,
    reason: str,
    reviewer: str = "agent",
    where: Optional[str] = None,
) -> Dict[str, Any]:
    return STATE.screening_decision(record_id, decision, code, reason, reviewer, where)


def slr_full_text(
    record_id: str,
    decision: str,
    code: str,
    why: str,
    where: Optional[str] = None,
) -> Dict[str, Any]:
    return STATE.full_text_decision(record_id, decision, code, why, where)


def slr_appraisal(
    record_id: str,
    cls: str,
    items: Dict[str, str],
    risk: str = "low",
) -> Dict[str, Any]:
    return STATE.appraisal_decision(record_id, cls, items, risk)


def slr_extraction(record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return STATE.extraction_record(record_id, data)


def slr_prisma() -> Dict[str, Any]:
    return STATE.prisma()


def slr_summary() -> Dict[str, Any]:
    return STATE.summary()


def slr_reset() -> None:
    STATE.reset()


def slr_csv_summary() -> str:
    """Return a CSV table of the review (id, title, stage decisions)."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "id",
            "title",
            "year",
            "venue",
            "doi",
            "screening_decision",
            "screening_code",
            "full_text_decision",
            "full_text_code",
            "appraisal_class",
            "appraisal_yes",
            "appraisal_risk",
        ]
    )
    for rid, st in STATE.studies.items():
        scr = STATE.screening.get(rid, {})
        ft = STATE.full_text.get(rid, {})
        app = STATE.appraisal.get(rid, {})
        writer.writerow(
            [
                rid,
                st.get("title", ""),
                st.get("year", ""),
                st.get("venue", ""),
                st.get("doi", ""),
                scr.get("decision", ""),
                scr.get("code", ""),
                ft.get("decision", ""),
                ft.get("code", ""),
                app.get("class", ""),
                app.get("yes", ""),
                app.get("risk", ""),
            ]
        )
    return out.getvalue()

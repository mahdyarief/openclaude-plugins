"""Participant-flow arithmetic for trials (CONSORT 2025) and observational studies (STROBE).

The PRISMA check in :mod:`paperassist.reporting_checks` follows records through
a review. This module follows people through a study:

* CONSORT 2025 flow diagram (enrolment, allocation, follow-up, analysis):
  ``randomised = assessed - excluded``; the arms' ``allocated`` counts sum to
  ``randomised``; within an arm ``received + not_received = allocated`` and
  ``analysed + excluded_from_analysis = allocated``; nobody is analysed who was
  never allocated. The TREND statement asks for the same flow in
  non-randomised evaluations, so quasi-experiments use it too (without the
  randomisation step, ``allocated`` may sum to ``assessed - excluded``).
* STROBE item 13 (numbers at each stage): every stage is at most the stage
  before it (potentially eligible, examined, eligible, included, followed up,
  analysed), and ``included = eligible - not_participating`` when both are
  given.

Only identities whose every term is reported are checked; the rest are listed
as ``unchecked``. Inequalities (``<=``) are used where a design legitimately
allows a gap, such as intention-to-treat analysis with imputed outcomes.

Input is a JSON document of counts. Arms go under ``arms`` (or ``groups``,
``kelompok``, ``lengan``) as a mapping of arm name to counts, or as a list of
objects with a ``name``. Keys are matched case- and separator-insensitively and
accept common Indonesian names (``dirandomisasi``, ``dianalisis``...).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .reporting_checks import FlowCheck, FlowIdentity, _as_int, _norm_key

FLOW_KINDS = ("consort", "strobe")
ARM_KEYS = ("arms", "groups", "kelompok", "lengan")

_CONSORT_FIELDS: dict[str, tuple[str, ...]] = {
    "assessed": ("assessed", "assessed_for_eligibility", "screened", "eligibility_assessed",
                 "dinilai_kelayakan", "diskrining", "populasi"),
    "excluded": ("excluded", "excluded_enrolment", "not_randomised", "not_randomized",
                 "dieksklusi", "dikeluarkan"),
    "randomised": ("randomised", "randomized", "n_randomised", "n_randomized",
                   "dirandomisasi", "enrolled", "sampel", "sample"),
}
_CONSORT_BREAKDOWNS = ("excluded_reasons", "exclusion_reasons", "reasons_excluded",
                       "alasan_eksklusi")
_ARM_FIELDS: dict[str, tuple[str, ...]] = {
    "allocated": ("allocated", "allocated_to_intervention", "n_allocated", "dialokasikan", "n"),
    "received": ("received", "received_intervention", "received_allocated_intervention",
                 "menerima_intervensi", "menerima"),
    "not_received": ("not_received", "did_not_receive", "did_not_receive_intervention",
                     "tidak_menerima"),
    "lost_to_follow_up": ("lost_to_follow_up", "lost", "loss_to_follow_up",
                          "hilang", "drop_out", "dropout", "mangkir"),
    "discontinued": ("discontinued", "discontinued_intervention", "berhenti"),
    "analysed": ("analysed", "analyzed", "n_analysed", "n_analyzed", "dianalisis"),
    "excluded_from_analysis": ("excluded_from_analysis", "excluded_analysis",
                               "dikeluarkan_dari_analisis"),
}

# STROBE item 13a stages, in order; each is at most the one before it.
_STROBE_STAGES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("potentially_eligible", ("potentially_eligible", "population", "populasi", "approached",
                              "invited", "diundang")),
    ("examined", ("examined", "examined_for_eligibility", "screened", "assessed",
                  "assessed_for_eligibility", "diperiksa")),
    ("eligible", ("eligible", "confirmed_eligible", "memenuhi_kriteria", "layak")),
    ("included", ("included", "included_in_study", "participants", "enrolled", "partisipan",
                  "diikutsertakan", "responden")),
    ("followed_up", ("followed_up", "completed_follow_up", "completing_follow_up",
                     "menyelesaikan")),
    ("analysed", ("analysed", "analyzed", "included_in_analysis", "dianalisis")),
)
_STROBE_NONPARTICIPATION = ("not_participating", "non_participants", "nonparticipants",
                            "declined", "refused", "menolak", "tidak_berpartisipasi")


def _pick(document: Mapping[str, Any], names: Sequence[str]) -> int | None:
    lookup = {_norm_key(key): value for key, value in document.items()}
    for name in names:
        number = _as_int(lookup.get(name))
        if number is not None:
            return number
    return None


def _breakdown(document: Mapping[str, Any], names: Sequence[str]) -> int | None:
    lookup = {_norm_key(key): value for key, value in document.items()}
    for name in names:
        value = lookup.get(name)
        if isinstance(value, Mapping):
            parts = [_as_int(item) for item in value.values()]
            if parts and all(part is not None for part in parts):
                return sum(part for part in parts if part is not None)
    return None


def _arms(document: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    lookup = {_norm_key(key): value for key, value in document.items()}
    for key in ARM_KEYS:
        value = lookup.get(key)
        if isinstance(value, Mapping):
            return [
                (str(name), arm) for name, arm in value.items() if isinstance(arm, Mapping)
            ]
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            arms = [arm for arm in value if isinstance(arm, Mapping)]
            return [
                (str(arm.get("name") or arm.get("arm") or f"arm_{index + 1}"), arm)
                for index, arm in enumerate(arms)
            ]
    return []


def _merge(documents: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Later documents fill keys the earlier ones left out; arms are kept whole."""

    merged: dict[str, Any] = {}
    for document in documents:
        for key, value in document.items():
            if str(key).startswith("_"):
                continue
            merged.setdefault(key, value)
    return merged


def _consort(document: Mapping[str, Any], *, randomised_design: bool) -> FlowCheck:
    values: dict[str, int] = {}
    for canonical, names in _CONSORT_FIELDS.items():
        number = _pick(document, names)
        if number is not None:
            values[canonical] = number
    identities: list[FlowIdentity] = []
    unchecked: list[str] = []

    if {"assessed", "excluded", "randomised"} <= values.keys():
        identities.append(
            FlowIdentity(
                name="enrolment",
                expected=values["assessed"] - values["excluded"],
                reported=values["randomised"],
                formula="assessed - excluded",
            )
        )
    else:
        unchecked.append("enrolment")
    reasons = _breakdown(document, _CONSORT_BREAKDOWNS)
    if reasons is not None and "excluded" in values:
        identities.append(
            FlowIdentity(
                name="excluded_breakdown",
                expected=reasons,
                reported=values["excluded"],
                formula="sum of exclusion reasons",
            )
        )

    arms = _arms(document)
    arm_values: list[tuple[str, dict[str, int]]] = []
    for name, arm in arms:
        counts = {
            canonical: number
            for canonical, names in _ARM_FIELDS.items()
            if (number := _pick(arm, names)) is not None
        }
        arm_values.append((name, counts))
        for canonical, number in counts.items():
            values[f"{name}.{canonical}"] = number

    if not arm_values:
        unchecked.append("allocation")
    else:
        allocated = [counts.get("allocated") for _, counts in arm_values]
        total = values.get("randomised")
        if total is None and not randomised_design and {"assessed", "excluded"} <= values.keys():
            total = values["assessed"] - values["excluded"]
        if total is not None and all(item is not None for item in allocated):
            identities.append(
                FlowIdentity(
                    name="allocation",
                    expected=total,
                    reported=sum(item for item in allocated if item is not None),
                    formula="randomised" if "randomised" in values else "assessed - excluded",
                )
            )
        else:
            unchecked.append("allocation")

    for name, counts in arm_values:
        allocated_n = counts.get("allocated")
        if allocated_n is None:
            unchecked.append(f"{name}.allocated")
            continue
        if {"received", "not_received"} <= counts.keys():
            identities.append(
                FlowIdentity(
                    name=f"{name}.intervention",
                    expected=allocated_n,
                    reported=counts["received"] + counts["not_received"],
                    formula=f"{name}.allocated",
                )
            )
        if "analysed" in counts and "excluded_from_analysis" in counts:
            identities.append(
                FlowIdentity(
                    name=f"{name}.analysis",
                    expected=allocated_n,
                    reported=counts["analysed"] + counts["excluded_from_analysis"],
                    formula=f"{name}.allocated",
                )
            )
        elif "analysed" in counts:
            identities.append(
                FlowIdentity(
                    name=f"{name}.analysis",
                    expected=allocated_n,
                    reported=counts["analysed"],
                    formula=f"{name}.allocated",
                    relation="<=",
                )
            )
        else:
            unchecked.append(f"{name}.analysis")
        lost = counts.get("lost_to_follow_up", 0) + counts.get("discontinued", 0)
        if lost:
            identities.append(
                FlowIdentity(
                    name=f"{name}.follow_up",
                    expected=allocated_n,
                    reported=lost,
                    formula=f"{name}.allocated",
                    relation="<=",
                )
            )
    return FlowCheck(
        fields=values, identities=tuple(identities), unchecked=tuple(unchecked), kind="consort"
    )


def _strobe(document: Mapping[str, Any]) -> FlowCheck:
    values: dict[str, int] = {}
    for stage, names in _STROBE_STAGES:
        number = _pick(document, names)
        if number is not None:
            values[stage] = number
    identities: list[FlowIdentity] = []
    reported = [stage for stage, _ in _STROBE_STAGES if stage in values]
    for before, after in zip(reported, reported[1:], strict=False):
        identities.append(
            FlowIdentity(
                name=f"{after}_within_{before}",
                expected=values[before],
                reported=values[after],
                formula=before,
                relation="<=",
            )
        )
    not_participating = _pick(document, _STROBE_NONPARTICIPATION)
    if not_participating is not None:
        values["not_participating"] = not_participating
        if {"eligible", "included"} <= values.keys():
            identities.append(
                FlowIdentity(
                    name="participation",
                    expected=values["eligible"] - not_participating,
                    reported=values["included"],
                    formula="eligible - not_participating",
                )
            )
    unchecked = [] if len(reported) >= 2 else ["stages"]
    return FlowCheck(
        fields=values, identities=tuple(identities), unchecked=tuple(unchecked), kind="strobe"
    )


def check_participant_flow(
    documents: Sequence[Mapping[str, Any]], *, kind: str = "consort", randomised: bool = True
) -> FlowCheck:
    """Check the participant-flow arithmetic of ``documents``.

    ``kind`` is ``consort`` (trials and non-randomised evaluations; pass
    ``randomised=False`` for a quasi-experiment) or ``strobe``.
    """

    if kind not in FLOW_KINDS:
        raise ValueError(f"participant flow kind must be one of {', '.join(FLOW_KINDS)}")
    document = _merge([doc for doc in documents if isinstance(doc, Mapping)])
    if not document:
        return FlowCheck(kind=kind)
    if kind == "strobe":
        return _strobe(document)
    return _consort(document, randomised_design=randomised)


__all__ = ["ARM_KEYS", "FLOW_KINDS", "check_participant_flow"]

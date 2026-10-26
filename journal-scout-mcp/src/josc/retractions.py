"""Retraction metadata modelled on Zotero's ``retractions.js``.

Zotero maps each retraction to one or more canonical reason keys from the
Retraction Watch taxonomy. This module ships those keys as identifiers so a
consumer can group, filter or render them; the long human-readable paragraphs
that Zotero also carries are intentionally not vendored here.
"""

from dataclasses import dataclass, field
from typing import List, Optional

RETRACTION_REASON_KEYS = frozenset({
    "Author Unresponsive",
    "Bias Issues or Lack of Balance",
    "Breach of Policy by Author",
    "Cites Retracted Work",
    "Civil Proceedings",
    "Complaints about Author",
    "Complaints about Company/Institution",
    "Complaints about Third Party",
    "Compromised Peer Review",
    "Computer-Aided Content or Computer-Generated Content",
    "Concerns/Issues about Animal Welfare",
    "Concerns/Issues about Article",
    "Concerns/Issues about Authorship/Affiliation",
    "Concerns/Issues about Data",
    "Concerns/Issues about Human Subject Welfare",
    "Concerns/Issues about Image",
    "Concerns/Issues about Methods",
    "Concerns/Issues about Peer Review",
    "Concerns/Issues about Referencing/Attributions",
    "Concerns/Issues about Results and/or Conclusions",
    "Concerns/Issues about Third Party Involvement",
    "Conflict of Interest",
    "Contamination of Cell Lines/Tissues",
    "Contamination of Materials",
    "Copyright Claims",
    "Criminal Proceedings",
    "Date of Article and/or Notice Unknown",
    "Doing the Right Thing",
    "Duplication of Content through Error by Journal/Publisher",
    "Duplication of Data",
    "Duplication of/in Article",
    "Duplication of/in Image",
    "Duplication of Text",
    "EOC Lifted",
    "Error by Journal/Publisher",
    "Error by Third Party",
    "Error in Analyses",
    "Error in Cell Lines/Tissues",
    "Error in Data",
    "Error in Image",
    "Error in Materials",
    "Error in Methods",
    "Error in Results and/or Conclusions",
    "Error in Text",
    "Ethical Violations by Author",
    "Ethical Violations by Company/Institution/Third Party",
    "Euphemisms for Duplication",
    "Euphemisms for Misconduct",
    "Euphemisms for Plagiarism",
    "False/Forged Affiliation",
    "False/Forged Authorship",
    "Falsification/Fabrication of Data",
    "Falsification/Fabrication of Image",
    "Falsification/Fabrication of Results",
    "Hoax Paper",
    "Informed/Patient Consent - None/Withdrawn",
    "Investigation by Company/Institution",
    "Investigation by Journal/Publisher",
    "Investigation by ORI",
    "Investigation by Third Party",
    "Lack of Approval from Author",
    "Lack of Approval from Company/Institution",
    "Lack of Approval from Third Party",
    "Lack of IRB/IACUC Approval and/or Compliance",
    "Legal Reasons and/or Threats",
    "Manipulation of Data",
    "Manipulation of Images",
    "Manipulation of Results",
    "Miscommunication with/by Author",
    "Miscommunication with/by Company/Institution",
    "Miscommunication with/by Journal/Publisher",
    "Miscommunication with/by Third Party",
    "Misconduct by Author",
    "Misconduct by Company/Institution",
    "Misconduct by Third Party",
    "Misconduct - Official Investigation(s) and/or Finding(s)",
    "No Further Action",
    "Nonpayment of Fees and/or Refusal to Pay",
    "Notice - Lack of",
    "Notice - Limited or No Information",
    "Notice - Unable to Access via current resources",
    "Not Presented at Conference",
    "Objections by Author(s)",
    "Objections by Company/Institution",
    "Objections by Third Party",
    "Original Data and/or Images not Provided and/or not Available",
    "Paper Mill",
    "Plagiarism of Data",
    "Plagiarism of Image",
    "Plagiarism of/in Article",
    "Plagiarism of Text",
    "Publishing Ban",
    "Results Not Reproducible",
    "Retract and Replace",
    "Rogue Editor",
    "Sabotage of Materials/Methods",
    "Salami Slicing",
    "Taken from Dissertation/Thesis",
    "Taken via Peer Review",
    "Taken via Translation",
    "Temporary Removal",
    "Transfer of Copyright and/or Ownership",
    "Unreliable Data",
    "Unreliable Image",
    "Unreliable Results and/or Conclusions",
    "Updated to Correction",
    "Updated to Expression of Concern",
    "Updated to Retraction",
    "Upgrade/Update of Prior Notice(s)",
    "Withdrawn as Out of Date",
    "Withdrawn to Publish in Different Journal",
})

_REASON_BY_CASEFOLD = {key.casefold(): key for key in RETRACTION_REASON_KEYS}


def normalize_reason(value: Optional[str]) -> Optional[str]:
    """Return the canonical taxonomy key for ``value``, or ``None``."""
    if not value:
        return None
    return _REASON_BY_CASEFOLD.get(value.strip().casefold())


@dataclass
class RetractionInfo:
    """Structured retraction metadata attached to a paper."""

    reasons: List[str] = field(default_factory=list)
    notice_doi: Optional[str] = None
    notice_url: Optional[str] = None
    notice_date: Optional[str] = None
    source: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "reasons": self.reasons,
            "notice_doi": self.notice_doi,
            "notice_url": self.notice_url,
            "notice_date": self.notice_date,
            "source": self.source,
        }

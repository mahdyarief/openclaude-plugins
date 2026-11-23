"""Score the SLR2 manuscript through the real research-OS pipeline.

Kept with the plugin rather than in the manuscript's workspace so the
paper project holds only its own content.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from paperassist.research_os import ResearchOSError, run_research_os


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        r"D:/KuliahS2/riset-jurnal/icd/paper/SLR2-KELAYAKAN-AI"
    )
    try:
        result = run_research_os(
            root,
            {
                "run_id": "slr2-gate-check",
                "target_path": "paper-assist-workspace/main.tex",
                "records_paths": ["sr_work/prisma_flow.json", "sr_work/ft_extraction.json"],
                "ris_paths": ["sr_work/FT_include.ris"],
                "bibliography_path": "paper-assist-workspace/references.bib",
                "fulltext_root": "sr_work/ft_text",
                "depth_target": 500,
                "min_anchored": 0.6,
                "plan_limit": 8,
            },
        )
    except ResearchOSError as exc:
        print(f"ERROR {exc}")
        return 1

    summary = result.ledger.summary()
    print(f"SCORE {result.quality.score:.4f}  {result.quality.grade}  "
          f"{result.quality.recommendation}")
    print(f"claims {summary['claims']}  unsupported {summary['unsupported']}")
    for name in ("depth", "citations", "evidence", "structure", "provenance",
                 "method_rigour", "limitations", "tables_figures", "prose_style",
                 "readability", "abstract"):
        dim = result.quality.dimension(name)
        if dim is None:
            continue
        print(f"{name} {dim.score:.3f} {dim.measurements}")
    print()
    for claim in result.ledger.claims:
        if claim.status == "unsupported":
            print(f"UNSUPPORTED L{claim.line_start} [{claim.section}] "
                  f"q={claim.quantities}")
            print(f"   {claim.sentence[:260]}")
    print()
    for finding in result.quality.findings():
        if finding.severity in ("critical", "warning"):
            print(f"[{finding.severity}] {finding.dimension}: {finding.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
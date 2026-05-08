from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "papers"
INDEX = OUT_DIR / "README.md"


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


PROJECTS = {
    "SemCodebook": {
        "title": "SemCodebook: Structured Provenance Watermarks for Semantic Code Rewrites",
        "short": "structured white-box provenance watermarking",
        "thesis": "A code watermark should survive meaning-preserving rewrites by binding provenance to recoverable program structure rather than to surface tokens.",
        "method": [
            "The encoder distributes provenance over AST, CFG, and SSA carrier families under a keyed schedule.",
            "An error-correcting recovery layer aggregates carrier support and fails closed when evidence is insufficient.",
            "The detector records support family, support level, carrier coverage, ECC state, and abstention reasons instead of forcing labels.",
        ],
        "main_points": [
            "72,000 admitted white-box records over 10 models, 5 model families, and tiny/small/mid/large scale buckets.",
            "23,342/24,000 positive recoveries and 0/48,000 negative-control hits.",
            "43,200 generation-changing ablation rows bind AST/CFG/SSA/ECC/keyed-schedule contribution.",
        ],
        "limitations": [
            "The claim is restricted to admitted white-box cells.",
            "The paper must not claim first-sample/no-retry natural generation.",
            "Baseline comparisons must distinguish official runnable baselines from citation-only or non-equivalent controls.",
        ],
    },
    "CodeDye": {
        "title": "CodeDye: A Conservative Curator-Side Null-Audit for Code Contamination Evidence",
        "short": "black-box sparse null-audit",
        "thesis": "A curator-side audit can preserve low-false-positive contamination evidence without turning sparse signals into provider accusations.",
        "method": [
            "The protocol freezes task hashes, prompt hashes, raw provider transcript hashes, structured payload hashes, and support-row exclusion before interpretation.",
            "The decision rule separates sparse audit signal, positive-control sensitivity, and negative-control false-positive evidence.",
            "Utility-only top-up preserves the 300-row denominator without selecting records by contamination score.",
        ],
        "main_points": [
            "300 claim-bearing DeepSeek live rows with complete hash retention.",
            "4/300 sparse audit signals, 170/300 positive-control hits, and 0/300 negative-control hits.",
            "Support/public rows remain outside the main denominator.",
        ],
        "limitations": [
            "This is not a high-recall contamination detector.",
            "Non-signals are non-accusatory outcomes, not evidence of absence.",
            "Any v4 sensitivity improvement requires a frozen protocol before execution.",
        ],
    },
    "ProbeTrace": {
        "title": "ProbeTrace: Active-Owner Attribution with Source-Bound Semantic Witnesses",
        "short": "active-owner source-bound attribution",
        "thesis": "Attribution should be tested as an owner-bound protocol with decoys, source witnesses, and heldout controls rather than as generic authorship classification.",
        "method": [
            "The protocol binds candidate owners to semantic witnesses and commitment evidence while hiding owner labels from provider prompts.",
            "Wrong-owner, null-owner, random-owner, and same-provider unwrap controls are evaluated beside true-owner rows.",
            "Owner-heldout and task-heldout splits turn perfect single-owner results into a multi-owner margin test.",
        ],
        "main_points": [
            "6,000 claim-bearing DeepSeek multi-owner rows over 5 owners and 3 languages.",
            "750/750 positive owner attributions, 0/5,250 false-attribution controls, and margin AUC 1.0.",
            "APIS-300, transfer-900, anti-leakage, and latency/query frontier artifacts are bound to the final lock.",
        ],
        "limitations": [
            "The claim is DeepSeek-only and source-bound.",
            "The paper must foreground anti-leakage controls because the result is very strong.",
            "Provider-general or cross-provider attribution requires new provider-specific gates.",
        ],
    },
    "SealAudit": {
        "title": "SealAudit: Selective Triage for Watermarks as Security-Relevant Objects",
        "short": "watermark-as-security-object selective triage",
        "thesis": "Watermark evaluation should include safety-relevant audit and abstention surfaces rather than treating every marker as harmless by construction.",
        "method": [
            "The v5 conjunction checks marker-hidden evidence, support traces, executable conditions, threshold sensitivity, and visible-marker diagnostic boundaries.",
            "The audit reports coverage-risk frontier and unsafe-pass bound instead of forcing every ambiguous case into a class.",
            "Expert review is used only as anonymous role-based support and packet confirmation.",
        ],
        "main_points": [
            "320 cases, 960 marker-hidden claim rows, and 320 visible-marker diagnostic rows.",
            "320/960 decisive marker-hidden rows and 0/960 unsafe-pass rows.",
            "Visible-marker rows remain diagnostic-only and cannot enter the main denominator.",
        ],
        "limitations": [
            "This is selective triage, not an automatic safety classifier.",
            "The result is not a harmlessness guarantee or security certificate.",
            "Hard ambiguity and needs-review rows are retained as safety-preserving abstention.",
        ],
    },
}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    main_table = load("results/watermark_submission_main_table_manifest_v1_20260508.json")
    diagnosis = load("results/watermark_submission_gap_diagnosis_v1_20260508.json")
    table_by_project = {row["project"]: row for row in main_table["rows"]}
    diag_by_project = {row["project"]: row for row in diagnosis["projects"]}
    generated = []
    for project, spec in PROJECTS.items():
        path = OUT_DIR / f"{project}.md"
        table = table_by_project[project]
        diag = diag_by_project[project]
        lines = [
            f"# {spec['title']}",
            "",
            f"Generated: `{utc_now()}`",
            "",
            "## One-Sentence Claim",
            "",
            f"{project} studies {spec['short']}. {spec['thesis']}",
            "",
            "## Abstract Draft",
            "",
            (
                f"Source-code watermark evidence is fragile when claims are tied to surface tokens, unscoped provider behavior, "
                f"or unverified safety assumptions. We present {project}, a scoped protocol for {spec['short']}. "
                f"The method fixes its denominator, controls, and claim boundary before interpretation, then reports both positive evidence "
                f"and failure/abstention surfaces. In the current locked evaluation, {table['primary_result']}. "
                f"The result supports the scoped claim only; it does not license the forbidden claims listed below."
            ),
            "",
            "## Contributions",
            "",
            f"1. A scoped mechanism for {spec['short']} with explicit claim boundaries.",
            "2. A fixed-denominator evaluation surface tied to hash-bound artifacts and final claim locks.",
            "3. Negative-control, support-only, and failure-boundary reporting designed to prevent overclaiming.",
            "",
            "## Method Framing",
            "",
        ]
        lines.extend(f"- {item}" for item in spec["method"])
        lines.extend(["", "## Main Result Surface", ""])
        lines.extend(f"- {item}" for item in spec["main_points"])
        lines.extend(["", "Current main-table source artifacts:"])
        lines.extend(f"- `{item['path']}`" for item in table["artifacts"])
        lines.extend(["", "## Best-Paper Gap To Address In Writing", ""])
        for gap in diag["best_paper_gap"]:
            lines.append(f"- `{gap['axis']}` ({gap['severity']}): {gap['issue']} Fix: {gap['fix']}")
        lines.extend(["", "## Limitations And Forbidden Claims", ""])
        lines.extend(f"- {item}" for item in spec["limitations"])
        lines.extend(["", "Forbidden table uses:"])
        lines.extend(f"- {item}" for item in table["forbidden_table_uses"])
        lines.extend(["", "## Reviewer Response Anchors", ""])
        lines.extend(
            [
                "- The main denominator is fixed before interpretation and bound to versioned artifacts.",
                "- Support-only rows do not enter the main denominator.",
                "- Zero-event and perfect-event results must be reported with finite confidence bounds.",
                "- Claims are scoped to the provider/model/cell conditions in the final lock.",
            ]
        )
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        generated.append(path)

    index_lines = [
        "# Paper Briefs",
        "",
        "These files are submission-facing drafting briefs for the four watermark papers. They are not claim-bearing result artifacts; they bind writing to the final claim locks and main-table manifest.",
        "",
    ]
    for path in generated:
        index_lines.append(f"- `{path.relative_to(ROOT).as_posix()}`")
    INDEX.write_text("\n".join(index_lines).rstrip() + "\n", encoding="utf-8")
    print(f"[OK] Wrote {INDEX.relative_to(ROOT)}")
    for path in generated:
        print(f"[OK] Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

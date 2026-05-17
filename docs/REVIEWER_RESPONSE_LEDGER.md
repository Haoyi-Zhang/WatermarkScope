# Reviewer Response Ledger

This ledger is a viva-facing response aid. It uses the submitted FYP evidence surface and keeps continuation work separate.

| Likely challenge | Short response | Evidence to cite | Boundary |
|---|---|---|---|
| Is WatermarkScope claiming a universal code watermark? | No. It evaluates bounded evidence surfaces. | SemCodebook: 23,342/24,000 recoveries and 0/48,000 negative-control hits. | Not universal natural-generation watermarking. |
| Are positive misses hidden? | No. The denominator remains fixed, so misses stay visible. | SemCodebook: 658 misses remain inside 24,000 positive rows. | Do not report only the recovery rate without the denominator. |
| Is CodeDye proving contamination? | No. It is conservative black-box audit evidence. | CodeDye: 6/300 sparse live signals; 170/300 positive controls; 0/300 negative controls. | Not prevalence, provider accusation, high-recall detection, or proof of absence. |
| Is ProbeTrace general authorship attribution? | No. It is scoped active-owner attribution. | ProbeTrace: 300/300 scoped decisions and 0/1,200 false-owner controls. | Not provider-general or cross-provider authorship proof. |
| Is SealAudit a safety classifier? | No. It is selective triage with explicit abstention. | SealAudit: 81/960 decisive triage outcomes and 0 observed unsafe passes. | Not a safety certificate or automatic harmlessness guarantee. |
| Why not rerun everything live? | Full reruns need GPUs, model weights, or provider/API conditions. The live viva route checks inspectability. | README, claim boundaries, traceability matrix, result manifest, and `scripts/viva_check.py`. | The quick check is not a replacement for the full experiments. |

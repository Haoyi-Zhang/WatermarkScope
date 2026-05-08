# Environment

This repository is designed so that the dissertation-level integrity checks run on a normal Python environment, while full experiment reruns can be executed on a GPU/API host.

## Local Integrity Check Environment

Minimum local requirement:

- Python 3.9 or newer.
- No GPU required.
- No API key required.
- No model weights required.

Recommended commands from the repository root:

```bash
python scripts/repro_check.py
python scripts/summarize_all.py
```

These checks use only the Python standard library.

## Dissertation Build Environment

To rebuild the PDF:

```bash
cd dissertation/latex
pdflatex report.tex
bibtex report
pdflatex report.tex
pdflatex report.tex
```

The LaTeX source uses IEEE-style references through `IEEEtran.bst`. The submitted PDF is already included at `dissertation/WatermarkScope_FYP_Dissertation.pdf`.

## Full Experiment Environment

Full reruns are heavier than the repository integrity check. They may require:

- CUDA-capable Linux host for local model experiments,
- PyTorch and model-specific inference dependencies,
- local model weights for white-box experiments,
- provider API access for black-box audit experiments,
- sufficient disk space for raw run payloads and intermediate artifacts.

The included implementation snapshots document the project-specific entry points, but this FYP repository intentionally keeps raw provider secrets and large transient run dumps out of version control.

## Project-Specific Notes

| Module | Local inspection | Full rerun resources |
|---|---|---|
| CodeMarkBench | code, configs, result tables, benchmark docs | GPU host and pinned local model weights |
| SemCodebook | source package, tests, gate scripts, artifacts | white-box model weights and full 72,000-row workload |
| CodeDye | audit scripts, control gates, artifacts | DeepSeek/provider API access for live audit reruns |
| ProbeTrace | attribution/transfer scripts, artifacts | provider API access and transfer-validation resources |
| SealAudit | triage source, scripts, artifacts | benchmark generation, provider judging where configured, triage rerun resources |

## Secret Handling

Credentials are not required for local checks and are not stored in this repository. Any future live rerun should inject keys through the host environment or a local secret manager, not through tracked files.

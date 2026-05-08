# Environment Capture

The canonical release workflow captures the exact execution environment for the reviewer-visible result of record.

The formal public run uses `results/environment/` as the environment-of-record location for the completed single-host 8-GPU canonical run. The release-facing capture must be refreshed on the execution host with the same visible execution class as the canonical matrix before staging a public companion repository.

## What Is Captured

The environment capture records:

- host platform details
- Python executable and version
- `torch`, `transformers`, `numpy`, and `pandas` versions when available
- toolchain versions for `g++`, `javac`, `java`, `node`, and `go`
- `nvidia-smi` output or a clear error if the GPU query is unavailable
- both the physical GPU inventory and the visible execution-class slice selected through `CUDA_VISIBLE_DEVICES`
- the checked-worktree git query result when the execution-host copy still carries VCS metadata

The environment capture does not replace the separate model-roster provenance record or the release-facing code identity. For publication, pair it with the exact released model identifiers, their resolved local snapshot revisions, and the `code_snapshot_digest` documented in the release provenance contract. If the execution host uses a sanitized work copy rather than a live git checkout, that provenance contract remains the authoritative code-identity surface even if the environment capture reports that a git query is unavailable in the working copy.

## Output Files

The canonical capture writes two files:

- a machine-readable JSON summary
- a reviewer-facing Markdown summary

By default, the workflow stores these under `results/environment/`.

Those two files are part of the public release bundle and companion surface.

## How To Capture

Use the dedicated capture script when you need to refresh the environment record for a public release review:

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 python scripts/capture_environment.py --label formal-single-host-full --execution-mode single_host_canonical --output-json results/environment/runtime_environment.json --output-md results/environment/runtime_environment.md
```

Or let the reviewer workflow and remote preflight generate the environment capture as part of their normal execution. For the formal single-host release path, the remote preflight capture is the environment-of-record for rerun-backed results and should preserve the same visible execution class used by the public result-of-record.

## How To Use It

The environment capture is meant to be cited alongside reruns and raw artifacts so that a reviewer can reconstruct the execution context without guessing about toolchains or GPU availability. Read the visible execution-class fields together with the physical GPU inventory: for the formal public run, the result-of-record is locked to one Linux host with `CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7`, even though the underlying host may physically expose more GPUs than the fixed eight-device execution class used by the canonical run. Treat the refreshed single-host capture as the release evidence; do not substitute earlier local captures for the execution-host record.

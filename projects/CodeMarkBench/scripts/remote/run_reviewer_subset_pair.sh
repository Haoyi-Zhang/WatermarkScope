#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEFAULT_REMOTE_VENV="${CODEMARKBENCH_REMOTE_VENV:-}"
VENV_DIR="${VENV_DIR:-$DEFAULT_REMOTE_VENV}"
PYTHON_BIN="${PYTHON_BIN:-}"
GPU_A="${GPU_A:-0}"
GPU_B="${GPU_B:-1}"
GPU_POOL_MODE="${GPU_POOL_MODE:-shared}"
CPU_WORKERS="${CPU_WORKERS:-1}"
RETRY_COUNT="${RETRY_COUNT:-1}"
RESUME=0
PROBE_HF_ACCESS=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: run_reviewer_subset_pair.sh [--python PATH] [--venv PATH] [--gpu-a ID] [--gpu-b ID]
                                   [--gpu-pool-mode split|shared] [--cpu-workers N] [--retry-count N]
                                   [--resume] [--probe-hf-access] [--dry-run]

Runs the canonical reviewer subset pair in parallel with isolated profiles:
  - suite_reviewer_subset_a = Qwen2.5-Coder-14B-Instruct + sweet_runtime + crafted_original
  - suite_reviewer_subset_b = Qwen2.5-Coder-7B-Instruct  + kgw_runtime   + humaneval_plus
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --venv)
      VENV_DIR="$2"
      shift 2
      ;;
    --gpu-a)
      GPU_A="$2"
      shift 2
      ;;
    --gpu-b)
      GPU_B="$2"
      shift 2
      ;;
    --gpu-pool-mode)
      GPU_POOL_MODE="$2"
      shift 2
      ;;
    --cpu-workers)
      CPU_WORKERS="$2"
      shift 2
      ;;
    --retry-count)
      RETRY_COUNT="$2"
      shift 2
      ;;
    --resume)
      RESUME=1
      shift
      ;;
    --probe-hf-access)
      PROBE_HF_ACCESS=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$VENV_DIR/bin/python"
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing Python interpreter: $PYTHON_BIN" >&2
  echo "Create the venv first with: bash $ROOT/scripts/remote/bootstrap_linux_gpu.sh --install --venv $VENV_DIR" >&2
  exit 1
fi

LOG_DIR="$ROOT/results/certifications"
mkdir -p "$LOG_DIR"
SUBSET_A_LOG="$LOG_DIR/subset_a.log"
SUBSET_B_LOG="$LOG_DIR/subset_b.log"

COMMON_ARGS=(
  "$ROOT/scripts/reviewer_workflow.py"
  subset
  --gpu-slots 1
  --gpu-pool-mode "$GPU_POOL_MODE"
  --cpu-workers "$CPU_WORKERS"
  --retry-count "$RETRY_COUNT"
  --python "$PYTHON_BIN"
)

if [[ $RESUME -eq 1 ]]; then
  COMMON_ARGS+=(--resume)
fi
if [[ $PROBE_HF_ACCESS -eq 1 ]]; then
  COMMON_ARGS+=(--probe-hf-access)
fi

SUBSET_A_COMMAND=(
  env "CUDA_VISIBLE_DEVICES=$GPU_A"
  "$PYTHON_BIN"
  "${COMMON_ARGS[@]}"
  --profile suite_reviewer_subset_a
  --models Qwen/Qwen2.5-Coder-14B-Instruct
  --methods sweet_runtime
  --sources crafted_original
)

SUBSET_B_COMMAND=(
  env "CUDA_VISIBLE_DEVICES=$GPU_B"
  "$PYTHON_BIN"
  "${COMMON_ARGS[@]}"
  --profile suite_reviewer_subset_b
  --models Qwen/Qwen2.5-Coder-7B-Instruct
  --methods kgw_runtime
  --sources humaneval_plus
)

if [[ $DRY_RUN -eq 1 ]]; then
  printf '+'
  printf ' %q' "${SUBSET_A_COMMAND[@]}"
  printf '\n'
  printf '+'
  printf ' %q' "${SUBSET_B_COMMAND[@]}"
  printf '\n'
  exit 0
fi

(
  printf '+'
  printf ' %q' "${SUBSET_A_COMMAND[@]}"
  printf '\n'
  "${SUBSET_A_COMMAND[@]}"
) >"$SUBSET_A_LOG" 2>&1 &
PID_A=$!

(
  printf '+'
  printf ' %q' "${SUBSET_B_COMMAND[@]}"
  printf '\n'
  "${SUBSET_B_COMMAND[@]}"
) >"$SUBSET_B_LOG" 2>&1 &
PID_B=$!

STATUS=0
wait "$PID_A" || STATUS=$?
wait "$PID_B" || STATUS=$?
exit "$STATUS"

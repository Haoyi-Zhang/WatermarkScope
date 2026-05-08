#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ORIGINAL_ARGS=("$@")
MANIFEST="configs/matrices/suite_all_models_methods.json"
PROFILE="suite_all_models_methods"
OUTPUT_ROOT="$ROOT/results/matrix"
PYTHON_BIN="${PYTHON_BIN:-}"
DEFAULT_REMOTE_VENV="${CODEMARKBENCH_REMOTE_VENV:-}"
VENV_DIR="${VENV_DIR:-}"
if [[ -z "$VENV_DIR" ]]; then
  if [[ -n "$DEFAULT_REMOTE_VENV" && -d "$DEFAULT_REMOTE_VENV" ]]; then
    VENV_DIR="$DEFAULT_REMOTE_VENV"
  else
    VENV_DIR="$ROOT/.venv/tosem_release"
  fi
fi
GPU_SLOTS="${GPU_SLOTS:-8}"
GPU_POOL_MODE="${GPU_POOL_MODE:-shared}"
CPU_WORKERS="${CPU_WORKERS:-9}"
RETRY_COUNT="${RETRY_COUNT:-1}"
COMMAND_TIMEOUT_SECONDS="${COMMAND_TIMEOUT_SECONDS:-259200}"
DRY_RUN=0
FAIL_FAST=0
SKIP_HF_ACCESS=0

normalize_abs_path() {
  local value="$1"
  local absolute="$value"
  if [[ "$absolute" != /* ]]; then
    absolute="$ROOT/$absolute"
  fi
  python3 - "$absolute" <<'PY'
from pathlib import Path
import sys

print(Path(sys.argv[1]).resolve(strict=False))
PY
}

validate_results_control_path() {
  local path="$1"
  local label="$2"
  python3 - "$ROOT" "$path" "$label" <<'PY'
from pathlib import Path
import os
import sys

root = Path(sys.argv[1]).resolve()
results_root = root / "results"
candidate = Path(sys.argv[2])
label = sys.argv[3]
if not candidate.is_absolute():
    candidate = root / candidate
normalized = Path(os.path.abspath(str(candidate)))
try:
    normalized.relative_to(results_root)
except ValueError:
    raise SystemExit(f"refusing to use {label} outside {results_root}: {normalized}")
current = root
if current.is_symlink():
    raise SystemExit(f"refusing to use {label} through symlinked path components: {current}")
for part in normalized.relative_to(root).parts:
    current = current / part
    if current.is_symlink():
        raise SystemExit(f"refusing to use {label} through symlinked path components: {current}")
print(normalized)
PY
}

ensure_formal_matrix_output_surface_safe() {
  validate_results_control_path "$OUTPUT_PATH/$PROFILE" "formal matrix output directory" >/dev/null
  validate_results_control_path "$OUTPUT_PATH/$PROFILE/matrix_index.json" "formal matrix index" >/dev/null
  validate_results_control_path "$OUTPUT_PATH/$PROFILE/matrix_index.dry_run.json" "formal dry-run matrix index" >/dev/null
}

effective_gpu_slots() {
  "$PYTHON_BIN" - "$GPU_SLOTS" <<'PY'
import os
import sys

requested = max(1, int(sys.argv[1]))
tokens = [token.strip() for token in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if token.strip()]
print(min(requested, len(tokens)) if tokens else requested)
PY
}

normalized_visible_devices() {
  "$PYTHON_BIN" - <<'PY'
import os

tokens = [token.strip() for token in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if token.strip()]
print(",".join(tokens))
PY
}

validate_visible_device_ordinals() {
  "$PYTHON_BIN" - <<'PY'
import os
import subprocess

tokens = [token.strip() for token in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if token.strip()]
if not tokens:
    raise SystemExit("The formal single-host suite contract requires CUDA_VISIBLE_DEVICES to be set.")
if any(not token.isdigit() for token in tokens):
    raise SystemExit(
        "The formal single-host suite contract requires numeric CUDA_VISIBLE_DEVICES ordinals; "
        f"got {','.join(tokens)}."
    )
completed = subprocess.run(
    ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader,nounits"],
    check=True,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
physical = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
missing = [token for token in tokens if token not in physical]
if missing:
    raise SystemExit(
        "The formal single-host suite contract requires CUDA_VISIBLE_DEVICES to reference actual host GPU ordinals; "
        f"missing={missing}, detected={physical}"
    )
PY
}

require_formal_single_host_contract() {
  if [[ "$GPU_SLOTS" != "8" || "$GPU_POOL_MODE" != "shared" || "$CPU_WORKERS" != "9" || "$RETRY_COUNT" != "1" || "$COMMAND_TIMEOUT_SECONDS" != "259200" ]]; then
    echo "The formal single-host suite contract is fixed to --gpu-slots 8 --gpu-pool-mode shared --cpu-workers 9 --retry-count 1 --command-timeout-seconds 259200." >&2
    exit 1
  fi
  FORMAL_VISIBLE_DEVICES="$(normalized_visible_devices)"
  if [[ -z "${CUDA_VISIBLE_DEVICES:-}" ]]; then
    echo "The formal single-host suite contract requires CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7." >&2
    exit 1
  fi
  if [[ "$FORMAL_VISIBLE_DEVICES" != "0,1,2,3,4,5,6,7" ]]; then
    echo "The formal single-host suite contract requires CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7; got $FORMAL_VISIBLE_DEVICES." >&2
    exit 1
  fi
  validate_visible_device_ordinals
  if [[ "$EFFECTIVE_GPU_SLOTS" != "8" ]]; then
    echo "The formal single-host suite contract requires eight visible GPUs; got CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES." >&2
    exit 1
  fi
}

require_formal_release_completion() {
  "$PYTHON_BIN" - "$OUTPUT_PATH" "$PROFILE" <<'PY'
import json
import sys
from pathlib import Path

output_root = Path(sys.argv[1])
profile = sys.argv[2]
matrix_index = output_root / profile / "matrix_index.json"
if not matrix_index.exists():
    raise SystemExit(f"formal single-host completion check could not find matrix index: {matrix_index}")
payload = json.loads(matrix_index.read_text(encoding="utf-8"))
run_count = int(payload.get("run_count", 0) or 0)
success_count = int(payload.get("success_count", 0) or 0)
failed_count = int(payload.get("failed_count", 0) or 0)
execution_mode = str(payload.get("execution_mode", "")).strip()
if run_count != 140 or success_count != 140 or failed_count != 0:
    raise SystemExit(
        "formal single-host publication-facing completion requires "
        f"run_count=140, success_count=140, failed_count=0; observed "
        f"run_count={run_count}, success_count={success_count}, failed_count={failed_count}"
    )
if execution_mode != "single_host_canonical":
    raise SystemExit(
        "formal single-host publication-facing completion requires execution_mode=single_host_canonical; "
        f"observed execution_mode={execution_mode or '<missing>'}"
    )
PY
}

usage() {
  cat <<'EOF'
Usage: run_formal_single_host_full.sh [--manifest PATH] [--profile NAME] [--output-root PATH]
                                      [--python PATH] [--venv PATH]
                                      [--gpu-slots N] [--gpu-pool-mode shared] [--cpu-workers N] [--retry-count N]
                                      [--command-timeout-seconds N] [--skip-hf-access] [--dry-run] [--fail-fast]

This helper is the formal publication-facing one-shot path:
standalone preflight -> clean -> direct canonical full launch.
The older run_suite_matrix.sh wrapper remains available for engineering smoke and A/B precheck workflows.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      MANIFEST="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --venv)
      VENV_DIR="$2"
      shift 2
      ;;
    --gpu-slots)
      GPU_SLOTS="$2"
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
    --command-timeout-seconds)
      COMMAND_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --skip-hf-access)
      SKIP_HF_ACCESS=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --fail-fast|--full-fail-fast)
      FAIL_FAST=1
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

MANIFEST_PATH="$(normalize_abs_path "$MANIFEST")"
OUTPUT_PATH="$(normalize_abs_path "$OUTPUT_ROOT")"

if [[ ! -x "$PYTHON_BIN" && $DRY_RUN -eq 0 ]]; then
  echo "Missing Python interpreter: $PYTHON_BIN" >&2
  echo "Create the venv first with: bash $ROOT/scripts/remote/bootstrap_linux_gpu.sh --install --venv $VENV_DIR" >&2
  exit 1
fi

if [[ "$MANIFEST_PATH" != "$(normalize_abs_path "configs/matrices/suite_all_models_methods.json")" || "$PROFILE" != "suite_all_models_methods" ]]; then
  echo "The formal direct-full helper is reserved for configs/matrices/suite_all_models_methods.json with profile suite_all_models_methods." >&2
  exit 1
fi
OUTPUT_PATH="$(validate_results_control_path "$OUTPUT_PATH" "formal output root")"
CANONICAL_OUTPUT_PATH="$(validate_results_control_path "$ROOT/results/matrix" "formal canonical output root")"
if [[ "$OUTPUT_PATH" != "$CANONICAL_OUTPUT_PATH" ]]; then
  echo "The formal direct-full helper is reserved for repo-local output root results/matrix." >&2
  exit 1
fi
ensure_formal_matrix_output_surface_safe

if [[ $DRY_RUN -eq 1 ]]; then
  cat <<EOF
{
  "root": "$ROOT",
  "manifest": "$MANIFEST_PATH",
  "profile": "$PROFILE",
  "output_root": "$OUTPUT_PATH",
  "python": "$PYTHON_BIN",
  "venv": "$VENV_DIR",
  "gpu_slots": "$GPU_SLOTS",
  "gpu_pool_mode": "$GPU_POOL_MODE",
  "cpu_workers": "$CPU_WORKERS",
  "retry_count": "$RETRY_COUNT",
  "command_timeout_seconds": "$COMMAND_TIMEOUT_SECONDS",
  "skip_hf_access": $SKIP_HF_ACCESS,
  "steps": [
    "standalone_preflight",
    "clean_suite_outputs",
    "run_full_matrix"
  ]
}
EOF
  exit 0
fi

EFFECTIVE_GPU_SLOTS="$(effective_gpu_slots)"
require_formal_single_host_contract

if [[ -z "${CODEMARKBENCH_FORMAL_FULL_DETACHED:-}" ]]; then
  FULL_RUN_DIR="$OUTPUT_PATH/$PROFILE"
  LAUNCHER_RUN_DIR="$ROOT/results/launchers/$PROFILE"
  FULL_LAUNCH_LOCK_DIR="$LAUNCHER_RUN_DIR/formal_full.launch.lock"
  FULL_LAUNCH_REQUESTER_PID="$FULL_LAUNCH_LOCK_DIR/requester_pid"
  FULL_LAUNCH_LOCK_PID="$FULL_LAUNCH_LOCK_DIR/pid"
  FULL_LAUNCH_LOG="$LAUNCHER_RUN_DIR/full_run.launch.log"
  FULL_LAUNCH_STATUS="$LAUNCHER_RUN_DIR/full_run.launch.status"
  FULL_LAUNCH_PID="$LAUNCHER_RUN_DIR/full_run.launch.pid"
  FULL_LAUNCH_SCRIPT="$LAUNCHER_RUN_DIR/full_run.launch.sh"
  ensure_formal_launcher_control_surfaces_safe() {
    validate_results_control_path "$LAUNCHER_RUN_DIR" "formal launcher run directory" >/dev/null
    validate_results_control_path "$FULL_LAUNCH_LOCK_DIR" "formal launcher lock directory" >/dev/null
    validate_results_control_path "$FULL_LAUNCH_REQUESTER_PID" "formal launcher requester pid file" >/dev/null
    validate_results_control_path "$FULL_LAUNCH_LOCK_PID" "formal launcher lock pid file" >/dev/null
    validate_results_control_path "$FULL_LAUNCH_LOG" "formal launcher log" >/dev/null
    validate_results_control_path "$FULL_LAUNCH_STATUS" "formal launcher status" >/dev/null
    validate_results_control_path "$FULL_LAUNCH_PID" "formal launcher pid file" >/dev/null
    validate_results_control_path "$FULL_LAUNCH_SCRIPT" "formal launcher script" >/dev/null
  }
  LAUNCHER_RUN_DIR="$(validate_results_control_path "$LAUNCHER_RUN_DIR" "formal launcher run directory")"
  FULL_LAUNCH_LOCK_DIR="$(validate_results_control_path "$FULL_LAUNCH_LOCK_DIR" "formal launcher lock directory")"
  FULL_LAUNCH_REQUESTER_PID="$(validate_results_control_path "$FULL_LAUNCH_REQUESTER_PID" "formal launcher requester pid file")"
  FULL_LAUNCH_LOCK_PID="$(validate_results_control_path "$FULL_LAUNCH_LOCK_PID" "formal launcher lock pid file")"
  FULL_LAUNCH_LOG="$(validate_results_control_path "$FULL_LAUNCH_LOG" "formal launcher log")"
  FULL_LAUNCH_STATUS="$(validate_results_control_path "$FULL_LAUNCH_STATUS" "formal launcher status")"
  FULL_LAUNCH_PID="$(validate_results_control_path "$FULL_LAUNCH_PID" "formal launcher pid file")"
  FULL_LAUNCH_SCRIPT="$(validate_results_control_path "$FULL_LAUNCH_SCRIPT" "formal launcher script")"
  ensure_formal_launcher_control_surfaces_safe
  mkdir -p "$FULL_RUN_DIR" "$LAUNCHER_RUN_DIR"
  if [[ -d "$FULL_LAUNCH_LOCK_DIR" ]]; then
    EXISTING_LAUNCH_PID=""
    if [[ -f "$FULL_LAUNCH_LOCK_PID" ]]; then
      EXISTING_LAUNCH_PID="$(tr -d '[:space:]' < "$FULL_LAUNCH_LOCK_PID" || true)"
    fi
    if [[ -n "$EXISTING_LAUNCH_PID" ]] && kill -0 "$EXISTING_LAUNCH_PID" 2>/dev/null; then
      echo "Detected active detached launcher control surface for $PROFILE; refusing to start another launch." >&2
      echo "launcher_pid=$EXISTING_LAUNCH_PID" >&2
      exit 1
    fi
    ensure_formal_launcher_control_surfaces_safe
    rm -rf "$FULL_LAUNCH_LOCK_DIR"
  fi
  ensure_formal_launcher_control_surfaces_safe
  mkdir -p "$FULL_LAUNCH_LOCK_DIR"
  printf '%s\n' "$$" > "$FULL_LAUNCH_REQUESTER_PID"
  ORIGINAL_ARGS_ESCAPED="$(printf '%q ' "${ORIGINAL_ARGS[@]}")"
  SELF_ESCAPED="$(printf '%q' "$ROOT/scripts/remote/run_formal_single_host_full.sh")"
  LAUNCHER_RUN_DIR_ESCAPED="$(printf '%q' "$LAUNCHER_RUN_DIR")"
  FULL_LAUNCH_LOCK_DIR_ESCAPED="$(printf '%q' "$FULL_LAUNCH_LOCK_DIR")"
  FULL_LAUNCH_REQUESTER_PID_ESCAPED="$(printf '%q' "$FULL_LAUNCH_REQUESTER_PID")"
  FULL_LAUNCH_LOCK_PID_ESCAPED="$(printf '%q' "$FULL_LAUNCH_LOCK_PID")"
  FULL_LAUNCH_LOG_ESCAPED="$(printf '%q' "$FULL_LAUNCH_LOG")"
  FULL_LAUNCH_STATUS_ESCAPED="$(printf '%q' "$FULL_LAUNCH_STATUS")"
  FULL_LAUNCH_PID_ESCAPED="$(printf '%q' "$FULL_LAUNCH_PID")"
  ensure_formal_launcher_control_surfaces_safe
  cat > "$FULL_LAUNCH_SCRIPT" <<EOF
#!/usr/bin/env bash
set -euo pipefail
validate_results_control_path() {
  local path="\$1"
  local label="\$2"
  python3 - "$ROOT" "\$path" "\$label" <<'PY'
from pathlib import Path
import os
import sys

root = Path(sys.argv[1]).resolve()
results_root = root / "results"
candidate = Path(sys.argv[2])
label = sys.argv[3]
if not candidate.is_absolute():
    candidate = root / candidate
normalized = Path(os.path.abspath(str(candidate)))
try:
    normalized.relative_to(results_root)
except ValueError:
    raise SystemExit(f"refusing to use {label} outside {results_root}: {normalized}")
current = root
if current.is_symlink():
    raise SystemExit(f"refusing to use {label} through symlinked path components: {current}")
for part in normalized.relative_to(root).parts:
    current = current / part
    if current.is_symlink():
        raise SystemExit(f"refusing to use {label} through symlinked path components: {current}")
print(normalized)
PY
}
ensure_formal_launcher_control_surfaces_safe() {
  validate_results_control_path $LAUNCHER_RUN_DIR_ESCAPED "formal launcher run directory" >/dev/null
  validate_results_control_path $FULL_LAUNCH_LOCK_DIR_ESCAPED "formal launcher lock directory" >/dev/null
  validate_results_control_path $FULL_LAUNCH_REQUESTER_PID_ESCAPED "formal launcher requester pid file" >/dev/null
  validate_results_control_path $FULL_LAUNCH_LOCK_PID_ESCAPED "formal launcher lock pid file" >/dev/null
  validate_results_control_path $FULL_LAUNCH_LOG_ESCAPED "formal launcher log" >/dev/null
  validate_results_control_path $FULL_LAUNCH_STATUS_ESCAPED "formal launcher status" >/dev/null
}
cleanup_detached_launcher_lock() {
  if ! ensure_formal_launcher_control_surfaces_safe; then
    echo "Skipping detached launcher lock cleanup because reviewer-facing control surfaces are not safe." >&2
    return
  fi
  if [[ -d $FULL_LAUNCH_LOCK_DIR_ESCAPED ]]; then
    local lock_pid=""
    if [[ -f $FULL_LAUNCH_LOCK_PID_ESCAPED ]]; then
      lock_pid="\$(tr -d '[:space:]' < $FULL_LAUNCH_LOCK_PID_ESCAPED || true)"
    fi
    if [[ -n "\$lock_pid" && "\$lock_pid" == "\$\$" ]]; then
      rm -rf $FULL_LAUNCH_LOCK_DIR_ESCAPED
    fi
  fi
}
trap cleanup_detached_launcher_lock EXIT
ensure_formal_launcher_control_surfaces_safe
mkdir -p $FULL_LAUNCH_LOCK_DIR_ESCAPED
printf '%s\n' "\$\$" > $FULL_LAUNCH_LOCK_PID_ESCAPED
ensure_formal_launcher_control_surfaces_safe
cat > $FULL_LAUNCH_STATUS_ESCAPED <<'STATUS'
status=running
manifest=$MANIFEST_PATH
profile=$PROFILE
output_root=$OUTPUT_PATH
log_path=$FULL_LAUNCH_LOG
matrix_index=$OUTPUT_PATH/$PROFILE/matrix_index.json
STATUS
ensure_formal_launcher_control_surfaces_safe
: > $FULL_LAUNCH_LOG_ESCAPED
set +e
CODEMARKBENCH_FORMAL_FULL_DETACHED=1 bash $SELF_ESCAPED $ORIGINAL_ARGS_ESCAPED >> $FULL_LAUNCH_LOG_ESCAPED 2>&1
EXIT_CODE=\$?
set -e
ensure_formal_launcher_control_surfaces_safe
cat > $FULL_LAUNCH_STATUS_ESCAPED <<STATUS
status=\$( [[ \$EXIT_CODE -eq 0 ]] && echo passed || echo failed )
exit_code=\$EXIT_CODE
manifest=$MANIFEST_PATH
profile=$PROFILE
output_root=$OUTPUT_PATH
log_path=$FULL_LAUNCH_LOG
matrix_index=$OUTPUT_PATH/$PROFILE/matrix_index.json
STATUS
exit \$EXIT_CODE
EOF
  chmod +x "$FULL_LAUNCH_SCRIPT"
  nohup "$FULL_LAUNCH_SCRIPT" >/dev/null 2>&1 &
  LAUNCHER_PID="$!"
  ensure_formal_launcher_control_surfaces_safe
  printf '%s\n' "$LAUNCHER_PID" > "$FULL_LAUNCH_PID"
  echo "Detached formal direct-full launcher started." >&2
  echo "launcher_pid: $LAUNCHER_PID" >&2
  echo "launcher_log: $FULL_LAUNCH_LOG" >&2
  echo "launcher_status: $FULL_LAUNCH_STATUS" >&2
  echo "matrix_index: $OUTPUT_PATH/$PROFILE/matrix_index.json" >&2
  exit 0
fi

PREFLIGHT_ARGS=(
  bash "$ROOT/scripts/remote/run_preflight.sh"
  --python "$PYTHON_BIN"
  --venv "$VENV_DIR"
  --full-manifest "$MANIFEST_PATH"
  --full-profile "$PROFILE"
  --output-root "$OUTPUT_PATH"
  --command-timeout-seconds "$COMMAND_TIMEOUT_SECONDS"
  --formal-full-only
)
if [[ $SKIP_HF_ACCESS -eq 1 ]]; then
  PREFLIGHT_ARGS+=(--skip-hf-access)
fi
"${PREFLIGHT_ARGS[@]}"

"$PYTHON_BIN" "$ROOT/scripts/clean_suite_outputs.py" \
  --include-full-matrix \
  --include-release-bundle \
  --preserve-precheck-artifacts \
  --preserve-launcher-artifacts

FULL_MATRIX_ARGS=(
  "$PYTHON_BIN" "$ROOT/scripts/run_full_matrix.py"
  --manifest "$MANIFEST_PATH"
  --profile "$PROFILE"
  --allow-formal-release-path
  --output-root "$OUTPUT_PATH"
  --gpu-slots "$EFFECTIVE_GPU_SLOTS"
  --gpu-pool-mode "$GPU_POOL_MODE"
  --cpu-workers "$CPU_WORKERS"
  --retry-count "$RETRY_COUNT"
  --command-timeout-seconds "$COMMAND_TIMEOUT_SECONDS"
)
if [[ $FAIL_FAST -eq 1 ]]; then
  FULL_MATRIX_ARGS+=(--fail-fast)
fi
"${FULL_MATRIX_ARGS[@]}"

require_formal_release_completion
echo "Canonical release-suite run complete. Publication-facing status requires the canonical matrix to report 140/140 success."

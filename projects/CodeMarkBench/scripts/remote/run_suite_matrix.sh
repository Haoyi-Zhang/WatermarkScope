#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ORIGINAL_ARGS=("$@")
MANIFEST="configs/matrices/suite_all_models_methods.json"
PROFILE="suite_all_models_methods"
STAGE_A_MANIFEST="configs/matrices/suite_canary_heavy.json"
STAGE_A_PROFILE="suite_canary_heavy"
STAGE_B_MANIFEST="configs/matrices/model_invocation_smoke.json"
STAGE_B_PROFILE="model_invocation_smoke"
OUTPUT_ROOT="$ROOT/results/matrix"
PYTHON_BIN="${PYTHON_BIN:-}"
BOOTSTRAP_PYTHON="${BOOTSTRAP_PYTHON:-python3}"
DEFAULT_REMOTE_VENV="${CODEMARKBENCH_REMOTE_VENV:-}"
VENV_DIR="${VENV_DIR:-}"
export PYTHONDONTWRITEBYTECODE=1
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
FULL_FAIL_FAST=0
DRY_RUN=0
BOOTSTRAP=0
RUN_FULL=0
CLEAN_OUTPUTS=1
RESUME=0
REQUIRE_HF_TOKEN=0
SKIP_HF_ACCESS=0
STAGE_A_MANIFEST_EXPLICIT=0
STAGE_A_PROFILE_EXPLICIT=0
STAGE_B_MANIFEST_EXPLICIT=0
STAGE_B_PROFILE_EXPLICIT=0

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

CANONICAL_MANIFEST_DEFAULT_PATH="$(normalize_abs_path "configs/matrices/suite_all_models_methods.json")"
CANONICAL_STAGE_A_MANIFEST_DEFAULT_PATH="$(normalize_abs_path "configs/matrices/suite_canary_heavy.json")"
CANONICAL_STAGE_B_MANIFEST_DEFAULT_PATH="$(normalize_abs_path "configs/matrices/model_invocation_smoke.json")"

find_active_certification_processes() {
  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi
  pgrep -af "run_preflight.sh|certify_suite_precheck.py|audit_full_matrix.py" | grep "$ROOT" | grep -v " $$" || true
}

find_active_full_matrix_processes() {
  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi
  pgrep -af "run_full_matrix.py" \
    | grep "$ROOT" \
    | grep -F -- "--manifest $MANIFEST_PATH" \
    | grep -F -- "--profile $PROFILE" \
    | grep -F -- "--output-root $OUTPUT_PATH" \
    | grep -v " $$" || true
}

find_active_cleanup_processes() {
  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi
  pgrep -af "clean_suite_outputs.py" | grep "$ROOT" | grep -v " $$" || true
}

find_active_full_matrix_lock_owner() {
  "$PYTHON_BIN" - "$OUTPUT_PATH/$PROFILE/.matrix_runner.lock" "$MANIFEST_PATH" "$PROFILE" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

lock_path = Path(sys.argv[1])
manifest = sys.argv[2]
profile = sys.argv[3]
if not lock_path.exists():
    raise SystemExit(0)
try:
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
if str(payload.get("manifest", "")).strip() != manifest:
    raise SystemExit(0)
if str(payload.get("profile", "")).strip() != profile:
    raise SystemExit(0)
pid = int(payload.get("pid", 0) or 0)
if pid <= 0:
    raise SystemExit(0)
try:
    os.kill(pid, 0)
except OSError:
    raise SystemExit(0)
print(json.dumps(payload, ensure_ascii=False))
PY
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
import sys

tokens = [token.strip() for token in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if token.strip()]
if not tokens:
    raise SystemExit("The formal single-host suite contract requires CUDA_VISIBLE_DEVICES to be set.")
if any(not token.isdigit() for token in tokens):
    raise SystemExit(
        "The formal single-host suite contract requires numeric CUDA_VISIBLE_DEVICES ordinals; "
        f"got {','.join(tokens)}."
    )
try:
    completed = subprocess.run(
        ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader,nounits"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
except Exception as exc:
    raise SystemExit(
        "The formal single-host suite contract requires a detectable GPU inventory from nvidia-smi "
        f"before launch-time validation: {exc}"
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
  if ! validate_visible_device_ordinals; then
    exit 1
  fi
  if [[ "$EFFECTIVE_GPU_SLOTS" != "8" ]]; then
    echo "The formal single-host suite contract requires eight visible GPUs; got CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES." >&2
    exit 1
  fi
}

usage() {
  cat <<'EOF'
Usage: run_suite_matrix.sh [--manifest PATH] [--profile NAME] [--stage-a-manifest PATH] [--stage-a-profile NAME]
                           [--stage-b-manifest PATH] [--stage-b-profile NAME] [--output-root PATH] [--python PATH] [--venv PATH]
                           [--gpu-slots N] [--gpu-pool-mode split|shared] [--cpu-workers N] [--retry-count N]
                           [--command-timeout-seconds N]
                           [--bootstrap] [--run-full] [--full-fail-fast] [--resume]
                           [--require-hf-token] [--skip-hf-access] [--dry-run] [--no-clean]

This wrapper exists for engineering smoke and legacy A/B precheck coverage only; it is not the publication-facing entrypoint.
Use scripts/remote/run_formal_single_host_full.sh for the formal direct-full release path, or scripts/remote/run_matrix_shard.sh when you explicitly want the optional reviewer-safe two-host identical-execution-class reproduction path.
`--gpu-pool-mode shared` is the canonical throughput-oriented path reused by the engineering wrapper: runtime and local-HF pool labels share one GPU queue.
Use `split` only when you explicitly want per-pool GPU separation for engineering/debug runs.
`--resume` is reserved for non-canonical engineering continuations and is rejected on the formal single-host one-shot release path.
EOF
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
gpu_pool_mode = str(payload.get("gpu_pool_mode", "")).strip()
code_snapshot_digest = str(payload.get("code_snapshot_digest", "")).strip().lower()
execution_environment_fingerprint = str(payload.get("execution_environment_fingerprint", "")).strip().lower()
assembly_source_execution_modes = [
    str(item).strip()
    for item in payload.get("assembly_source_execution_modes", [])
    if str(item).strip()
]
def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
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
if gpu_pool_mode != "shared":
    raise SystemExit(
        "formal single-host publication-facing completion requires gpu_pool_mode=shared; "
        f"observed gpu_pool_mode={gpu_pool_mode or '<missing>'}"
    )
if assembly_source_execution_modes and assembly_source_execution_modes != ["single_host_canonical"]:
    raise SystemExit(
        "formal single-host publication-facing completion requires assembly_source_execution_modes=['single_host_canonical']; "
        f"observed {assembly_source_execution_modes}"
    )
if not _is_sha256(code_snapshot_digest):
    raise SystemExit("formal single-host publication-facing completion requires a 64-hex code_snapshot_digest")
if not _is_sha256(execution_environment_fingerprint):
    raise SystemExit("formal single-host publication-facing completion requires a 64-hex execution_environment_fingerprint")
PY
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
    --stage-a-manifest)
      STAGE_A_MANIFEST="$2"
      STAGE_A_MANIFEST_EXPLICIT=1
      shift 2
      ;;
    --stage-a-profile)
      STAGE_A_PROFILE="$2"
      STAGE_A_PROFILE_EXPLICIT=1
      shift 2
      ;;
    --stage-b-manifest)
      STAGE_B_MANIFEST="$2"
      STAGE_B_MANIFEST_EXPLICIT=1
      shift 2
      ;;
    --stage-b-profile)
      STAGE_B_PROFILE="$2"
      STAGE_B_PROFILE_EXPLICIT=1
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
    --bootstrap)
      BOOTSTRAP=1
      shift
      ;;
    --run-full)
      RUN_FULL=1
      shift
      ;;
    --full-fail-fast)
      FULL_FAIL_FAST=1
      shift
      ;;
    --resume)
      RESUME=1
      shift
      ;;
    --require-hf-token)
      REQUIRE_HF_TOKEN=1
      shift
      ;;
    --skip-hf-access)
      SKIP_HF_ACCESS=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-clean)
      CLEAN_OUTPUTS=0
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

MANIFEST_PATH="$MANIFEST"
MANIFEST_PATH="$(normalize_abs_path "$MANIFEST_PATH")"

STAGE_A_MANIFEST_PATH="$STAGE_A_MANIFEST"
STAGE_A_MANIFEST_PATH="$(normalize_abs_path "$STAGE_A_MANIFEST_PATH")"

STAGE_B_MANIFEST_PATH="$STAGE_B_MANIFEST"
STAGE_B_MANIFEST_PATH="$(normalize_abs_path "$STAGE_B_MANIFEST_PATH")"

OUTPUT_PATH="$OUTPUT_ROOT"
OUTPUT_PATH="$(normalize_abs_path "$OUTPUT_PATH")"

CANONICAL_SUITE_PROFILE=0
if [[ "$MANIFEST_PATH" == "$CANONICAL_MANIFEST_DEFAULT_PATH" && "$PROFILE" == "suite_all_models_methods" ]]; then
  CANONICAL_SUITE_PROFILE=1
  if [[ "$STAGE_A_MANIFEST_PATH" != "$CANONICAL_STAGE_A_MANIFEST_DEFAULT_PATH" || "$STAGE_A_PROFILE" != "suite_canary_heavy" || "$STAGE_B_MANIFEST_PATH" != "$CANONICAL_STAGE_B_MANIFEST_DEFAULT_PATH" || "$STAGE_B_PROFILE" != "model_invocation_smoke" ]]; then
    echo "Canonical --manifest/--profile requires the canonical stage A/B manifests and profiles so precheck certifies one canonical manifest set." >&2
    exit 1
  fi
else
  if [[ $STAGE_A_MANIFEST_EXPLICIT -ne 1 || $STAGE_A_PROFILE_EXPLICIT -ne 1 || $STAGE_B_MANIFEST_EXPLICIT -ne 1 || $STAGE_B_PROFILE_EXPLICIT -ne 1 ]]; then
    echo "Custom --manifest/--profile requires explicit --stage-a-manifest/--stage-a-profile/--stage-b-manifest/--stage-b-profile so precheck certifies the same roster." >&2
    exit 1
  fi
fi

if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$VENV_DIR/bin/python"
fi

CANONICAL_FORMAL_FULL=0
if [[ $RUN_FULL -eq 1 && $CANONICAL_SUITE_PROFILE -eq 1 ]]; then
  CANONICAL_FORMAL_FULL=1
fi

if [[ $CANONICAL_FORMAL_FULL -eq 1 ]]; then
  echo "run_suite_matrix.sh no longer owns the canonical publication-facing full launch." >&2
  echo "Use scripts/remote/run_formal_single_host_full.sh for the A/B-free standalone-preflight direct-full contract." >&2
  exit 1
fi

if [[ $DRY_RUN -eq 1 ]]; then
  STEP_BLOCK='    "build_suite_manifests",
    "suite_preflight",
    "suite_precheck"'
  if [[ $RUN_FULL -eq 1 ]]; then
    STEP_BLOCK="$STEP_BLOCK,
    \"run_full_matrix\""
  fi
  cat <<EOF
{
  "root": "$ROOT",
  "manifest": "$MANIFEST",
  "profile": "$PROFILE",
  "stage_a_manifest": "$STAGE_A_MANIFEST",
  "stage_a_profile": "$STAGE_A_PROFILE",
  "stage_b_manifest": "$STAGE_B_MANIFEST",
  "stage_b_profile": "$STAGE_B_PROFILE",
  "output_root": "$OUTPUT_PATH",
  "venv": "$VENV_DIR",
  "python": "$PYTHON_BIN",
  "command_timeout_seconds": "$COMMAND_TIMEOUT_SECONDS",
  "bootstrap": $BOOTSTRAP,
  "run_full": $RUN_FULL,
  "full_fail_fast": $FULL_FAIL_FAST,
  "resume": $RESUME,
  "clean_outputs": $CLEAN_OUTPUTS,
  "require_hf_token": $REQUIRE_HF_TOKEN,
  "skip_hf_access": $SKIP_HF_ACCESS,
  "steps": [
$STEP_BLOCK
  ]
}
EOF
  exit 0
fi

if [[ $BOOTSTRAP -eq 1 ]]; then
  bash "$ROOT/scripts/remote/bootstrap_linux_gpu.sh" --install --python "$BOOTSTRAP_PYTHON" --venv "$VENV_DIR"
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing Python interpreter: $PYTHON_BIN" >&2
  echo "Create the venv first with: bash $ROOT/scripts/remote/bootstrap_linux_gpu.sh --install --venv $VENV_DIR" >&2
  exit 1
fi

EFFECTIVE_GPU_SLOTS="$(effective_gpu_slots)"
if [[ -n "${CUDA_VISIBLE_DEVICES:-}" && "$EFFECTIVE_GPU_SLOTS" != "$GPU_SLOTS" ]]; then
  echo "Adjusting gpu-slots from $GPU_SLOTS to $EFFECTIVE_GPU_SLOTS to match CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES." >&2
fi

ACTIVE_CERTIFICATION="$(find_active_certification_processes)"
if [[ -n "$ACTIVE_CERTIFICATION" ]]; then
  echo "Detected active certification processes for $ROOT; wait for them to finish before starting another preflight/precheck stack." >&2
  echo "$ACTIVE_CERTIFICATION" >&2
  exit 1
fi

ACTIVE_CLEANUP="$(find_active_cleanup_processes)"
if [[ -n "$ACTIVE_CLEANUP" ]]; then
  echo "Detected active cleanup process for $ROOT; wait for it to finish before starting preflight or another launch." >&2
  echo "$ACTIVE_CLEANUP" >&2
  exit 1
fi

ACTIVE_FULL_LOCK_OWNER=""
ACTIVE_FULL_PROCESS=""
ACTIVE_FULL_LOCK_OWNER="$(find_active_full_matrix_lock_owner)"
ACTIVE_FULL_PROCESS="$(find_active_full_matrix_processes)"
if [[ -n "$ACTIVE_FULL_LOCK_OWNER" || -n "$ACTIVE_FULL_PROCESS" ]]; then
  if [[ $RUN_FULL -eq 1 ]]; then
    echo "Detected active full-matrix run for $ROOT; refusing to clean outputs or start another full launch." >&2
  else
    echo "Detected active full-matrix run for $ROOT; refusing to start a preflight-only wrapper that would rewrite shared launch artifacts." >&2
  fi
  if [[ -n "$ACTIVE_FULL_LOCK_OWNER" ]]; then
    echo "$ACTIVE_FULL_LOCK_OWNER" >&2
  fi
  if [[ -n "$ACTIVE_FULL_PROCESS" ]]; then
    echo "$ACTIVE_FULL_PROCESS" >&2
  fi
  exit 1
fi

if [[ $RUN_FULL -eq 1 && -z "${CODEMARKBENCH_SUITE_LAUNCHER_DETACHED:-}" ]]; then
  FULL_RUN_DIR="$OUTPUT_PATH/$PROFILE"
  CERTIFICATION_RUN_DIR="$ROOT/results/certifications/$PROFILE"
  LAUNCHER_RUN_DIR="$ROOT/results/launchers/$PROFILE"
  FULL_LAUNCH_LOCK_DIR="$LAUNCHER_RUN_DIR/full_run.launch.lock"
  mkdir -p "$FULL_RUN_DIR" "$CERTIFICATION_RUN_DIR" "$LAUNCHER_RUN_DIR"
  if [[ -d "$FULL_LAUNCH_LOCK_DIR" ]]; then
    EXISTING_LAUNCH_PID=""
    if [[ -f "$FULL_LAUNCH_LOCK_DIR/pid" ]]; then
      EXISTING_LAUNCH_PID="$(tr -d '[:space:]' < "$FULL_LAUNCH_LOCK_DIR/pid" || true)"
    fi
    if [[ -n "$EXISTING_LAUNCH_PID" ]] && kill -0 "$EXISTING_LAUNCH_PID" 2>/dev/null; then
      echo "Detected active detached launcher control surface for $PROFILE; refusing to start another launch." >&2
      echo "launcher_pid=$EXISTING_LAUNCH_PID" >&2
      exit 1
    fi
    rm -rf "$FULL_LAUNCH_LOCK_DIR"
  fi
  if ! mkdir "$FULL_LAUNCH_LOCK_DIR" 2>/dev/null; then
    echo "Unable to acquire detached launcher lock under $FULL_LAUNCH_LOCK_DIR." >&2
    exit 1
  fi
  printf '%s\n' "$$" > "$FULL_LAUNCH_LOCK_DIR/requester_pid"
  FULL_LAUNCH_LOG="$LAUNCHER_RUN_DIR/full_run.launch.log"
  FULL_LAUNCH_STATUS="$LAUNCHER_RUN_DIR/full_run.launch.status"
  FULL_LAUNCH_PID="$LAUNCHER_RUN_DIR/full_run.launch.pid"
  FULL_LAUNCH_SCRIPT="$LAUNCHER_RUN_DIR/full_run.launch.sh"
  RUN_SUITE_SCRIPT="$ROOT/scripts/remote/run_suite_matrix.sh"
  ORIGINAL_ARGS_ESCAPED="$(printf '%q ' "${ORIGINAL_ARGS[@]}")"
  ROOT_ESCAPED="$(printf '%q' "$ROOT")"
  RUN_SUITE_SCRIPT_ESCAPED="$(printf '%q' "$RUN_SUITE_SCRIPT")"
  FULL_LAUNCH_LOG_ESCAPED="$(printf '%q' "$FULL_LAUNCH_LOG")"
  FULL_LAUNCH_STATUS_ESCAPED="$(printf '%q' "$FULL_LAUNCH_STATUS")"
  FULL_LAUNCH_PID_ESCAPED="$(printf '%q' "$FULL_LAUNCH_PID")"
  FULL_LAUNCH_LOCK_DIR_ESCAPED="$(printf '%q' "$FULL_LAUNCH_LOCK_DIR")"
  FULL_RUN_DIR_ESCAPED="$(printf '%q' "$FULL_RUN_DIR")"
  CERTIFICATION_RUN_DIR_ESCAPED="$(printf '%q' "$CERTIFICATION_RUN_DIR")"
  LAUNCHER_RUN_DIR_ESCAPED="$(printf '%q' "$LAUNCHER_RUN_DIR")"
  MANIFEST_PATH_ESCAPED="$(printf '%q' "$MANIFEST_PATH")"
  PROFILE_ESCAPED="$(printf '%q' "$PROFILE")"
  OUTPUT_PATH_ESCAPED="$(printf '%q' "$OUTPUT_PATH")"
  cat > "$FULL_LAUNCH_SCRIPT" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cleanup_detached_launcher_lock() {
  if [[ -d $FULL_LAUNCH_LOCK_DIR_ESCAPED ]]; then
    local lock_pid=""
    if [[ -f $FULL_LAUNCH_LOCK_DIR_ESCAPED/pid ]]; then
      lock_pid="\$(tr -d '[:space:]' < $FULL_LAUNCH_LOCK_DIR_ESCAPED/pid || true)"
    fi
    if [[ -n "\$lock_pid" && "\$lock_pid" == "\$\$" ]]; then
      rm -rf $FULL_LAUNCH_LOCK_DIR_ESCAPED
    fi
  fi
}
trap cleanup_detached_launcher_lock EXIT
mkdir -p $FULL_RUN_DIR_ESCAPED
mkdir -p $CERTIFICATION_RUN_DIR_ESCAPED
mkdir -p $LAUNCHER_RUN_DIR_ESCAPED
mkdir -p $FULL_LAUNCH_LOCK_DIR_ESCAPED
printf '%s\n' "\$\$" > $FULL_LAUNCH_LOCK_DIR_ESCAPED/pid
cat > $FULL_LAUNCH_STATUS_ESCAPED <<'STATUS'
status=running
manifest=$MANIFEST_PATH
profile=$PROFILE
output_root=$OUTPUT_PATH
log_path=$FULL_LAUNCH_LOG
matrix_index=$OUTPUT_PATH/$PROFILE/matrix_index.json
STATUS
: > $FULL_LAUNCH_LOG_ESCAPED
set +e
CODEMARKBENCH_SUITE_LAUNCHER_DETACHED=1 bash $RUN_SUITE_SCRIPT_ESCAPED $ORIGINAL_ARGS_ESCAPED >> $FULL_LAUNCH_LOG_ESCAPED 2>&1
EXIT_CODE=\$?
set -e
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
  printf '%s\n' "$LAUNCHER_PID" > "$FULL_LAUNCH_PID"
  echo "Detached engineering suite launcher started." >&2
  echo "launcher_pid: $LAUNCHER_PID" >&2
  echo "launcher_log: $FULL_LAUNCH_LOG" >&2
  echo "launcher_status: $FULL_LAUNCH_STATUS" >&2
  echo "matrix_index: $OUTPUT_PATH/$PROFILE/matrix_index.json" >&2
  exit 0
fi

PREFLIGHT_ARGS=(
  bash "$ROOT/scripts/remote/run_preflight.sh"
  --python "$PYTHON_BIN" \
  --venv "$VENV_DIR" \
  --full-manifest "$MANIFEST_PATH" \
  --full-profile "$PROFILE" \
  --stage-a-manifest "$STAGE_A_MANIFEST_PATH" \
  --stage-a-profile "$STAGE_A_PROFILE" \
  --stage-b-manifest "$STAGE_B_MANIFEST_PATH" \
  --stage-b-profile "$STAGE_B_PROFILE" \
  --output-root "$OUTPUT_PATH" \
  --command-timeout-seconds "$COMMAND_TIMEOUT_SECONDS"
)
if [[ $REQUIRE_HF_TOKEN -eq 1 ]]; then
  PREFLIGHT_ARGS+=(--require-hf-token)
fi
if [[ $SKIP_HF_ACCESS -eq 1 ]]; then
  PREFLIGHT_ARGS+=(--skip-hf-access)
fi
"${PREFLIGHT_ARGS[@]}"

CERTIFY_ARGS=(
  "$PYTHON_BIN" "$ROOT/scripts/certify_suite_precheck.py"
  --python-bin "$PYTHON_BIN" \
  --full-manifest "$MANIFEST_PATH" \
  --full-profile "$PROFILE" \
  --stage-a-manifest "$STAGE_A_MANIFEST_PATH" \
  --stage-a-profile "$STAGE_A_PROFILE" \
  --stage-b-manifest "$STAGE_B_MANIFEST_PATH" \
  --stage-b-profile "$STAGE_B_PROFILE" \
  --output-root "$OUTPUT_PATH" \
  --gpu-slots "$EFFECTIVE_GPU_SLOTS" \
  --gpu-pool-mode "$GPU_POOL_MODE" \
  --cpu-workers "$CPU_WORKERS" \
  --retry-count "$RETRY_COUNT" \
  --command-timeout-seconds "$COMMAND_TIMEOUT_SECONDS" \
  --step-timeout-seconds "$COMMAND_TIMEOUT_SECONDS"
)
if [[ $SKIP_HF_ACCESS -eq 1 ]]; then
  CERTIFY_ARGS+=(--skip-hf-access)
fi
if [[ $RESUME -eq 1 ]]; then
  echo "Full-run resume requested: precheck stages will rerun cleanly; --resume is reserved for the final full matrix launch." >&2
fi
"${CERTIFY_ARGS[@]}"

LAUNCH_VALIDATE_ARGS=(
  "$PYTHON_BIN" "$ROOT/scripts/validate_single_host_launch_receipt.py"
  --python-bin "$PYTHON_BIN" \
  --full-manifest "$MANIFEST_PATH" \
  --full-profile "$PROFILE" \
  --stage-a-manifest "$STAGE_A_MANIFEST_PATH" \
  --stage-a-profile "$STAGE_A_PROFILE" \
  --stage-b-manifest "$STAGE_B_MANIFEST_PATH" \
  --stage-b-profile "$STAGE_B_PROFILE" \
  --output-root "$OUTPUT_PATH"
)
if [[ $SKIP_HF_ACCESS -eq 1 ]]; then
  LAUNCH_VALIDATE_ARGS+=(--skip-hf-access)
fi
"${LAUNCH_VALIDATE_ARGS[@]}"

if [[ $RUN_FULL -ne 1 ]]; then
  echo "Suite precheck complete. This wrapper remains engineering smoke only; use scripts/remote/run_formal_single_host_full.sh for the formal release rerun." >&2
  exit 0
fi

if [[ $CLEAN_OUTPUTS -eq 1 && $RESUME -eq 0 ]]; then
  "$PYTHON_BIN" "$ROOT/scripts/clean_suite_outputs.py" --include-full-matrix --include-release-bundle --preserve-precheck-artifacts --preserve-launcher-artifacts
fi

FULL_MATRIX_ARGS=(
  "$PYTHON_BIN" "$ROOT/scripts/run_full_matrix.py"
  --manifest "$MANIFEST_PATH"
  --profile "$PROFILE"
  --output-root "$OUTPUT_PATH"
  --gpu-slots "$EFFECTIVE_GPU_SLOTS"
  --gpu-pool-mode "$GPU_POOL_MODE"
  --cpu-workers "$CPU_WORKERS"
  --retry-count "$RETRY_COUNT"
  --command-timeout-seconds "$COMMAND_TIMEOUT_SECONDS"
)

if [[ $FULL_FAIL_FAST -eq 1 ]]; then
  FULL_MATRIX_ARGS+=(--fail-fast)
fi
if [[ $RESUME -eq 1 ]]; then
  FULL_MATRIX_ARGS+=(--resume)
fi

"${FULL_MATRIX_ARGS[@]}"

echo "Engineering wrapper full run complete. Publication-facing reruns must use scripts/remote/run_formal_single_host_full.sh."

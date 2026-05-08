#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FULL_MANIFEST="configs/matrices/suite_all_models_methods.json"
FULL_PROFILE="suite_all_models_methods"
STAGE_A_MANIFEST="configs/matrices/suite_canary_heavy.json"
STAGE_A_PROFILE="suite_canary_heavy"
STAGE_B_MANIFEST="configs/matrices/model_invocation_smoke.json"
STAGE_B_PROFILE="model_invocation_smoke"
OUTPUT_ROOT="$ROOT/results/matrix"
ENVIRONMENT_JSON="$ROOT/results/environment/runtime_environment.json"
ENVIRONMENT_MD="$ROOT/results/environment/runtime_environment.md"
PREFLIGHT_RECEIPT="$ROOT/results/certifications/remote_preflight_receipt.json"
PRECHECK_IDLE_GPU_MAX_MEMORY_MB="${PRECHECK_IDLE_GPU_MAX_MEMORY_MB:-512}"
COMMAND_TIMEOUT_SECONDS="${COMMAND_TIMEOUT_SECONDS:-259200}"
export PRECHECK_IDLE_GPU_MAX_MEMORY_MB
DEFAULT_REMOTE_VENV="${CODEMARKBENCH_REMOTE_VENV:-}"
VENV_DIR="${VENV_DIR:-}"
if [[ -z "$VENV_DIR" ]]; then
  if [[ -n "$DEFAULT_REMOTE_VENV" && -d "$DEFAULT_REMOTE_VENV" ]]; then
    VENV_DIR="$DEFAULT_REMOTE_VENV"
  else
    VENV_DIR="$ROOT/.venv/tosem_release"
  fi
fi
PYTHON_BIN="${PYTHON_BIN:-}"
DRY_RUN=0
REQUIRE_HF_TOKEN=0
SKIP_HF_ACCESS=0
FORMAL_FULL_ONLY=0
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

usage() {
  cat <<'EOF'
Usage: run_preflight.sh [--full-manifest PATH] [--full-profile NAME] [--stage-a-manifest PATH] [--stage-a-profile NAME]
                        [--stage-b-manifest PATH] [--stage-b-profile NAME] [--output-root PATH]
                        [--environment-json PATH] [--environment-md PATH]
                        [--preflight-receipt PATH]
                        [--command-timeout-seconds N]
                        [--venv PATH] [--python PATH] [--dry-run] [--require-hf-token] [--skip-hf-access]
                        [--formal-full-only]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full-manifest)
      FULL_MANIFEST="$2"
      shift 2
      ;;
    --full-profile)
      FULL_PROFILE="$2"
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
    --environment-json)
      ENVIRONMENT_JSON="$2"
      shift 2
      ;;
    --environment-md)
      ENVIRONMENT_MD="$2"
      shift 2
      ;;
    --preflight-receipt)
      PREFLIGHT_RECEIPT="$2"
      shift 2
      ;;
    --command-timeout-seconds)
      COMMAND_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --venv)
      VENV_DIR="$2"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
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
    --formal-full-only)
      FORMAL_FULL_ONLY=1
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

FULL_MANIFEST_PATH="$(normalize_abs_path "$FULL_MANIFEST")"
STAGE_A_MANIFEST_PATH="$(normalize_abs_path "$STAGE_A_MANIFEST")"
STAGE_B_MANIFEST_PATH="$(normalize_abs_path "$STAGE_B_MANIFEST")"
OUTPUT_PATH="$(normalize_abs_path "$OUTPUT_ROOT")"

ENVIRONMENT_JSON_PATH="$ENVIRONMENT_JSON"
if [[ "$ENVIRONMENT_JSON_PATH" != /* ]]; then
  ENVIRONMENT_JSON_PATH="$ROOT/$ENVIRONMENT_JSON_PATH"
fi

ENVIRONMENT_MD_PATH="$ENVIRONMENT_MD"
if [[ "$ENVIRONMENT_MD_PATH" != /* ]]; then
  ENVIRONMENT_MD_PATH="$ROOT/$ENVIRONMENT_MD_PATH"
fi

PREFLIGHT_RECEIPT_PATH="$PREFLIGHT_RECEIPT"
if [[ "$PREFLIGHT_RECEIPT_PATH" != /* ]]; then
  PREFLIGHT_RECEIPT_PATH="$ROOT/$PREFLIGHT_RECEIPT_PATH"
fi
ENVIRONMENT_JSON_PATH="$(validate_results_control_path "$ENVIRONMENT_JSON_PATH" "remote preflight environment json")"
ENVIRONMENT_MD_PATH="$(validate_results_control_path "$ENVIRONMENT_MD_PATH" "remote preflight environment markdown")"
PREFLIGHT_RECEIPT_PATH="$(validate_results_control_path "$PREFLIGHT_RECEIPT_PATH" "remote preflight receipt")"
OUTPUT_PATH="$(validate_results_control_path "$OUTPUT_PATH" "remote preflight output root")"
CANONICAL_REPO_OUTPUT_PATH="$(validate_results_control_path "$ROOT/results/matrix" "remote preflight canonical output root")"
if [[ $FORMAL_FULL_ONLY -eq 1 ]]; then
  if [[ "$OUTPUT_PATH" != "$CANONICAL_REPO_OUTPUT_PATH" ]]; then
    echo "Canonical --formal-full-only preflight requires repo-local output root results/matrix." >&2
    exit 1
  fi
fi

CANONICAL_FULL_MANIFEST_PATH="$(normalize_abs_path "configs/matrices/suite_all_models_methods.json")"
CANONICAL_STAGE_A_MANIFEST_PATH="$(normalize_abs_path "configs/matrices/suite_canary_heavy.json")"
CANONICAL_STAGE_B_MANIFEST_PATH="$(normalize_abs_path "configs/matrices/model_invocation_smoke.json")"
FULL_MANIFEST_IS_CANONICAL=0
if [[ "$FULL_MANIFEST_PATH" == "$CANONICAL_FULL_MANIFEST_PATH" && "$FULL_PROFILE" == "suite_all_models_methods" ]]; then
  FULL_MANIFEST_IS_CANONICAL=1
fi
PREFLIGHT_LOCK_DIR="$ROOT/results/launchers/.remote_preflight.lock"
PREFLIGHT_LOCK_PID_PATH="$PREFLIGHT_LOCK_DIR/pid"
PREFLIGHT_LOCK_ROOT_PATH="$PREFLIGHT_LOCK_DIR/root"
PREFLIGHT_LOCK_DIR="$(validate_results_control_path "$PREFLIGHT_LOCK_DIR" "remote preflight lock directory")"
PREFLIGHT_LOCK_PID_PATH="$(validate_results_control_path "$PREFLIGHT_LOCK_PID_PATH" "remote preflight lock pid file")"
PREFLIGHT_LOCK_ROOT_PATH="$(validate_results_control_path "$PREFLIGHT_LOCK_ROOT_PATH" "remote preflight lock root file")"

JAVA_SMOKE_DIR=""
GO_SMOKE_DIR=""

ensure_preflight_control_surfaces_safe() {
  validate_results_control_path "$PREFLIGHT_LOCK_DIR" "remote preflight lock directory" >/dev/null
  validate_results_control_path "$PREFLIGHT_LOCK_PID_PATH" "remote preflight lock pid file" >/dev/null
  validate_results_control_path "$PREFLIGHT_LOCK_ROOT_PATH" "remote preflight lock root file" >/dev/null
  validate_results_control_path "$ENVIRONMENT_JSON_PATH" "remote preflight environment json" >/dev/null
  validate_results_control_path "$ENVIRONMENT_MD_PATH" "remote preflight environment markdown" >/dev/null
  validate_results_control_path "$PREFLIGHT_RECEIPT_PATH" "remote preflight receipt" >/dev/null
}
ensure_preflight_control_surfaces_safe

validate_matrix_output_surface() {
  local profile="$1"
  validate_results_control_path "$OUTPUT_PATH/$profile" "remote preflight matrix output directory for $profile" >/dev/null
  validate_results_control_path "$OUTPUT_PATH/$profile/matrix_index.dry_run.json" "remote preflight dry-run matrix index for $profile" >/dev/null
}

cleanup_preflight() {
  if [[ -n "${JAVA_SMOKE_DIR:-}" ]]; then
    rm -rf "$JAVA_SMOKE_DIR"
  fi
  if [[ -n "${GO_SMOKE_DIR:-}" ]]; then
    rm -rf "$GO_SMOKE_DIR"
  fi
  if [[ -n "${PREFLIGHT_LOCK_DIR:-}" && -d "$PREFLIGHT_LOCK_DIR" ]]; then
    if ! ensure_preflight_control_surfaces_safe; then
      echo "Skipping remote preflight lock cleanup because reviewer-facing control surfaces are not safe." >&2
      return
    fi
    local lock_pid=""
    if [[ -f "$PREFLIGHT_LOCK_PID_PATH" ]]; then
      lock_pid="$(tr -d '[:space:]' < "$PREFLIGHT_LOCK_PID_PATH" || true)"
    fi
    if [[ -n "$lock_pid" && "$lock_pid" == "$$" ]]; then
      rm -rf "$PREFLIGHT_LOCK_DIR"
    fi
  fi
}

write_preflight_lock_metadata() {
  ensure_preflight_control_surfaces_safe
  printf '%s\n' "$$" > "$PREFLIGHT_LOCK_PID_PATH"
  printf '%s\n' "$ROOT" > "$PREFLIGHT_LOCK_ROOT_PATH"
}

acquire_preflight_lock() {
  ensure_preflight_control_surfaces_safe
  mkdir -p "$(dirname "$PREFLIGHT_LOCK_DIR")"
  local existing_pid=""
  local lock_probe_attempts=0
  while true; do
    ensure_preflight_control_surfaces_safe
    if mkdir "$PREFLIGHT_LOCK_DIR" 2>/dev/null; then
      write_preflight_lock_metadata
      return 0
    fi
    existing_pid=""
    if [[ -f "$PREFLIGHT_LOCK_PID_PATH" ]]; then
      existing_pid="$(tr -d '[:space:]' < "$PREFLIGHT_LOCK_PID_PATH" || true)"
    fi
    if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
      echo "Another remote preflight is already active for this repository root (pid=$existing_pid)." >&2
      exit 1
    fi
    if [[ -z "$existing_pid" && $lock_probe_attempts -lt 3 ]]; then
      lock_probe_attempts=$((lock_probe_attempts + 1))
      sleep 1
      continue
    fi
    ensure_preflight_control_surfaces_safe
    rm -rf "$PREFLIGHT_LOCK_DIR"
    ensure_preflight_control_surfaces_safe
    if ! mkdir "$PREFLIGHT_LOCK_DIR" 2>/dev/null; then
      echo "Unable to acquire the remote preflight lock under $PREFLIGHT_LOCK_DIR." >&2
      exit 1
    fi
    write_preflight_lock_metadata
    return 0
  done
}

find_active_repo_blockers() {
  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi
  pgrep -af "run_full_matrix.py|certify_suite_precheck.py|clean_suite_outputs.py" | grep -F "$ROOT" | grep -v " $$" || true
}

trap cleanup_preflight EXIT

if [[ $FORMAL_FULL_ONLY -eq 0 && $FULL_MANIFEST_IS_CANONICAL -eq 1 ]]; then
  if [[ "$STAGE_A_MANIFEST_PATH" != "$CANONICAL_STAGE_A_MANIFEST_PATH" || "$STAGE_A_PROFILE" != "suite_canary_heavy" || "$STAGE_B_MANIFEST_PATH" != "$CANONICAL_STAGE_B_MANIFEST_PATH" || "$STAGE_B_PROFILE" != "model_invocation_smoke" ]]; then
    echo "Canonical --full-manifest/--full-profile requires the canonical stage A/B manifests and profiles so preflight certifies one canonical manifest set." >&2
    exit 1
  fi
elif [[ $FORMAL_FULL_ONLY -eq 0 ]]; then
  if [[ $STAGE_A_MANIFEST_EXPLICIT -ne 1 || $STAGE_A_PROFILE_EXPLICIT -ne 1 || $STAGE_B_MANIFEST_EXPLICIT -ne 1 || $STAGE_B_PROFILE_EXPLICIT -ne 1 ]]; then
    echo "Custom --full-manifest/--full-profile requires explicit --stage-a-manifest/--stage-a-profile/--stage-b-manifest/--stage-b-profile so preflight certifies the same roster." >&2
    exit 1
  fi
fi

if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$VENV_DIR/bin/python"
fi

if [[ $DRY_RUN -eq 1 ]]; then
  STAGE_FIELDS=""
  if [[ $FORMAL_FULL_ONLY -eq 0 ]]; then
    STAGE_FIELDS=$(cat <<EOF
  "stage_a_manifest": "$STAGE_A_MANIFEST",
  "stage_a_profile": "$STAGE_A_PROFILE",
  "stage_b_manifest": "$STAGE_B_MANIFEST",
  "stage_b_profile": "$STAGE_B_PROFILE",
EOF
)
  fi
  cat <<EOF
{
  "root": "$ROOT",
  "full_manifest": "$FULL_MANIFEST",
  "full_profile": "$FULL_PROFILE",
$STAGE_FIELDS
  "output_root": "$OUTPUT_PATH",
  "environment_json": "$ENVIRONMENT_JSON_PATH",
  "environment_md": "$ENVIRONMENT_MD_PATH",
  "preflight_receipt": "$PREFLIGHT_RECEIPT_PATH",
  "venv": "$VENV_DIR",
  "python": "$PYTHON_BIN",
  "command_timeout_seconds": "$COMMAND_TIMEOUT_SECONDS",
  "require_hf_token": $REQUIRE_HF_TOKEN,
  "skip_hf_access": $SKIP_HF_ACCESS,
  "formal_full_only": $FORMAL_FULL_ONLY,
  "precheck_idle_gpu_max_memory_mb": "$PRECHECK_IDLE_GPU_MAX_MEMORY_MB",
  "checks": [
    "zero_legacy_name",
    "build_suite_manifests",
    "audit_benchmarks",
    "audit_suite_matrix",
    "python_version",
    "toolchain",
    "cuda",
    "disk"$( [[ $FORMAL_FULL_ONLY -eq 1 ]] && printf ',\n    "canonical_full_dry_run"' || printf ',\n    "stage_a_dry_run",\n    "stage_b_dry_run"' )
  ]
}
EOF
  exit 0
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing Python interpreter: $PYTHON_BIN" >&2
  echo "Create the venv first with: bash $ROOT/scripts/remote/bootstrap_linux_gpu.sh --install --venv $VENV_DIR" >&2
  exit 1
fi

if [[ $REQUIRE_HF_TOKEN -eq 1 && -z "${HF_ACCESS_TOKEN:-}" && -z "${HF_ACCESS_TOKEN_FALLBACK:-}" ]]; then
  echo "HF_ACCESS_TOKEN or HF_ACCESS_TOKEN_FALLBACK is required for this preflight." >&2
  exit 1
fi

acquire_preflight_lock
ACTIVE_REPO_BLOCKERS="$(find_active_repo_blockers)"
if [[ -n "$ACTIVE_REPO_BLOCKERS" ]]; then
  echo "Detected active suite or cleanup processes for $ROOT; refusing to rewrite shared preflight artifacts." >&2
  echo "$ACTIVE_REPO_BLOCKERS" >&2
  exit 1
fi
ensure_preflight_control_surfaces_safe
rm -f "$PREFLIGHT_RECEIPT_PATH"

"$PYTHON_BIN" "$ROOT/scripts/check_zero_legacy_name.py" --root "$ROOT"

runtime_checkouts_ready() {
  "$PYTHON_BIN" - "$ROOT" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from codemarkbench.baselines.stone_family.common import validate_checkout

methods = ("stone_runtime", "sweet_runtime", "ewd_runtime", "kgw_runtime")
raise SystemExit(0 if all(not validate_checkout(method) for method in methods) else 1)
PY
}

validate_stage_roster_alignment() {
  "$PYTHON_BIN" - "$ROOT" "$FULL_MANIFEST_PATH" "$FULL_PROFILE" "$STAGE_A_MANIFEST_PATH" "$STAGE_A_PROFILE" "$STAGE_B_MANIFEST_PATH" "$STAGE_B_PROFILE" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from scripts import certify_suite_precheck

full_manifest = Path(sys.argv[2]).resolve()
full_profile = sys.argv[3]
stage_pairs = (
    (Path(sys.argv[4]).resolve(), sys.argv[5]),
    (Path(sys.argv[6]).resolve(), sys.argv[7]),
)
for stage_manifest, stage_profile in stage_pairs:
    certify_suite_precheck.validate_stage_manifest_against_full(
        full_manifest_path=full_manifest,
        full_profile=full_profile,
        stage_manifest_path=stage_manifest,
        stage_profile=stage_profile,
    )
PY
}

pick_idle_gpu() {
  nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader,nounits | \
    awk -F',' '
      BEGIN {
        best_idx = "";
        best_mem = -1;
        max_mem = ENVIRON["PRECHECK_IDLE_GPU_MAX_MEMORY_MB"] + 0;
      }
      {
        gsub(/ /, "", $1); gsub(/ /, "", $2); gsub(/ /, "", $3);
        if (($2 + 0) == 0 && ($3 + 0) <= max_mem) {
          if (best_idx == "" || ($3 + 0) < best_mem) {
            best_idx = $1;
            best_mem = ($3 + 0);
          }
        }
      }
      END {
        if (best_idx != "") {
          print best_idx;
        }
      }
    '
}

visible_gpu_slot_count() {
  "$PYTHON_BIN" - <<'PY'
import os

tokens = [token.strip() for token in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if token.strip()]
print(max(1, len(tokens)))
PY
}

if [[ $FULL_MANIFEST_IS_CANONICAL -eq 1 ]]; then
  "$PYTHON_BIN" "$ROOT/scripts/build_suite_manifests.py"
fi
if [[ $FORMAL_FULL_ONLY -eq 0 ]]; then
  validate_stage_roster_alignment
fi
if runtime_checkouts_ready; then
  echo "Pinned runtime upstream checkouts already validate cleanly; skipping network refresh."
else
  echo "Pinned runtime upstream checkouts are missing or invalid." >&2
  echo "Run bash $ROOT/scripts/fetch_runtime_upstreams.sh all explicitly before preflight." >&2
  exit 1
fi
"$PYTHON_BIN" "$ROOT/scripts/audit_benchmarks.py" --manifest "$FULL_MANIFEST_PATH" --matrix-profile "$FULL_PROFILE" --profile "$FULL_PROFILE"

"$PYTHON_BIN" -V
command -v g++ >/dev/null 2>&1 || { echo "Missing g++" >&2; exit 1; }
command -v javac >/dev/null 2>&1 || { echo "Missing javac" >&2; exit 1; }
command -v java >/dev/null 2>&1 || { echo "Missing java" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Missing node" >&2; exit 1; }
command -v go >/dev/null 2>&1 || { echo "Missing go" >&2; exit 1; }
command -v nvidia-smi >/dev/null 2>&1 || { echo "Missing nvidia-smi" >&2; exit 1; }
g++ --version | head -n 1
javac -version
java -version
node --version
go version
nvidia-smi >/dev/null
node -e "const add = (a, b) => a + b; if (add(1, 2) !== 3) { process.exit(1); } console.log('node smoke ok');"
JAVA_SMOKE_DIR="$(mktemp -d)"
GO_SMOKE_DIR="$(mktemp -d)"
cat >"$JAVA_SMOKE_DIR/Smoke.java" <<'EOF'
public final class Smoke {
    public static void main(String[] args) {
        if (1 + 2 != 3) {
            throw new RuntimeException("java smoke failed");
        }
        System.out.println("java smoke ok");
    }
}
EOF
javac "$JAVA_SMOKE_DIR/Smoke.java"
java -cp "$JAVA_SMOKE_DIR" Smoke
cat >"$GO_SMOKE_DIR/main.go" <<'EOF'
package main

import "fmt"

func main() {
	if 1+2 != 3 {
		panic("go smoke failed")
	}
	fmt.Println("go smoke ok")
}
EOF
go run "$GO_SMOKE_DIR/main.go"
df -h "$ROOT"

if [[ -n "${CUDA_VISIBLE_DEVICES:-}" ]]; then
  echo "Using caller-provided CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES for controlled preflight."
else
  IDLE_GPU="$(pick_idle_gpu || true)"
  if [[ -z "${IDLE_GPU:-}" ]]; then
    echo "Unable to find an idle GPU for controlled preflight." >&2
    exit 1
  fi
  export CUDA_VISIBLE_DEVICES="$IDLE_GPU"
  echo "Using CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES for controlled preflight."
fi
PREFLIGHT_GPU_SLOTS="$(visible_gpu_slot_count)"
echo "Using PREFLIGHT_GPU_SLOTS=$PREFLIGHT_GPU_SLOTS for controlled preflight."

AUDIT_ARGS=(
  "$PYTHON_BIN" "$ROOT/scripts/audit_full_matrix.py"
  "--manifest" "$FULL_MANIFEST_PATH"
  "--profile" "$FULL_PROFILE"
  "--strict-hf-cache"
  "--model-load-smoke"
  "--runtime-smoke"
  "--runtime-smoke-timeout-seconds" "$COMMAND_TIMEOUT_SECONDS"
  "--skip-provider-credentials"
)
if [[ $SKIP_HF_ACCESS -eq 1 ]]; then
  AUDIT_ARGS+=("--skip-hf-access")
fi
"${AUDIT_ARGS[@]}"

ensure_preflight_control_surfaces_safe
"$PYTHON_BIN" "$ROOT/scripts/capture_environment.py" --label formal_execution_host_pre_rerun --execution-mode single_host_canonical --output-json "$ENVIRONMENT_JSON_PATH" --output-md "$ENVIRONMENT_MD_PATH"
if [[ $FORMAL_FULL_ONLY -eq 1 ]]; then
  validate_matrix_output_surface "$FULL_PROFILE"
  "$PYTHON_BIN" "$ROOT/scripts/run_full_matrix.py" --manifest "$FULL_MANIFEST_PATH" --profile "$FULL_PROFILE" --output-root "$OUTPUT_PATH" --gpu-slots "$PREFLIGHT_GPU_SLOTS" --allow-formal-release-path --dry-run
else
  validate_matrix_output_surface "$STAGE_A_PROFILE"
  "$PYTHON_BIN" "$ROOT/scripts/run_full_matrix.py" --manifest "$STAGE_A_MANIFEST_PATH" --profile "$STAGE_A_PROFILE" --output-root "$OUTPUT_PATH" --gpu-slots "$PREFLIGHT_GPU_SLOTS" --dry-run
  validate_matrix_output_surface "$STAGE_B_PROFILE"
  "$PYTHON_BIN" "$ROOT/scripts/run_full_matrix.py" --manifest "$STAGE_B_MANIFEST_PATH" --profile "$STAGE_B_PROFILE" --output-root "$OUTPUT_PATH" --gpu-slots "$PREFLIGHT_GPU_SLOTS" --dry-run
fi

ensure_preflight_control_surfaces_safe
"$PYTHON_BIN" - "$ROOT" "$PREFLIGHT_RECEIPT_PATH" "$FORMAL_FULL_ONLY" "$FULL_MANIFEST_PATH" "$FULL_PROFILE" "$STAGE_A_MANIFEST_PATH" "$STAGE_A_PROFILE" "$STAGE_B_MANIFEST_PATH" "$STAGE_B_PROFILE" "$OUTPUT_PATH" "$ENVIRONMENT_JSON_PATH" "$ENVIRONMENT_MD_PATH" "$SKIP_HF_ACCESS" "$PYTHON_BIN" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

project_root = Path(sys.argv[1]).resolve()
receipt_path = Path(sys.argv[2])
formal_full_only = bool(int(sys.argv[3]))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from codemarkbench.suite import SUITE_MODEL_REVISIONS
from scripts import certify_suite_precheck


def file_sha256(path_text: str) -> str:
    return hashlib.sha256(Path(path_text).read_bytes()).hexdigest()


def safe_write_text(path: Path, payload: str) -> None:
    current = project_root
    if current.is_symlink():
        raise SystemExit(f"refusing to write remote preflight receipt through symlinked path components: {current}")
    for part in path.relative_to(project_root).parts:
        current = current / part
        if current.is_symlink():
            raise SystemExit(f"refusing to write remote preflight receipt through symlinked path components: {current}")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def normalized_cuda_visible_devices() -> str:
    tokens = [token.strip() for token in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if token.strip()]
    return ",".join(tokens)


payload = {
    "schema_version": 5,
    "receipt_type": "remote_preflight",
    "status": "passed",
    "created_at_epoch_seconds": int(time.time()),
    "full_manifest": sys.argv[4],
    "full_profile": sys.argv[5],
    "output_root": sys.argv[10],
    "environment_json": sys.argv[11],
    "environment_md": sys.argv[12],
    "skip_hf_access": bool(int(sys.argv[13])),
    "formal_full_only": formal_full_only,
    "manifest_digests": {
        "full_manifest": file_sha256(sys.argv[4]),
    },
    "suite_model_revisions": dict(SUITE_MODEL_REVISIONS),
    "runtime_checkout_receipt": certify_suite_precheck._current_runtime_checkout_receipt(),
    "environment_receipt": {
        "python_bin": str(Path(sys.argv[14]).resolve()),
        "python_executable": "",
        "environment_fingerprint": "",
        "cuda_visible_devices": "",
        "preflight_gpu_slots": 0,
    },
}
if not formal_full_only:
    payload.update(
        {
            "stage_a_manifest": sys.argv[6],
            "stage_a_profile": sys.argv[7],
            "stage_b_manifest": sys.argv[8],
            "stage_b_profile": sys.argv[9],
        }
    )
    payload["manifest_digests"].update(
        {
            "stage_a_manifest": file_sha256(sys.argv[6]),
            "stage_b_manifest": file_sha256(sys.argv[8]),
        }
    )
environment_payload = json.loads(Path(sys.argv[11]).read_text(encoding="utf-8"))
payload["environment_receipt"] = certify_suite_precheck._environment_receipt_from_payload(
    python_bin=sys.argv[14],
    environment_payload=environment_payload,
    code_snapshot_digest=str(environment_payload.get("execution", {}).get("code_snapshot_digest", "")).strip(),
    cuda_visible_devices=normalized_cuda_visible_devices(),
)
safe_write_text(receipt_path, json.dumps(payload, indent=2) + "\n")
PY

echo "Remote preflight passed."

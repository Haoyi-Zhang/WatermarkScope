#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CANONICAL_MANIFEST="configs/matrices/suite_all_models_methods.json"
CANONICAL_PROFILE="suite_all_models_methods"
DEFAULT_REMOTE_VENV="${CODEMARKBENCH_REMOTE_VENV:-}"

MANIFEST=""
PROFILE=""
CANONICAL_MANIFEST_ARG="$CANONICAL_MANIFEST"
CANONICAL_PROFILE_ARG="$CANONICAL_PROFILE"
SHARD_INDEX=""
SHARD_COUNT="${SHARD_COUNT:-}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT/results/matrix}"
CERTIFICATIONS_ROOT="${CERTIFICATIONS_ROOT:-$ROOT/results/certifications}"
PYTHON_BIN="${PYTHON_BIN:-}"
VENV_DIR="${VENV_DIR:-}"
export PYTHONDONTWRITEBYTECODE=1
GPU_SLOTS="${GPU_SLOTS:-8}"
GPU_POOL_MODE="${GPU_POOL_MODE:-shared}"
CPU_WORKERS="${CPU_WORKERS:-9}"
RETRY_COUNT="${RETRY_COUNT:-1}"
DRY_RUN=0
NO_CLEAN=0
READINESS_ONLY=0
SKIP_READINESS=0

usage() {
  cat <<'EOF'
Usage: run_matrix_shard.sh --manifest PATH --profile NAME --shard-index N [options]

Host-local shard wrapper for optional identical-execution-class sharded reproduction.
This script performs readiness checks locally, writes a shard-scoped receipt under
results/certifications/<shard_profile>/, preserves shard certification state when
requested during the launch-after-readiness handoff, cleans shard-local launch outputs
immediately before matrix execution, and then launches run_full_matrix.py with the
fixed shard-throughput settings. Use --readiness-only when you want all shard hosts to
finish readiness first, then launch them together later with --skip-readiness
--no-clean. The published reviewer-safe
workflow uses two hosts, but this wrapper remains parameterized by shard count for
operator-controlled layouts.
EOF
}

resolve_abs_path() {
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

effective_visible_gpu_count() {
  python3 - <<'PY'
import os

tokens = [token.strip() for token in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if token.strip()]
print(len(tokens))
PY
}

normalized_visible_devices() {
  python3 - <<'PY'
import os

tokens = [token.strip() for token in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if token.strip()]
print(",".join(tokens))
PY
}

resolve_repo_rel_path() {
  local value="$1"
  local absolute
  absolute="$(resolve_abs_path "$value")"
  case "$absolute" in
    "$ROOT"/*)
      printf '%s\n' "${absolute#"$ROOT"/}"
      ;;
    *)
      printf '%s\n' "$absolute"
      ;;
  esac
}

is_safe_profile_name() {
  local value="$1"
  [[ "$value" =~ ^[A-Za-z0-9._-]+$ ]]
}

require_repo_results_root() {
  local value="$1"
  local expected_root="$2"
  local flag_name="$3"
  case "$value" in
    "$expected_root"|"$expected_root"/*)
      ;;
    *)
      echo "$flag_name must stay under $expected_root; got $value" >&2
      exit 1
      ;;
  esac
}

validate_visible_device_ordinals() {
  python3 - <<'PY'
import os
import subprocess

tokens = [token.strip() for token in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if token.strip()]
if not tokens:
    raise SystemExit("The canonical reviewer-safe shard contract requires CUDA_VISIBLE_DEVICES to be set.")
if any(not token.isdigit() for token in tokens):
    raise SystemExit(
        "The canonical reviewer-safe shard contract requires numeric CUDA_VISIBLE_DEVICES ordinals; "
        f"got {','.join(tokens)}."
    )
if len(set(tokens)) != len(tokens):
    raise SystemExit(
        "The canonical reviewer-safe shard contract requires distinct CUDA_VISIBLE_DEVICES ordinals; "
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
        "The canonical reviewer-safe shard contract requires a detectable GPU inventory from nvidia-smi "
        f"before launch-time validation: {exc}"
    )
physical = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
missing = [token for token in tokens if token not in physical]
if missing:
    raise SystemExit(
        "The canonical reviewer-safe shard contract requires CUDA_VISIBLE_DEVICES to reference actual host GPU ordinals; "
        f"missing={missing}, detected={physical}"
    )
PY
}

if [[ -z "$VENV_DIR" ]]; then
  if [[ -n "$DEFAULT_REMOTE_VENV" && -d "$DEFAULT_REMOTE_VENV" ]]; then
    VENV_DIR="$DEFAULT_REMOTE_VENV"
  else
    VENV_DIR="$ROOT/.venv/tosem_release"
  fi
fi

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
    --canonical-manifest)
      CANONICAL_MANIFEST_ARG="$2"
      shift 2
      ;;
    --canonical-profile)
      CANONICAL_PROFILE_ARG="$2"
      shift 2
      ;;
    --shard-index)
      SHARD_INDEX="$2"
      shift 2
      ;;
    --shard-count)
      SHARD_COUNT="$2"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    --certifications-root)
      CERTIFICATIONS_ROOT="$2"
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
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --readiness-only)
      READINESS_ONLY=1
      shift
      ;;
    --skip-readiness)
      SKIP_READINESS=1
      shift
      ;;
    --no-clean)
      NO_CLEAN=1
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

if [[ -z "$MANIFEST" || -z "$PROFILE" || -z "$SHARD_INDEX" ]]; then
  echo "Missing required arguments: --manifest PATH --profile NAME --shard-index N" >&2
  usage >&2
  exit 1
fi

if ! is_safe_profile_name "$PROFILE"; then
  echo "Invalid --profile: $PROFILE. Profile names must be simple identifiers without path separators." >&2
  exit 1
fi

if ! is_safe_profile_name "$CANONICAL_PROFILE_ARG"; then
  echo "Invalid --canonical-profile: $CANONICAL_PROFILE_ARG. Profile names must be simple identifiers without path separators." >&2
  exit 1
fi

if [[ ! "$SHARD_INDEX" =~ ^[0-9]+$ ]]; then
  echo "Invalid --shard-index: $SHARD_INDEX" >&2
  exit 1
fi

if [[ $READINESS_ONLY -eq 1 && $SKIP_READINESS -eq 1 ]]; then
  echo "Use either --readiness-only or --skip-readiness, not both." >&2
  exit 1
fi

if [[ $NO_CLEAN -eq 1 && $SKIP_READINESS -eq 0 ]]; then
  echo "--no-clean is only valid with --skip-readiness in the optional shard flow." >&2
  echo "Fresh shard launches must rerun readiness and always clean shard-local launch outputs before execution." >&2
  exit 1
fi

if [[ $SKIP_READINESS -eq 1 && $NO_CLEAN -eq 0 ]]; then
  echo "Use --skip-readiness together with --no-clean so the already-passed readiness receipt and shard certification state survive until launch-time validation." >&2
  exit 1
fi

MANIFEST_PATH="$(resolve_abs_path "$MANIFEST")"
CANONICAL_MANIFEST_PATH="$(resolve_abs_path "$CANONICAL_MANIFEST_ARG")"
CANONICAL_MANIFEST_DEFAULT_PATH="$(resolve_abs_path "$CANONICAL_MANIFEST")"
OUTPUT_PATH="$(resolve_abs_path "$OUTPUT_ROOT")"
CERTIFICATIONS_PATH="$(resolve_abs_path "$CERTIFICATIONS_ROOT")"
MANIFEST_REL="$(resolve_repo_rel_path "$MANIFEST")"
CANONICAL_MANIFEST_REL="$(resolve_repo_rel_path "$CANONICAL_MANIFEST_ARG")"
OUTPUT_ROOT_REL="$(resolve_repo_rel_path "$OUTPUT_ROOT")"
CERTIFICATIONS_ROOT_REL="$(resolve_repo_rel_path "$CERTIFICATIONS_ROOT")"
SHARD_OUTPUT_DIR="$OUTPUT_PATH/$PROFILE"
SHARD_CERT_DIR="$CERTIFICATIONS_PATH/$PROFILE"
SHARD_ENV_DIR="$ROOT/results/environment/$PROFILE"
SHARD_AUDIT_DIR="$ROOT/results/audits/$PROFILE"
SHARD_FIGURE_DIR="$ROOT/results/figures/$PROFILE"
SHARD_TABLE_DIR="$ROOT/results/tables/$PROFILE"
ENV_JSON="$SHARD_CERT_DIR/host_environment.json"
ENV_MD="$SHARD_CERT_DIR/host_environment.md"
BENCH_AUDIT_JSON="$SHARD_CERT_DIR/benchmark_audit.json"
BENCH_AUDIT_LOG="$SHARD_CERT_DIR/benchmark_audit.log"
FULL_AUDIT_JSON="$SHARD_CERT_DIR/full_matrix_audit.json"
FULL_AUDIT_LOG="$SHARD_CERT_DIR/full_matrix_audit.log"
READINESS_JSON="$SHARD_CERT_DIR/matrix_shard_readiness.json"

if [[ "$MANIFEST_PATH" == "$CANONICAL_MANIFEST_PATH" && "$PROFILE" == "$CANONICAL_PROFILE_ARG" ]]; then
  echo "Use scripts/remote/run_formal_single_host_full.sh for the formal single-host full suite; run_matrix_shard.sh is only for the optional two-host sharded identical-execution-class reproduction path." >&2
  exit 1
fi

if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$VENV_DIR/bin/python"
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing Python interpreter: $PYTHON_BIN" >&2
  echo "Create the venv first with: bash $ROOT/scripts/remote/bootstrap_linux_gpu.sh --install --venv $VENV_DIR" >&2
  exit 1
fi

require_repo_results_root "$OUTPUT_PATH" "$ROOT/results/matrix" "--output-root"
require_repo_results_root "$CERTIFICATIONS_PATH" "$ROOT/results/certifications" "--certifications-root"

if [[ -z "$SHARD_COUNT" ]]; then
  SHARD_COUNT="$("$PYTHON_BIN" - "$MANIFEST_PATH" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
count = int(payload.get("shard_count", 0) or 0)
if count <= 0:
    raise SystemExit("0")
print(count)
PY
)"
fi
if [[ ! "$SHARD_COUNT" =~ ^[0-9]+$ ]]; then
  echo "Invalid --shard-count: $SHARD_COUNT" >&2
  exit 1
fi
if [[ "$SHARD_INDEX" -lt 1 || "$SHARD_INDEX" -gt "$SHARD_COUNT" ]]; then
  echo "Shard index must be between 1 and $SHARD_COUNT inclusive." >&2
  exit 1
fi
if [[ "$CANONICAL_MANIFEST_PATH" == "$CANONICAL_MANIFEST_DEFAULT_PATH" && "$CANONICAL_PROFILE_ARG" == "$CANONICAL_PROFILE" ]]; then
  if [[ "$SHARD_COUNT" != "2" ]]; then
    echo "The published reviewer-safe sharded workflow for the canonical suite is fixed to two hosts/two shards." >&2
    exit 1
  fi
  if [[ "$GPU_SLOTS" != "8" || "$GPU_POOL_MODE" != "shared" || "$CPU_WORKERS" != "9" || "$RETRY_COUNT" != "1" ]]; then
    echo "The canonical reviewer-safe shard contract is fixed to --gpu-slots 8 --gpu-pool-mode shared --cpu-workers 9 --retry-count 1." >&2
    exit 1
  fi
  if [[ -z "${CUDA_VISIBLE_DEVICES:-}" || "$(effective_visible_gpu_count)" != "8" ]]; then
    echo "The canonical reviewer-safe shard contract requires CUDA_VISIBLE_DEVICES to expose exactly eight GPUs." >&2
    exit 1
  fi
  if [[ "$(normalized_visible_devices)" != "0,1,2,3,4,5,6,7" ]]; then
    echo "The canonical reviewer-safe shard contract requires CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7." >&2
    exit 1
  fi
  if ! validate_visible_device_ordinals; then
    exit 1
  fi
fi

run_step() {
  local label="$1"
  local log_path="$2"
  shift 2
  mkdir -p "$(dirname "$log_path")"
  echo "[matrix_shard] start $label: $*" | tee -a "$log_path"
  if "$@" 2>&1 | tee -a "$log_path"; then
    echo "[matrix_shard] finish $label: status=passed" | tee -a "$log_path"
    return 0
  else
    local exit_code=${PIPESTATUS[0]}
    echo "[matrix_shard] finish $label: status=failed exit_code=$exit_code" | tee -a "$log_path"
    return "$exit_code"
  fi
}

validate_shard_manifest() {
  "$PYTHON_BIN" - \
    "$ROOT" \
    "$MANIFEST_PATH" \
    "$PROFILE" \
    "$CANONICAL_MANIFEST_PATH" \
    "$CANONICAL_PROFILE_ARG" \
    "$SHARD_INDEX" \
    "$SHARD_COUNT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
profile = sys.argv[3]
canonical_manifest_path = Path(sys.argv[4])
canonical_profile = sys.argv[5]
shard_index = int(sys.argv[6])
shard_count = int(sys.argv[7])

payload = json.loads(manifest_path.read_text(encoding="utf-8"))
if not isinstance(payload, dict):
    raise SystemExit(f"{manifest_path} must be a JSON object")
if str(payload.get("profile", "")).strip() != profile:
    raise SystemExit(f"{manifest_path} profile mismatch for shard launch")
if str(payload.get("canonical_profile", "")).strip() != canonical_profile:
    raise SystemExit(f"{manifest_path} canonical_profile mismatch for shard launch")
canonical_manifest = str(payload.get("canonical_manifest", "")).strip()
expected_rel = str(canonical_manifest_path.relative_to(root)).replace("\\", "/")
observed_canonical = root / canonical_manifest if canonical_manifest and not Path(canonical_manifest).is_absolute() else Path(canonical_manifest)
if canonical_manifest != expected_rel and observed_canonical.resolve(strict=False) != canonical_manifest_path.resolve(strict=False):
    raise SystemExit(f"{manifest_path} canonical_manifest mismatch for shard launch")
if int(payload.get("shard_index", 0) or 0) != shard_index:
    raise SystemExit(f"{manifest_path} shard_index mismatch for shard launch")
if int(payload.get("shard_count", 0) or 0) != shard_count:
    raise SystemExit(f"{manifest_path} shard_count mismatch for shard launch")
run_ids = [str(run.get("run_id", "")).strip() for run in payload.get("runs", []) if isinstance(run, dict)]
if not run_ids:
    raise SystemExit(f"{manifest_path} contains no runs")
if len(run_ids) != len(set(run_ids)):
    raise SystemExit(f"{manifest_path} contains duplicate run_id values")
PY
}

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

ensure_runtime_checkouts() {
  if runtime_checkouts_ready; then
    echo "Pinned runtime upstream checkouts already validate cleanly; skipping network refresh."
    return 0
  fi
  echo "Pinned runtime upstream checkouts are missing or invalid." >&2
  echo "Run bash $ROOT/scripts/fetch_runtime_upstreams.sh all explicitly before readiness or shard launch." >&2
  return 1
}

toolchain_smoke() {
  "$PYTHON_BIN" -V
  command -v g++ >/dev/null 2>&1 || { echo "Missing g++" >&2; return 1; }
  command -v javac >/dev/null 2>&1 || { echo "Missing javac" >&2; return 1; }
  command -v java >/dev/null 2>&1 || { echo "Missing java" >&2; return 1; }
  command -v node >/dev/null 2>&1 || { echo "Missing node" >&2; return 1; }
  command -v go >/dev/null 2>&1 || { echo "Missing go" >&2; return 1; }
  command -v nvidia-smi >/dev/null 2>&1 || { echo "Missing nvidia-smi" >&2; return 1; }
  g++ --version | head -n 1
  javac -version
  java -version
  node --version
  go version
  nvidia-smi >/dev/null
  node -e "const add = (a, b) => a + b; if (add(1, 2) !== 3) { process.exit(1); } console.log('node smoke ok');"
  local java_smoke_dir
  local go_smoke_dir
  java_smoke_dir="$(mktemp -d)"
  go_smoke_dir="$(mktemp -d)"
  cat >"$java_smoke_dir/Smoke.java" <<'EOF'
public final class Smoke {
    public static void main(String[] args) {
        if (1 + 2 != 3) {
            throw new RuntimeException("java smoke failed");
        }
        System.out.println("java smoke ok");
    }
}
EOF
  javac "$java_smoke_dir/Smoke.java"
  java -cp "$java_smoke_dir" Smoke
  cat >"$go_smoke_dir/main.go" <<'EOF'
package main

import "fmt"

func main() {
	if 1+2 != 3 {
		panic("go smoke failed")
	}
	fmt.Println("go smoke ok")
}
EOF
  go run "$go_smoke_dir/main.go"
  rm -rf "$java_smoke_dir" "$go_smoke_dir"
}

write_readiness_receipt() {
  local status="$1"
  local failed_step="${2:-}"
  "$PYTHON_BIN" - \
    "$ROOT" \
    "$READINESS_JSON" \
    "$status" \
    "$failed_step" \
    "$MANIFEST_PATH" \
    "$MANIFEST_REL" \
    "$PROFILE" \
    "$CANONICAL_MANIFEST_PATH" \
    "$CANONICAL_MANIFEST_REL" \
    "$CANONICAL_PROFILE_ARG" \
    "$SHARD_INDEX" \
    "$SHARD_COUNT" \
    "$GPU_SLOTS" \
    "$GPU_POOL_MODE" \
    "$CPU_WORKERS" \
    "$RETRY_COUNT" \
    "$OUTPUT_ROOT_REL" \
    "$ENV_JSON" \
    "$ENV_MD" \
    "$BENCH_AUDIT_JSON" \
    "$FULL_AUDIT_JSON" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1])
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from scripts import _repo_snapshot, capture_environment

receipt_path = Path(sys.argv[2])
status = sys.argv[3]
failed_step = sys.argv[4]
manifest_path = Path(sys.argv[5])
manifest_rel = sys.argv[6]
profile = sys.argv[7]
canonical_manifest_path = Path(sys.argv[8])
canonical_manifest_rel = sys.argv[9]
canonical_profile = sys.argv[10]
shard_index = int(sys.argv[11])
shard_count = int(sys.argv[12])
gpu_slots = int(sys.argv[13])
gpu_pool_mode = sys.argv[14]
cpu_workers = int(sys.argv[15])
retry_count = int(sys.argv[16])
output_root_rel = sys.argv[17]
environment_json = Path(sys.argv[18])
environment_md = Path(sys.argv[19])
benchmark_audit_json = Path(sys.argv[20])
full_audit_json = Path(sys.argv[21])


def _load_json(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _repo_rel(path: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return str(resolved.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path.resolve(strict=False)).replace("\\", "/")


environment_payload = _load_json(environment_json)
host_environment_fingerprint = ""
execution_environment_fingerprint = ""
visible_gpu_count = 0
if isinstance(environment_payload, dict):
    cuda_visible_devices = str(os.environ.get("CUDA_VISIBLE_DEVICES", "")).strip()
    host_environment_fingerprint = capture_environment.environment_fingerprint_sha256(environment_payload)
    execution_environment_fingerprint = capture_environment.execution_environment_fingerprint_sha256(
        environment_payload,
        cuda_visible_devices=cuda_visible_devices,
    )
    visible_gpu_count = len(
        capture_environment.execution_class_gpu_devices(
            environment_payload,
            cuda_visible_devices=cuda_visible_devices,
        )
    )
shard_manifest_payload = _load_json(manifest_path)
if not isinstance(shard_manifest_payload, dict):
    raise SystemExit(f"Shard manifest must be a JSON object: {manifest_path}")
suite_model_revisions = dict(
    shard_manifest_payload.get("canonical_model_revisions")
    or shard_manifest_payload.get("model_revisions")
    or {}
)
receipt = {
    "schema_version": 2,
    "receipt_type": "matrix_shard_readiness",
    "status": status,
    "failed_step": failed_step or None,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "manifest": manifest_rel,
    "profile": profile,
    "host": {
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
    },
    "execution_mode": "sharded_identical_execution_class",
    "canonical_manifest": canonical_manifest_rel,
    "canonical_profile": canonical_profile,
    "manifest_digests": {
        "canonical_manifest": _sha256(canonical_manifest_path),
        "manifest": _sha256(manifest_path),
    },
    "code_snapshot_digest": _repo_snapshot.repo_snapshot_sha256(root),
    "suite_model_revisions": suite_model_revisions,
    "shard_manifest": manifest_rel,
    "shard_profile": profile,
    "shard_index": shard_index,
    "shard_count": shard_count,
    "gpu_slots": gpu_slots,
    "gpu_pool_mode": gpu_pool_mode,
    "cpu_workers": cpu_workers,
    "retry_count": retry_count,
    "paths": {
        "environment_json": _repo_rel(environment_json),
        "environment_md": _repo_rel(environment_md),
        "benchmark_audit_json": _repo_rel(benchmark_audit_json),
        "full_matrix_audit_json": _repo_rel(full_audit_json),
        "output_root": output_root_rel,
    },
    "environment_receipt": {
        "python_bin": str(Path(sys.executable).resolve()),
        "python_executable": str(environment_payload.get("python", {}).get("executable", "")).strip()
        if isinstance(environment_payload, dict)
        else "",
        "environment_fingerprint": execution_environment_fingerprint,
        "host_environment_fingerprint": host_environment_fingerprint,
        "execution_environment_fingerprint": execution_environment_fingerprint,
        "cuda_visible_devices": str(os.environ.get("CUDA_VISIBLE_DEVICES", "")).strip(),
        "visible_gpu_count": visible_gpu_count,
        "preflight_gpu_slots": gpu_slots,
    },
    "environment": environment_payload,
    "audits": {
        "benchmark_audit": _load_json(benchmark_audit_json),
        "full_matrix_audit": _load_json(full_audit_json),
    },
}
receipt_path.parent.mkdir(parents=True, exist_ok=True)
receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
PY
}

validate_existing_readiness_receipt() {
  "$PYTHON_BIN" "$ROOT/scripts/_matrix_shard_launch.py" validate-existing-receipt \
    --root "$ROOT" \
    --receipt "$READINESS_JSON" \
    --profile "$PROFILE" \
    --manifest-rel "$MANIFEST_REL" \
    --manifest "$MANIFEST_PATH" \
    --canonical-manifest "$CANONICAL_MANIFEST_PATH" \
    --shard-index "$SHARD_INDEX" \
    --shard-count "$SHARD_COUNT" \
    --gpu-slots "$GPU_SLOTS" \
    --gpu-pool-mode "$GPU_POOL_MODE" \
    --cpu-workers "$CPU_WORKERS" \
    --retry-count "$RETRY_COUNT"
}

validate_shard_full_matrix_audit() {
  "$PYTHON_BIN" - \
    "$ROOT" \
    "$FULL_AUDIT_JSON" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from scripts.merge_sharded_matrix import _shard_audit_is_merge_safe

audit_path = Path(sys.argv[2])
payload = json.loads(audit_path.read_text(encoding="utf-8"))
if not _shard_audit_is_merge_safe(payload):
    raise SystemExit(f"{audit_path} is not merge-safe for shard execution")
issues = payload.get("issues", [])
print(
    json.dumps(
        {
            "audit_path": str(audit_path),
            "status": str(payload.get("status", "")).strip(),
            "issues": issues,
            "merge_safe": True,
        },
        ensure_ascii=False,
    )
)
PY
}

prepare_clean_launch_tree() {
  "$PYTHON_BIN" "$ROOT/scripts/_matrix_shard_launch.py" prepare-clean-launch-tree \
    --root "$ROOT" \
    --output-dir "$SHARD_OUTPUT_DIR" \
    --extra-dir "$SHARD_AUDIT_DIR" \
    --extra-dir "$SHARD_FIGURE_DIR" \
    --extra-dir "$SHARD_TABLE_DIR"
}

run_audit_full_matrix_step() {
  mkdir -p "$(dirname "$FULL_AUDIT_LOG")"
  echo "[matrix_shard] start audit_full_matrix: $PYTHON_BIN $ROOT/scripts/audit_full_matrix.py --manifest $MANIFEST_PATH --profile $PROFILE --output $FULL_AUDIT_JSON --strict-hf-cache --model-load-smoke --runtime-smoke --skip-provider-credentials --skip-hf-access" | tee -a "$FULL_AUDIT_LOG"
  set +e
  "$PYTHON_BIN" "$ROOT/scripts/audit_full_matrix.py" \
    --manifest "$MANIFEST_PATH" \
    --profile "$PROFILE" \
    --output "$FULL_AUDIT_JSON" \
    --strict-hf-cache \
    --model-load-smoke \
    --runtime-smoke \
    --skip-provider-credentials \
    --skip-hf-access 2>&1 | tee -a "$FULL_AUDIT_LOG"
  local exit_code=${PIPESTATUS[0]}
  set -e
  if [[ $exit_code -eq 0 ]]; then
    echo "[matrix_shard] finish audit_full_matrix: status=passed" | tee -a "$FULL_AUDIT_LOG"
    return 0
  fi
  if [[ -f "$FULL_AUDIT_JSON" ]] && validate_shard_full_matrix_audit >>"$FULL_AUDIT_LOG" 2>&1; then
    echo "[matrix_shard] finish audit_full_matrix: status=passed merge_safe_has_issues=true exit_code=$exit_code" | tee -a "$FULL_AUDIT_LOG"
    return 0
  fi
  echo "[matrix_shard] finish audit_full_matrix: status=failed exit_code=$exit_code" | tee -a "$FULL_AUDIT_LOG"
  return "$exit_code"
}

if [[ $DRY_RUN -eq 1 ]]; then
  cat <<EOF
{
  "root": "$ROOT",
  "manifest": "$MANIFEST_REL",
  "profile": "$PROFILE",
  "canonical_manifest": "$CANONICAL_MANIFEST_REL",
  "canonical_profile": "$CANONICAL_PROFILE_ARG",
  "shard_index": $SHARD_INDEX,
  "shard_count": $SHARD_COUNT,
  "output_root": "$OUTPUT_ROOT_REL",
  "certifications_root": "$CERTIFICATIONS_ROOT_REL",
  "gpu_slots": $GPU_SLOTS,
  "gpu_pool_mode": "$GPU_POOL_MODE",
  "cpu_workers": $CPU_WORKERS,
  "retry_count": $RETRY_COUNT,
  "environment_json": "$ENV_JSON",
  "environment_md": "$ENV_MD",
  "benchmark_audit_json": "$BENCH_AUDIT_JSON",
  "full_matrix_audit_json": "$FULL_AUDIT_JSON",
  "readiness_json": "$READINESS_JSON",
    "steps": [
    "validate_shard_manifest",
    "ensure_runtime_checkouts",
    "capture_environment or validate_existing_readiness_receipt",
    "toolchain_smoke",
    "audit_benchmarks and audit_full_matrix (unless --skip-readiness)",
    "validate_shard_full_matrix_audit",
    "write_readiness_receipt (unless --skip-readiness)",
    "prepare_clean_launch_tree before launch",
    "run_full_matrix"
  ]
}
EOF
  exit 0
fi

SHARD_LABEL="matrix_shard_${SHARD_INDEX}_of_${SHARD_COUNT}"
if [[ $SKIP_READINESS -eq 0 ]]; then
  if ! run_step "validate_shard_manifest" "$SHARD_CERT_DIR/validate_shard_manifest.log" validate_shard_manifest
  then
    write_readiness_receipt "failed" "validate_shard_manifest"
    exit 1
  fi

  if ! run_step "ensure_runtime_checkouts" "$SHARD_CERT_DIR/runtime_checkouts.log" ensure_runtime_checkouts
  then
    write_readiness_receipt "failed" "ensure_runtime_checkouts"
    exit 1
  fi

  if ! run_step "capture_environment" "$SHARD_CERT_DIR/capture_environment.log" \
    "$PYTHON_BIN" "$ROOT/scripts/capture_environment.py" \
    --label "$SHARD_LABEL" \
    --execution-mode sharded_identical_execution_class \
    --output-json "$ENV_JSON" \
    --output-md "$ENV_MD"
  then
    write_readiness_receipt "failed" "capture_environment"
    exit 1
  fi

  if ! run_step "toolchain_smoke" "$SHARD_CERT_DIR/toolchain_smoke.log" toolchain_smoke
  then
    write_readiness_receipt "failed" "toolchain_smoke"
    exit 1
  fi

  if ! run_step "audit_benchmarks" "$BENCH_AUDIT_LOG" \
    "$PYTHON_BIN" "$ROOT/scripts/audit_benchmarks.py" \
    --manifest "$MANIFEST_PATH" \
    --matrix-profile "$PROFILE" \
    --output "$BENCH_AUDIT_JSON"
  then
    write_readiness_receipt "failed" "audit_benchmarks"
    exit 1
  fi

  if ! run_audit_full_matrix_step
  then
    write_readiness_receipt "failed" "audit_full_matrix"
    exit 1
  fi

  if ! run_step "validate_shard_full_matrix_audit" "$FULL_AUDIT_LOG" validate_shard_full_matrix_audit
  then
    write_readiness_receipt "failed" "validate_shard_full_matrix_audit"
    exit 1
  fi

  write_readiness_receipt "passed"
else
  if ! run_step "ensure_runtime_checkouts" "$SHARD_CERT_DIR/runtime_checkouts.log" ensure_runtime_checkouts
  then
    exit 1
  fi
  if ! run_step "validate_existing_readiness_receipt" "$SHARD_CERT_DIR/validate_existing_readiness_receipt.log" validate_existing_readiness_receipt
  then
    exit 1
  fi
fi

if [[ $READINESS_ONLY -eq 1 ]]; then
  echo "[matrix_shard] readiness-only complete for $PROFILE (shard $SHARD_INDEX/$SHARD_COUNT)." >&2
  exit 0
fi

if ! run_step "prepare_clean_launch_tree" "$SHARD_CERT_DIR/prepare_clean_launch_tree.log" prepare_clean_launch_tree
then
  exit 1
fi

echo "[matrix_shard] readiness complete for $PROFILE (shard $SHARD_INDEX/$SHARD_COUNT)." >&2
exec "$PYTHON_BIN" "$ROOT/scripts/run_full_matrix.py" \
  --manifest "$MANIFEST_REL" \
  --profile "$PROFILE" \
  --output-root "$OUTPUT_ROOT_REL" \
  --gpu-slots "$GPU_SLOTS" \
  --gpu-pool-mode "$GPU_POOL_MODE" \
  --cpu-workers "$CPU_WORKERS" \
  --retry-count "$RETRY_COUNT"

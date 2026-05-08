#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DEFAULT_REMOTE_VENV="${CODEMARKBENCH_REMOTE_VENV:-}"
VENV_DIR="${VENV_DIR:-}"
if [[ -z "$VENV_DIR" ]]; then
  if [[ -n "$DEFAULT_REMOTE_VENV" && -d "$DEFAULT_REMOTE_VENV" ]]; then
    VENV_DIR="$DEFAULT_REMOTE_VENV"
  else
    VENV_DIR="$ROOT/.venv/tosem_release"
  fi
fi
MODEL_CACHE_ROOT="${MODEL_CACHE_ROOT:-}"
INSTALL=0
DRY_RUN=0
SYSTEM_SITE_PACKAGES=0

usage() {
  cat <<'EOF'
Usage: bootstrap_linux_gpu.sh [--install] [--dry-run] [--system-site-packages] [--python PATH] [--venv PATH] [--model-cache-root PATH]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install)
      INSTALL=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --system-site-packages)
      SYSTEM_SITE_PACKAGES=1
      shift
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --venv)
      VENV_DIR="$2"
      shift 2
      ;;
    --model-cache-root)
      MODEL_CACHE_ROOT="$2"
      shift 2
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

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Missing Python interpreter: $PYTHON_BIN" >&2
  exit 1
fi

mkdir -p "$ROOT/results/runs" "$ROOT/results/release_bundle"

if [[ -n "$MODEL_CACHE_ROOT" ]]; then
  mkdir -p "$MODEL_CACHE_ROOT"
  if [[ -L "$ROOT/model_cache" ]]; then
    CURRENT_TARGET="$(readlink "$ROOT/model_cache")"
    if [[ "$CURRENT_TARGET" != "$MODEL_CACHE_ROOT" ]]; then
      rm -f "$ROOT/model_cache"
      ln -s "$MODEL_CACHE_ROOT" "$ROOT/model_cache"
    fi
  elif [[ -d "$ROOT/model_cache" ]]; then
    if [[ -n "$(ls -A "$ROOT/model_cache" 2>/dev/null)" ]]; then
      echo "Refusing to replace non-empty local model_cache directory: $ROOT/model_cache" >&2
      exit 1
    fi
    rmdir "$ROOT/model_cache"
    ln -s "$MODEL_CACHE_ROOT" "$ROOT/model_cache"
  elif [[ -e "$ROOT/model_cache" ]]; then
    echo "Refusing to replace non-directory model_cache path: $ROOT/model_cache" >&2
    exit 1
  else
    ln -s "$MODEL_CACHE_ROOT" "$ROOT/model_cache"
  fi
else
  mkdir -p "$ROOT/model_cache"
fi

if [[ $DRY_RUN -eq 1 ]]; then
  printf '%s\n' "{" \
    "  \"root\": \"${ROOT//\"/\\\"}\"," \
    "  \"python\": \"${PYTHON_BIN//\"/\\\"}\"," \
    "  \"venv\": \"${VENV_DIR//\"/\\\"}\"," \
    "  \"model_cache_root\": \"${MODEL_CACHE_ROOT//\"/\\\"}\"," \
    "  \"install\": ${INSTALL}," \
    "  \"system_site_packages\": ${SYSTEM_SITE_PACKAGES}," \
    "  \"results_dir\": \"${ROOT//\"/\\\"}/results/runs\"," \
    "  \"toolchain_reference\": \"${ROOT//\"/\\\"}/docs/remote_linux_gpu.md\"" \
    "}"
  exit 0
fi

if [[ $INSTALL -eq 1 ]]; then
  if [[ ! -d "$VENV_DIR" ]]; then
    VENV_ARGS=()
    if [[ $SYSTEM_SITE_PACKAGES -eq 1 ]]; then
      VENV_ARGS+=(--system-site-packages)
    fi
    "$PYTHON_BIN" -m venv "${VENV_ARGS[@]}" "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  for CA_CANDIDATE in "${SSL_CERT_FILE:-}" "${REQUESTS_CA_BUNDLE:-}" "/etc/ssl/certs/ca-certificates.crt" "/etc/pki/tls/certs/ca-bundle.crt"; do
    if [[ -n "$CA_CANDIDATE" && -f "$CA_CANDIDATE" ]]; then
      export SSL_CERT_FILE="$CA_CANDIDATE"
      export REQUESTS_CA_BUNDLE="$CA_CANDIDATE"
      export PIP_CERT="$CA_CANDIDATE"
      break
    fi
  done
  python -m pip install --upgrade pip
  python -m pip install --no-compile -r "$ROOT/requirements.txt"
  if [[ -f "$ROOT/requirements-remote.txt" ]]; then
    python -m pip install --no-compile -r "$ROOT/requirements-remote.txt"
  fi
  if [[ -f "$ROOT/constraints-release-cu124.txt" ]]; then
    python -m pip install --no-compile --extra-index-url https://download.pytorch.org/whl/cu124 -r "$ROOT/constraints-release-cu124.txt"
  fi
  TORCH_STATUS="$(python - <<'PY'
import json
try:
    import torch
    payload = {
        "importable": True,
        "cuda_build": bool(getattr(torch.version, "cuda", None)),
        "cuda_available": bool(torch.cuda.is_available()),
        "version": str(getattr(torch, "__version__", "")),
        "cuda_version": str(getattr(torch.version, "cuda", "") or ""),
    }
except Exception as exc:
    payload = {
        "importable": False,
        "cuda_build": False,
        "cuda_available": False,
        "version": "",
        "cuda_version": "",
        "error": f"{type(exc).__name__}: {exc}",
    }
print(json.dumps(payload))
PY
)"
  NEEDS_TORCH_INSTALL="$(python - "$TORCH_STATUS" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
print("1" if not payload.get("importable", False) else "0")
PY
)"
  NEEDS_CUDA_TORCH="$(python - "$TORCH_STATUS" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
print("1" if not payload.get("cuda_build", False) else "0")
PY
)"
  if command -v nvidia-smi >/dev/null 2>&1; then
    if [[ "$NEEDS_TORCH_INSTALL" == "1" || "$NEEDS_CUDA_TORCH" == "1" ]]; then
      python -m pip install --no-compile --extra-index-url https://download.pytorch.org/whl/cu124 -r "$ROOT/constraints-release-cu124.txt"
    fi
    python - <<'PY'
import torch
if not getattr(torch.version, "cuda", None):
    raise SystemExit("Expected a CUDA-enabled torch build on this GPU host, but torch.version.cuda is empty.")
if not torch.cuda.is_available():
    raise SystemExit("Expected torch.cuda.is_available() to be true on this GPU host after bootstrap.")
print(f"torch {torch.__version__} with CUDA {torch.version.cuda} is ready")
PY
  elif [[ "$NEEDS_TORCH_INSTALL" == "1" ]]; then
    python -m pip install --no-compile --extra-index-url https://download.pytorch.org/whl/cu124 -r "$ROOT/constraints-release-cu124.txt"
  fi
fi

echo "Bootstrap complete."
echo "Root: $ROOT"
echo "Python: $PYTHON_BIN"
echo "Venv: $VENV_DIR"
echo "Note: bootstrap provisions the Python environment only; run_preflight.sh validates host compilers and runtimes."

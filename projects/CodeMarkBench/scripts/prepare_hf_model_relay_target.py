from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from verify_hf_model_clean_state import inspect_clean_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail closed before a single-model Hugging Face cache relay by requiring the target-side "
            "cache entry, helper processes, and common relay artifacts to be absent."
        )
    )
    parser.add_argument("--model", required=True, help="Model ID, for example Qwen/Qwen2.5-Coder-7B-Instruct.")
    parser.add_argument("--cache-dir", required=True, help="Target Hugging Face cache root.")
    parser.add_argument(
        "--process-pattern",
        action="append",
        default=[],
        help="Optional process substring that must not appear in `ps -ef` before relay.",
    )
    parser.add_argument(
        "--artifact-prefix",
        action="append",
        default=[],
        help="Artifact prefix whose common relay residue suffixes must all be absent before relay.",
    )
    parser.add_argument(
        "--extra-path",
        action="append",
        default=[],
        help="Optional extra file or directory path that must not exist before relay.",
    )
    parser.add_argument("--report", type=Path, default=None, help="Optional JSON receipt path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = inspect_clean_state(
        model=args.model,
        cache_dir=args.cache_dir,
        process_patterns=args.process_pattern,
        extra_paths=args.extra_path,
        artifact_prefixes=args.artifact_prefix,
    )
    payload["gate_type"] = "hf_model_relay_target_clean_state"
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

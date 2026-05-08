from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
DEFAULT_INPUT_ROWS = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_rows_{DATE}.jsonl"
DEFAULT_OUTPUT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_score_vectors_{DATE}_merged_v1.jsonl"
DEFAULT_MANIFEST = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_score_vectors_{DATE}_merged_v1_manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministically merge ProbeTrace canonical live shards.")
    parser.add_argument("--input-rows", default=str(DEFAULT_INPUT_ROWS.relative_to(ROOT)))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    parser.add_argument("--manifest-output", default=str(DEFAULT_MANIFEST.relative_to(ROOT)))
    parser.add_argument("--sources", nargs="+", required=True)
    parser.add_argument("--source-ranges", nargs="*", default=[], help="Optional source_index:start:end filters matching --sources.")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def row_key(row: dict) -> str:
    return f"{row.get('task_id')}::{row.get('candidate_owner_id')}"


def main() -> int:
    args = parse_args()
    input_rows_path = ROOT / args.input_rows
    expected_rows = read_jsonl(input_rows_path)
    expected_keys = [row_key(row) for row in expected_rows]
    expected_index = {key: index for index, key in enumerate(expected_keys)}
    blockers: list[str] = []
    if len(expected_keys) != 6000 or len(set(expected_keys)) != 6000:
        blockers.append("canonical_input_keys_not_6000_unique")

    range_by_source: dict[str, tuple[int, int]] = {}
    for item in args.source_ranges:
        parts = item.split(":")
        if len(parts) != 3:
            raise SystemExit(f"invalid_source_range:{item}")
        source_index = int(parts[0])
        range_by_source[args.sources[source_index]] = (int(parts[1]), int(parts[2]))

    merged: dict[str, dict] = {}
    duplicate_keys: list[str] = []
    source_summaries = []
    for source_rel in args.sources:
        source_path = ROOT / source_rel
        if not source_path.exists():
            blockers.append(f"source_missing:{source_rel}")
            continue
        rows = read_jsonl(source_path)
        source_range = range_by_source.get(source_rel)
        if source_range is not None:
            start, end = source_range
            rows = [row for row in rows if start <= expected_index.get(row_key(row), -1) < end]
        source_summaries.append(
            {
                "path": source_rel,
                "row_count": len(rows),
                "sha256": sha256(source_path),
                "canonical_index_filter": list(source_range) if source_range is not None else None,
            }
        )
        for row in rows:
            key = row_key(row)
            if key not in expected_index:
                blockers.append(f"unexpected_row_key:{key}")
                continue
            if key in merged:
                duplicate_keys.append(key)
                continue
            row = dict(row)
            row["canonical_input_index"] = expected_index[key]
            merged[key] = row
    missing_keys = [key for key in expected_keys if key not in merged]
    if duplicate_keys:
        blockers.append("duplicate_output_keys")
    if missing_keys:
        blockers.append("missing_output_keys")

    output_rows = [merged[key] for key in expected_keys if key in merged]
    claim_bearing_rows = sum(1 for row in output_rows if row.get("claim_bearing") is True)
    missing_hash_rows = sum(
        1
        for row in output_rows
        if not row.get("raw_provider_transcript_hash")
        or not row.get("structured_payload_hash")
        or not row.get("prompt_hash")
        or not row.get("source_record_hash")
        or not row.get("output_record_sha256")
    )
    if claim_bearing_rows != len(output_rows):
        blockers.append("non_claim_bearing_rows_in_merge")
    if missing_hash_rows:
        blockers.append("missing_hash_rows_in_merge")

    output_path = ROOT / args.output
    manifest_path = ROOT / args.manifest_output
    if output_path.exists() or manifest_path.exists():
        raise FileExistsError("refusing_to_overwrite_merged_probetrace_outputs")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")
    manifest = {
        "schema_version": "probetrace_multi_owner_live_shard_merge_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not blockers,
        "output": args.output,
        "output_sha256": sha256(output_path),
        "canonical_input": args.input_rows,
        "canonical_input_sha256": sha256(input_rows_path),
        "source_summaries": source_summaries,
        "row_count": len(output_rows),
        "expected_row_count": len(expected_keys),
        "claim_bearing_rows": claim_bearing_rows,
        "missing_hash_rows": missing_hash_rows,
        "missing_key_count": len(missing_keys),
        "duplicate_key_count": len(duplicate_keys),
        "role_counts": dict(sorted(Counter(row.get("control_role", "missing") for row in output_rows).items())),
        "split_counts": dict(sorted(Counter(row.get("split", "missing") for row in output_rows).items())),
        "owner_count": len({row.get("true_owner_id") for row in output_rows if row.get("true_owner_id")}),
        "language_count": len({row.get("language") for row in output_rows if row.get("language")}),
        "blockers": blockers,
        "merge_policy": "No result-based filtering. Rows are ordered only by canonical input order.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {output_path.relative_to(ROOT)}")
    print(f"[OK] Wrote {manifest_path.relative_to(ROOT)}")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())

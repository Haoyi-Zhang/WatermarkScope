from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
DEFAULT_INPUT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_rows_{DATE}.jsonl"
DEFAULT_OUT_DIR = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_shards_{DATE}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic ProbeTrace multi-owner input shards.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT.relative_to(ROOT)))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR.relative_to(ROOT)))
    parser.add_argument("--start-index", type=int, required=True, help="0-based inclusive row offset.")
    parser.add_argument("--end-index", type=int, required=True, help="0-based exclusive row offset.")
    parser.add_argument("--shard-size", type=int, default=600)
    parser.add_argument("--label", default="tail_parallel")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite shard input: {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def main() -> int:
    args = parse_args()
    source = ROOT / args.input
    out_dir = ROOT / args.out_dir
    rows = read_jsonl(source)
    if len(rows) != 6000:
        raise SystemExit(f"expected_6000_source_rows:{len(rows)}")
    if args.start_index < 0 or args.end_index > len(rows) or args.start_index >= args.end_index:
        raise SystemExit("invalid_shard_range")
    if args.shard_size <= 0:
        raise SystemExit("invalid_shard_size")

    manifest_rows = []
    for shard_id, start in enumerate(range(args.start_index, args.end_index, args.shard_size), start=1):
        end = min(start + args.shard_size, args.end_index)
        shard_rows = []
        for global_index, row in enumerate(rows[start:end], start=start):
            row = dict(row)
            row["canonical_input_index"] = global_index
            row["canonical_shard_label"] = args.label
            shard_rows.append(row)
        rel = f"probetrace_multi_owner_{args.label}_shard_{shard_id:02d}_{start:04d}_{end:04d}.jsonl"
        write_jsonl(out_dir / rel, shard_rows)
        manifest_rows.append(
            {
                "shard_id": shard_id,
                "path": (out_dir / rel).relative_to(ROOT).as_posix(),
                "start_index": start,
                "end_index": end,
                "row_count": len(shard_rows),
                "label": args.label,
            }
        )
    manifest = {
        "schema_version": "probetrace_multi_owner_shard_inputs_v1",
        "claim_bearing": False,
        "source_input": args.input,
        "source_row_count": len(rows),
        "start_index": args.start_index,
        "end_index": args.end_index,
        "shard_size": args.shard_size,
        "label": args.label,
        "shards": manifest_rows,
        "merge_policy": "Sort by canonical_input_index and require exactly one output per canonical task_id::candidate_owner_id.",
    }
    manifest_path = out_dir / f"probetrace_multi_owner_{args.label}_shard_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"Refusing to overwrite shard manifest: {manifest_path.relative_to(ROOT)}")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {manifest_path.relative_to(ROOT)} with {len(manifest_rows)} shards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

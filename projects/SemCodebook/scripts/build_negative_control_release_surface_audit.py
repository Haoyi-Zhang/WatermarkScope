from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT


SCHEMA = "semcodebook_negative_control_release_surface_audit_v1"
DEFAULT_REPLAY_GATE = ARTIFACTS / "negative_control_replay_gate.json"
DEFAULT_OUTPUT = ARTIFACTS / "negative_control_release_surface_audit.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True).encode("utf-8") + b"\n"


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_audit(replay_gate_path: Path = DEFAULT_REPLAY_GATE) -> dict[str, Any]:
    replay_gate = _load_json(replay_gate_path)
    candidate_count = int(replay_gate.get("candidate_count") or 0)
    canonical_closure_blockers = [str(item) for item in _list(replay_gate.get("canonical_closure_blockers")) if str(item)]
    release_surface_blockers = [
        str(item)
        for item in _list(replay_gate.get("release_surface_blockers"))
        if str(item)
    ] or [f"canonical_closure:{item}" for item in canonical_closure_blockers]
    claim_table_blockers = [str(item) for item in _list(replay_gate.get("claim_table_blockers")) if str(item)]
    replay_blockers = [str(item) for item in _list(replay_gate.get("blockers")) if str(item)]

    if candidate_count and not any(item.startswith("canonical_closure:") for item in release_surface_blockers):
        release_surface_blockers.append(f"canonical_negative_control_hits_present:{candidate_count}")
    release_surface_blockers = list(dict.fromkeys(release_surface_blockers))

    support_replay_clean = (
        replay_gate.get("current_detector_negative_control_replay", {})
        if isinstance(replay_gate.get("current_detector_negative_control_replay"), dict)
        else {}
    ).get("current_detector_supports_repair")

    return {
        "schema": SCHEMA,
        "artifact_role": "release_surface_negative_control_audit_not_claim_bearing",
        "claim_bearing": False,
        "source_replay_gate": _rel(replay_gate_path),
        "source_replay_status": replay_gate.get("status"),
        "source_replay_claim_role": replay_gate.get("claim_role"),
        "candidate_count": candidate_count,
        "current_detector_replay_supports_repair": bool(support_replay_clean),
        "canonical_closure_blockers": canonical_closure_blockers,
        "replay_gate_blockers": replay_blockers,
        "claim_table_blockers": claim_table_blockers,
        "release_surface_blockers": release_surface_blockers,
        "release_surface_blocker_count": len(release_surface_blockers),
        "main_claim_admission_allowed": candidate_count == 0 and not release_surface_blockers,
        "status": "passed" if candidate_count == 0 and not release_surface_blockers else "blocked",
        "policy": {
            "old_canonical_negative_hits_must_not_enter_claim": True,
            "current_detector_replay_is_support_only": True,
            "fresh_canonical_rerun_required_before_claim": bool(candidate_count),
            "do_not_delete_hard_or_negative_cases": True,
            "do_not_lower_thresholds": True,
        },
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SemCodebook release-surface audit for negative-control closure.")
    parser.add_argument("--replay-gate", type=Path, default=DEFAULT_REPLAY_GATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_audit(args.replay_gate)
    rendered = _json_bytes(payload)
    if args.check:
        if not args.output.exists() or args.output.read_bytes() != rendered:
            print(f"{args.output} is stale; rerun build_negative_control_release_surface_audit.py", file=sys.stderr)
            return 1
        print(json.dumps({"status": payload["status"], "candidate_count": payload["candidate_count"], "path": str(args.output)}))
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rendered)
    print(json.dumps({"status": payload["status"], "candidate_count": payload["candidate_count"], "path": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

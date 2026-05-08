from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260508"
GENERATED = "artifacts/generated"
INPUT_ROWS = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_rows_20260507.jsonl"
REGISTRY = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_registry_20260505_remote.json"
PROTOCOL = ROOT / f"results/ProbeTrace/{GENERATED}/probetrace_commitment_shortcut_challenge_protocol_v1_{DATE}.json"
CHALLENGE_ROWS = ROOT / f"results/ProbeTrace/{GENERATED}/probetrace_commitment_shortcut_challenge_input_rows_v1_{DATE}.jsonl"
CORRUPTED_REGISTRY = ROOT / f"results/ProbeTrace/{GENERATED}/probetrace_commitment_shortcut_challenge_corrupted_registry_v1_{DATE}.json"
POSTRUN_GATE = ROOT / f"results/ProbeTrace/{GENERATED}/probetrace_commitment_shortcut_challenge_postrun_gate_v1_{DATE}.json"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def corrupted_commitment(owner_id: str, index: int) -> str:
    return sha256_text(f"probetrace-corrupted-commitment-v1::{DATE}::{index}::{owner_id}")


def materialize() -> dict[str, Any]:
    blockers: list[str] = []
    for path in (INPUT_ROWS, REGISTRY):
        if not path.exists():
            blockers.append(f"missing_prerequisite:{path.relative_to(ROOT)}")
    if blockers:
        payload = {
            "schema_version": "probetrace_commitment_shortcut_challenge_protocol_v1",
            "date": DATE,
            "claim_bearing": False,
            "gate_pass": False,
            "execution_allowed": False,
            "blockers": blockers,
        }
        write_json(PROTOCOL, payload)
        return payload

    rows = read_jsonl(INPUT_ROWS)
    positives = [row for row in rows if row.get("control_role") == "true_owner"]
    positives_by_owner_language: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in positives:
        key = (str(row.get("true_owner_id", "")), str(row.get("language", "")))
        positives_by_owner_language.setdefault(key, []).append(row)
    owners = sorted({owner for owner, _language in positives_by_owner_language})
    languages = sorted({language for _owner, language in positives_by_owner_language})
    selected: list[dict[str, Any]] = []
    owner_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()

    def add_row(row: dict[str, Any]) -> None:
        owner = str(row.get("true_owner_id", ""))
        language = str(row.get("language", ""))
        if owner_counts[owner] >= 4 or len(selected) >= 20:
            return
        item = dict(row)
        item["claim_bearing"] = False
        item["not_claim_bearing_reason"] = "commitment_shortcut_challenge_support_only"
        item["challenge_role"] = "true_owner_with_corrupted_candidate_commitment"
        item["expected_challenge_behavior"] = "abstain_or_low_score_because_candidate_commitment_is_mismatched"
        selected.append(item)
        owner_counts[owner] += 1
        language_counts[language] += 1

    # First force owner/language coverage, then fill to 20 without exceeding four rows per owner.
    for language in languages:
        for owner in owners:
            rows_for_cell = positives_by_owner_language.get((owner, language), [])
            if rows_for_cell:
                add_row(rows_for_cell[0])
    for owner in owners:
        for language in languages:
            for row in positives_by_owner_language.get((owner, language), [])[1:]:
                add_row(row)
                if len(selected) >= 20:
                    break
            if len(selected) >= 20:
                break
        if len(selected) >= 20:
            break
    if len(selected) != 20:
        blockers.append(f"challenge_row_count_not_20:{len(selected)}")
    if len(owner_counts) < 5:
        blockers.append("challenge_owner_count_below_5")
    if len(language_counts) < 3:
        blockers.append("challenge_language_count_below_3")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    owner_slots = registry.get("owner_slots", []) if isinstance(registry, dict) else []
    for index, slot in enumerate(owner_slots):
        if not isinstance(slot, dict):
            continue
        owner_id = str(slot.get("owner_slot_id", "")).strip()
        slot["owner_key_commitment_placeholder_sha256"] = corrupted_commitment(owner_id, index)
        slot["owner_key_commitment_status"] = "deliberately_corrupted_for_commitment_shortcut_challenge"
        slot["claim_role"] = "support_only_corrupted_commitment_negative_control"
    registry["artifact_role"] = "support_only_corrupted_commitment_negative_control_registry"
    registry["claim_bearing"] = False
    registry["formal_claim_allowed"] = False
    registry["challenge_policy"] = (
        "The source witness commitment in each input row is left unchanged while candidate owner registry "
        "commitments are deterministically corrupted. A robust attribution protocol should fail closed."
    )

    write_jsonl(CHALLENGE_ROWS, selected)
    write_json(CORRUPTED_REGISTRY, registry)

    output = f"results/ProbeTrace/{GENERATED}/probetrace_commitment_shortcut_challenge_live_results_v1_{DATE}.jsonl"
    progress = f"results/ProbeTrace/{GENERATED}/probetrace_commitment_shortcut_challenge_progress_v1_{DATE}.json"
    command = (
        "python projects/ProbeTrace/scripts/run_multi_owner_deepseek_live.py "
        "--provider deepseek "
        f"--run-id probetrace_commitment_shortcut_challenge_{DATE} "
        f"--input {CHALLENGE_ROWS.relative_to(ROOT).as_posix()} "
        f"--registry {CORRUPTED_REGISTRY.relative_to(ROOT).as_posix()} "
        f"--output {output} "
        f"--progress-output {progress}"
    )
    payload = {
        "schema_version": "probetrace_commitment_shortcut_challenge_protocol_v1",
        "date": DATE,
        "project": "ProbeTrace",
        "claim_bearing": False,
        "gate_pass": not blockers,
        "execution_allowed": not blockers,
        "experiment_role": "support_only_commitment_shortcut_negative_control",
        "provider": "deepseek",
        "provider_mode_required": "live",
        "challenge_input_rows": CHALLENGE_ROWS.relative_to(ROOT).as_posix(),
        "corrupted_registry": CORRUPTED_REGISTRY.relative_to(ROOT).as_posix(),
        "canonical_output": output,
        "progress_output": progress,
        "postrun_gate": POSTRUN_GATE.relative_to(ROOT).as_posix(),
        "minimum_live_records": 20,
        "owner_count": len(owner_counts),
        "language_count": len(language_counts),
        "owner_counts": dict(sorted(owner_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "launch_command_redacted": command,
        "secret_values_recorded": False,
        "main_claim_policy": {
            "support_rows_enter_main_denominator": False,
            "formal_provider_general_claim_allowed": False,
            "formal_multi_owner_claim_upgrade_allowed_by_this_artifact": False,
            "threshold_adjustment_allowed": False,
        },
        "source_artifacts": {
            "input_rows": {
                "path": INPUT_ROWS.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(INPUT_ROWS),
            },
            "registry": {
                "path": REGISTRY.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(REGISTRY),
            },
        },
        "blockers": blockers,
    }
    write_json(PROTOCOL, payload)
    return payload


def main() -> int:
    payload = materialize()
    print(json.dumps({"gate_pass": payload.get("gate_pass"), "output": PROTOCOL.relative_to(ROOT).as_posix(), "blockers": payload.get("blockers", [])}, ensure_ascii=True))
    return 0 if payload.get("gate_pass") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

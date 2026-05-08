from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
REGISTRY = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_registry_20260505_remote.json"
RERUN_MANIFEST = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_multilingual_deepseek_rerun_manifest_20260505_remote.json"
OUT_ROWS = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_rows_{DATE}.jsonl"
OUT_PACKAGE = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_{DATE}.json"
OUT_GATE = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_prerun_gate_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(payload: Any) -> str:
    return sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected object in {path}")
    return payload


def owner_split(owner: dict[str, Any]) -> str:
    return str(owner.get("split", "train_dev"))


def make_prompt(row: dict[str, Any], owner_commitment: str) -> str:
    return (
        "ProbeTrace multi-owner attribution scoring task.\n"
        f"Task: {row['task_id']}\n"
        f"Language: {row['language']}\n"
        f"Candidate owner: {row['candidate_owner_id']}\n"
        f"Control role: {row['control_role']}\n"
        f"Owner commitment: {owner_commitment}\n"
        "Return a JSON object with fields score, owner_id_hat, abstain, and rationale. "
        "Do not reveal or invent owner key material."
    )


def main() -> int:
    registry = load_json(REGISTRY)
    rerun_manifest = load_json(RERUN_MANIFEST)
    owners = registry.get("owner_slots", [])
    if not isinstance(owners, list):
        owners = []
    languages = registry.get("languages", [])
    if not isinstance(languages, list) or not languages:
        languages = ["python", "javascript", "go"]

    rows: list[dict[str, Any]] = []
    task_index = 0
    tasks_per_owner_language = 50
    owner_ids = [str(owner.get("owner_slot_id")) for owner in owners]
    owner_by_id = {str(owner.get("owner_slot_id")): owner for owner in owners}

    def add_row(
        *,
        true_owner_id: str,
        candidate_owner_id: str,
        language: str,
        split: str,
        control_role: str,
        task_no: int,
    ) -> None:
        nonlocal task_index
        owner = owner_by_id[true_owner_id]
        commitment = str(owner.get("owner_key_commitment_placeholder_sha256", ""))
        family = f"multi_owner_{control_role}_{language}"
        task_id = f"probetrace_multi_owner_{language}_{true_owner_id}_{task_no:03d}_{control_role}_{candidate_owner_id}"
        base = {
            "task_id": task_id,
            "source_id": f"probetrace_multi_owner_source_{task_index:05d}",
            "true_owner_id": true_owner_id,
            "candidate_owner_id": candidate_owner_id,
            "candidate_owner_count": len(owner_ids),
            "split": split,
            "owner_heldout": split == "owner_heldout",
            "task_heldout": split == "task_heldout",
            "control_role": control_role,
            "language": language,
            "family": family,
            "provider": "deepseek",
            "score_space": "fresh_multi_owner_candidate_owner_score",
            "threshold_version": "probetrace_multi_owner_threshold_free_rank_v1",
            "claim_bearing": False,
            "not_claim_bearing_reason": "canonical_input_package_not_provider_result",
            "owner_key_material_in_row": False,
            "owner_key_commitment_sha256": commitment,
        }
        prompt = make_prompt(base, commitment)
        base["prompt_hash"] = sha256_bytes(prompt.encode("utf-8"))
        base["task_hash"] = stable_hash({k: base[k] for k in sorted(base) if k != "prompt_hash"})
        base["row_sha256"] = stable_hash(base)
        rows.append(base)
        task_index += 1

    for owner in owners:
        true_owner_id = str(owner.get("owner_slot_id"))
        split = owner_split(owner)
        for language in languages:
            for task_no in range(1, tasks_per_owner_language + 1):
                add_row(
                    true_owner_id=true_owner_id,
                    candidate_owner_id=true_owner_id,
                    language=language,
                    split=split,
                    control_role="true_owner",
                    task_no=task_no,
                )
                for wrong_owner_id in owner_ids:
                    if wrong_owner_id != true_owner_id:
                        add_row(
                            true_owner_id=true_owner_id,
                            candidate_owner_id=wrong_owner_id,
                            language=language,
                            split=split,
                            control_role="wrong_owner",
                            task_no=task_no,
                        )
                for control_role, candidate in [
                    ("null_owner", "null_owner"),
                    ("random_owner", f"random_owner_seeded_{task_no:03d}"),
                    ("same_provider_unwrap", "same_provider_unwrap"),
                ]:
                    add_row(
                        true_owner_id=true_owner_id,
                        candidate_owner_id=candidate,
                        language=language,
                        split=split,
                        control_role=control_role,
                        task_no=task_no,
                    )

    OUT_ROWS.parent.mkdir(parents=True, exist_ok=True)
    OUT_ROWS.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

    role_counts = Counter(row["control_role"] for row in rows)
    split_counts = Counter(row["split"] for row in rows)
    language_counts = Counter(row["language"] for row in rows)
    owner_counts = Counter(row["true_owner_id"] for row in rows if row["control_role"] == "true_owner")
    expected = rerun_manifest.get("target_denominators", {})
    blockers = []
    if len(owner_ids) != int(expected.get("owner_count", 5)):
        blockers.append("owner_count_mismatch")
    if len(languages) != int(expected.get("language_count", 3)):
        blockers.append("language_count_mismatch")
    expected_roles = {
        "true_owner": int(expected.get("positive_records", 750)),
        "wrong_owner": int(expected.get("wrong_owner_negative_records", 3000)),
        "null_owner": int(expected.get("null_owner_negative_records", 750)),
        "random_owner": int(expected.get("random_owner_negative_records", 750)),
        "same_provider_unwrap": int(expected.get("same_provider_unwrap_control_records", 750)),
    }
    for role, count in expected_roles.items():
        if role_counts.get(role, 0) != count:
            blockers.append(f"{role}_count_mismatch:{role_counts.get(role, 0)}!={count}")
    if "owner_heldout" not in split_counts:
        blockers.append("owner_heldout_split_missing")
    if "task_heldout" not in split_counts:
        blockers.append("task_heldout_split_missing")
    if any(owner.get("owner_key_material_in_registry") is not False for owner in owners if isinstance(owner, dict)):
        blockers.append("owner_key_material_present_in_registry")

    package = {
        "schema_version": "probetrace_multi_owner_deepseek_canonical_input_package_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "formal_multi_owner_claim_allowed": False,
        "registry": REGISTRY.relative_to(ROOT).as_posix(),
        "registry_sha256": sha256_file(REGISTRY),
        "rerun_manifest": RERUN_MANIFEST.relative_to(ROOT).as_posix(),
        "rerun_manifest_sha256": sha256_file(RERUN_MANIFEST),
        "input_rows": OUT_ROWS.relative_to(ROOT).as_posix(),
        "input_rows_sha256": sha256_file(OUT_ROWS),
        "row_count": len(rows),
        "owner_count": len(owner_ids),
        "language_count": len(languages),
        "control_role_counts": dict(sorted(role_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "positive_rows_per_owner": dict(sorted(owner_counts.items())),
        "threshold_policy": "threshold-free rank/AUC evidence; any scalar thresholds must be frozen before provider execution",
        "promotion_policy": "This package is executable input only. It cannot promote a multi-owner claim without fresh provider outputs, transcript hashes, score vectors, and postrun audit.",
        "blockers": blockers,
        "gate_pass": not blockers,
    }
    OUT_PACKAGE.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gate = {
        "schema_version": "probetrace_multi_owner_deepseek_prerun_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not blockers,
        "formal_multi_owner_claim_allowed": False,
        "input_package": OUT_PACKAGE.relative_to(ROOT).as_posix(),
        "input_rows": OUT_ROWS.relative_to(ROOT).as_posix(),
        "required_postrun_artifacts": rerun_manifest.get("required_live_outputs_before_any_new_claim", []),
        "target_denominators": expected,
        "blockers": blockers,
        "allowed_next_step": "DeepSeek provider execution may start only as a fresh canonical run that writes raw/structured hashes and non-claim-bearing receipts until postrun promotion passes.",
    }
    OUT_GATE.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("[OK] Wrote ProbeTrace multi-owner canonical input package.")
    print(f"[OK] Rows: {len(rows)}; roles: {dict(sorted(role_counts.items()))}")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())

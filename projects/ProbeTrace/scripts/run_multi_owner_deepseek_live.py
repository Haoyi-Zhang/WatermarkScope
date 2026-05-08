from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = ROOT / "projects" / "ProbeTrace"
DEFAULT_INPUT = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_rows_20260507.jsonl"
DEFAULT_OUTPUT = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_score_vectors_20260507.jsonl"
DEFAULT_PROGRESS = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_progress_20260507.json"
DEFAULT_REGISTRY = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_registry_20260505_remote.json"
DEFAULT_ENV_FILE = Path("/root/.codemark_secrets/deepseek.env")
DEFAULT_PROVIDER_CONFIG = ROOT / "projects" / "CodeDye" / "configs" / "providers.example.json"
OWNER_ID_PATTERN = re.compile(r"\bowner_[a-zA-Z0-9_-]+\b")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ProbeTrace five-owner DeepSeek live score vectors.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT.relative_to(ROOT)))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    parser.add_argument("--progress-output", default=str(DEFAULT_PROGRESS.relative_to(ROOT)))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY.relative_to(ROOT)))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--provider-config", default=str(DEFAULT_PROVIDER_CONFIG.relative_to(ROOT)))
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--run-id", default="probetrace_multi_owner_20260507")
    parser.add_argument("--max-records", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--require-live", action="store_true", default=True)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--sleep-s", type=float, default=0.0)
    parser.add_argument("--claim-bearing-canonical", action="store_true")
    parser.add_argument("--canonical-shard", action="store_true")
    parser.add_argument("--canonical-total", type=int, default=6000)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(payload: Any) -> str:
    return sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def load_env_file(path: Path) -> dict[str, Any]:
    loaded: list[str] = []
    if not path.exists():
        return {"env_file": str(path), "env_file_state": "missing", "loaded_env_keys": []}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("export "):
            text = text[len("export ") :].strip()
        if "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key.startswith("DEEPSEEK_") and value:
            os.environ[key] = value
            loaded.append(key)
    return {
        "env_file": str(path),
        "env_file_state": "loaded",
        "loaded_env_keys": sorted(set(loaded)),
        "secret_values_serialized": False,
    }


def provider_spec(config_path: Path, provider: str) -> dict[str, Any]:
    payload = load_json(config_path)
    if not isinstance(payload, dict) or provider not in payload:
        raise SystemExit(f"provider_config_missing:{provider}")
    spec = payload[provider]
    if not isinstance(spec, dict):
        raise SystemExit(f"provider_config_invalid:{provider}")
    return spec


def configured_key(env_name: str) -> str:
    value = os.getenv(env_name, "").strip()
    lowered = value.lower()
    if not value or "placeholder" in lowered or "dummy" in lowered or "replace" in lowered:
        return ""
    return value


def provider_summary(spec: dict[str, Any]) -> dict[str, Any]:
    env_name = str(spec.get("api_key_env", "DEEPSEEK_API_KEY"))
    key = configured_key(env_name)
    return {
        "provider": "deepseek",
        "model_name": str(spec.get("model_name", "deepseek-chat")),
        "base_url_redacted": "deepseek_openai_compatible_endpoint",
        "provider_kind": str(spec.get("provider_kind", "openai_compatible")),
        "api_key_env": env_name,
        "api_key_state": "configured" if key else "missing_or_placeholder",
        "secret_values_serialized": False,
    }


def load_owner_commitments(path: Path) -> dict[str, str]:
    payload = load_json(path)
    owners = payload.get("owner_slots", []) if isinstance(payload, dict) else []
    output: dict[str, str] = {}
    if isinstance(owners, list):
        for owner in owners:
            if not isinstance(owner, dict):
                continue
            owner_id = str(owner.get("owner_slot_id", "")).strip()
            commitment = str(owner.get("owner_key_commitment_placeholder_sha256", "")).strip()
            if owner_id and commitment:
                output[owner_id] = commitment
    return output


def candidate_commitment(row: dict[str, Any], owner_commitments: dict[str, str]) -> str:
    candidate = str(row["candidate_owner_id"]).strip()
    if candidate in owner_commitments:
        return owner_commitments[candidate]
    if candidate.startswith("random_owner"):
        return sha256_text(f"random-owner-control::{candidate}::{row['task_hash']}")
    if candidate == "same_provider_unwrap":
        return sha256_text(f"same-provider-unwrapped-control::{row['task_hash']}")
    if candidate == "null_owner":
        return "null-owner-no-commitment"
    return sha256_text(f"unknown-candidate::{candidate}::{row['task_hash']}")


def build_prompt(row: dict[str, Any], owner_commitments: dict[str, str]) -> str:
    candidate = "candidate_" + sha256_text(str(row["candidate_owner_id"]))[:12]
    source_commitment = str(row["owner_key_commitment_sha256"])
    candidate_owner_commitment = candidate_commitment(row, owner_commitments)
    task_token = str(row["task_hash"])[:24]
    source_token = str(row["row_sha256"])[:24]
    return (
        "ProbeTrace active-owner attribution score task.\n"
        "You are auditing whether an output should be attributed to one candidate owner commitment.\n"
        "Use only the source witness commitment, candidate owner commitment, task binding, "
        "source hash binding, and witness consistency cues below.\n"
        "Do not infer from role names or hidden labels. Do not output secret key material.\n\n"
        f"Candidate alias: {candidate}\n"
        f"Source witness commitment: {source_commitment}\n"
        f"Candidate owner commitment: {candidate_owner_commitment}\n"
        f"Language: {row['language']}\n"
        "Attribution family: multi_owner_active_witness\n"
        f"Task binding token: {task_token}\n"
        f"Source binding token: {source_token}\n"
        f"Threshold policy: {row['threshold_version']}\n\n"
        "Return only compact JSON with keys: score, owner_id_hat, abstain, rationale.\n"
        "score must be a number in [0,1]. owner_id_hat must be the candidate alias or null. "
        "abstain must be boolean."
    )


def openai_compatible_call(prompt: str, spec: dict[str, Any], *, timeout_s: int, max_retries: int) -> tuple[str, dict[str, Any], float]:
    api_key_env = str(spec.get("api_key_env", "DEEPSEEK_API_KEY"))
    api_key = configured_key(api_key_env)
    if not api_key:
        raise RuntimeError(f"missing_or_placeholder_api_key:{api_key_env}")
    base_url = str(spec.get("base_url", "https://api.deepseek.com/v1")).rstrip("/")
    payload = {
        "model": str(spec.get("model_name", "deepseek-chat")),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict JSON scoring service for attribution evidence. "
                    "Return JSON only. Do not include Markdown or prose outside JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 160,
    }
    request = urllib.request.Request(
        url=f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    started = time.time()
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = str(body["choices"][0]["message"]["content"])
            return content, body, (time.time() - started) * 1000.0
        except (TimeoutError, socket.timeout, urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(min(0.5 * (2**attempt), 4.0))
    raise RuntimeError(f"provider_request_failed:{last_error}")


def parse_model_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        payload = json.loads(match.group(0)) if match else {}
    if not isinstance(payload, dict):
        payload = {}
    return payload


def clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def normalize_owner_hat(value: Any, candidate_owner_id: str, provider_visible_candidate_alias: str) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "abstain", "unknown"}:
        return ""
    if text in {candidate_owner_id, provider_visible_candidate_alias}:
        return candidate_owner_id
    match = OWNER_ID_PATTERN.search(text)
    return match.group(0) if match else text[:64]


def build_record(
    row: dict[str, Any],
    *,
    prompt: str,
    owner_commitments: dict[str, str],
    raw_text: str,
    raw_body: dict[str, Any],
    latency_ms: float,
    provider: str,
    model_name: str,
    run_id: str,
    canonical_claim: bool,
) -> dict[str, Any]:
    parsed = parse_model_json(raw_text)
    score = clamp_score(parsed.get("score"))
    candidate_owner_id = str(row["candidate_owner_id"])
    provider_visible_candidate_alias = "candidate_" + sha256_text(candidate_owner_id)[:12]
    candidate_owner_commitment = candidate_commitment(row, owner_commitments)
    owner_id_hat = normalize_owner_hat(parsed.get("owner_id_hat"), candidate_owner_id, provider_visible_candidate_alias)
    abstain = bool(parsed.get("abstain", False)) or not owner_id_hat
    is_positive = str(row.get("control_role")) in {"true_owner", "positive"}
    false_attribution = (not is_positive) and owner_id_hat == candidate_owner_id and not abstain
    best_wrong_owner_id = ""
    best_wrong_owner_score = 0.0
    if not is_positive:
        best_wrong_owner_id = candidate_owner_id
        best_wrong_owner_score = score
    signed_owner_margin = score if is_positive else -score
    raw_payload_hash = sha256_json(raw_body)
    structured = {
        "parsed": parsed,
        "score": score,
        "owner_id_hat": owner_id_hat,
        "abstain": abstain,
        "latency_ms": round(latency_ms, 3),
    }
    output_hash = sha256_json({"raw_text": raw_text, "structured": structured})
    record = {
        **row,
        "schema_version": "probetrace_multi_owner_deepseek_live_score_vector_v1",
        "project": "ProbeTrace",
        "run_id": run_id,
        "provider": provider,
        "provider_mode_resolved": "live",
        "provider_or_backbone": model_name,
        "model_name": model_name,
        "score": score,
        "score_space": "deepseek_live_candidate_owner_json_score",
        "owner_id_hat": owner_id_hat,
        "false_attribution": false_attribution,
        "signed_owner_margin": signed_owner_margin,
        "best_wrong_owner_id": best_wrong_owner_id,
        "best_wrong_owner_score": best_wrong_owner_score,
        "abstain": abstain,
        "provider_visible_candidate_alias": provider_visible_candidate_alias,
        "rationale_hash": sha256_text(str(parsed.get("rationale", ""))),
        "source_witness_commitment_hash": str(row["owner_key_commitment_sha256"]),
        "candidate_owner_commitment_hash": candidate_owner_commitment,
        "commitment_match": str(row["owner_key_commitment_sha256"]) == candidate_owner_commitment,
        "raw_provider_text_hash": sha256_text(raw_text),
        "raw_provider_transcript_hash": raw_payload_hash,
        "raw_payload_hash": raw_payload_hash,
        "structured_payload_hash": sha256_json(structured),
        "source_record_hash": str(row["row_sha256"]),
        "output_record_sha256": output_hash,
        "prompt_hash": sha256_text(prompt),
        "latency_ms": round(latency_ms, 3),
        "claim_bearing": canonical_claim,
        "claim_boundary": (
        "Claim-bearing only for complete 6000-row DeepSeek live score-vector run or deterministic canonical shard admitted by merge/postrun gate."
            if canonical_claim
            else "Non-claim-bearing health/partial provider run."
        ),
        "control_role_hidden_from_provider": True,
        "true_owner_id_hidden_from_provider": True,
    }
    record["record_hash"] = sha256_json({k: v for k, v in record.items() if k != "record_hash"})
    return record


def completed_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys = set()
    for row in read_jsonl(path):
        keys.add(str(row.get("task_id", "")) + "::" + str(row.get("candidate_owner_id", "")))
    return keys


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    role_counts: dict[str, int] = defaultdict(int)
    owner_counts: dict[str, int] = defaultdict(int)
    language_counts: dict[str, int] = defaultdict(int)
    claim_rows = 0
    for row in rows:
        role_counts[str(row.get("control_role", ""))] += 1
        owner_counts[str(row.get("true_owner_id", ""))] += 1
        language_counts[str(row.get("language", ""))] += 1
        claim_rows += 1 if row.get("claim_bearing") is True else 0
    return {
        "row_count": len(rows),
        "claim_bearing_rows": claim_rows,
        "control_role_counts": dict(sorted(role_counts.items())),
        "owner_counts": dict(sorted(owner_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
    }


def main() -> int:
    args = parse_args()
    env_state = load_env_file(Path(args.env_file))
    input_path = ROOT / args.input
    output_path = ROOT / args.output
    progress_path = ROOT / args.progress_output if str(args.progress_output).strip() else None
    registry_path = ROOT / args.registry
    config_path = ROOT / args.provider_config
    rows = read_jsonl(input_path)
    owner_commitments = load_owner_commitments(registry_path)
    expected_total = len(rows)
    run_rows = rows[: args.max_records] if args.max_records > 0 else rows
    canonical_claim = bool(
        args.claim_bearing_canonical
        and args.max_records == 0
        and (len(run_rows) == 6000 or (args.canonical_shard and args.canonical_total == 6000 and len(run_rows) > 0))
    )
    if args.claim_bearing_canonical and not canonical_claim:
        raise SystemExit("claim_bearing_canonical_requires_complete_6000_row_run_or_declared_canonical_shard")
    spec = provider_spec(config_path, args.provider)
    provider_meta = provider_summary(spec)
    if args.require_live and provider_meta["api_key_state"] != "configured":
        raise SystemExit(f"provider_resolved_not_live:{provider_meta['api_key_state']}")
    if output_path.exists() and not args.resume:
        raise SystemExit(f"output_exists_use_resume_or_new_path:{output_path}")
    done = completed_keys(output_path) if args.resume else set()
    started = time.time()
    processed_records: list[dict[str, Any]] = read_jsonl(output_path) if output_path.exists() else []
    for index, row in enumerate(run_rows, start=1):
        key = str(row.get("task_id", "")) + "::" + str(row.get("candidate_owner_id", ""))
        if key in done:
            continue
        prompt = build_prompt(row, owner_commitments)
        raw_text, raw_body, latency_ms = openai_compatible_call(
            prompt,
            spec,
            timeout_s=args.timeout_s,
            max_retries=args.max_retries,
        )
        record = build_record(
            row,
            prompt=prompt,
            owner_commitments=owner_commitments,
            raw_text=raw_text,
            raw_body=raw_body,
            latency_ms=latency_ms,
            provider=args.provider,
            model_name=str(spec.get("model_name", "deepseek-chat")),
            run_id=args.run_id,
            canonical_claim=canonical_claim,
        )
        append_jsonl(output_path, record)
        processed_records.append(record)
        if progress_path is not None:
            write_json(
                progress_path,
                {
                    "schema_version": "probetrace_multi_owner_deepseek_live_progress_v1",
                    "status": "running",
                    "run_id": args.run_id,
                    "completed": len(processed_records),
                    "total": len(run_rows),
                    "input_total": expected_total,
                    "claim_bearing": canonical_claim,
                    "current_task_id": row.get("task_id"),
                    "current_candidate_owner_id": row.get("candidate_owner_id"),
                    "provider": provider_meta,
                    "env_state": env_state,
                    "elapsed_seconds": round(time.time() - started, 3),
                },
            )
        if args.sleep_s > 0:
            time.sleep(args.sleep_s)
    if progress_path is not None:
        final_summary = summarize(processed_records)
        write_json(
            progress_path,
            {
                "schema_version": "probetrace_multi_owner_deepseek_live_progress_v1",
                "status": "completed",
                "run_id": args.run_id,
                "completed": len(processed_records),
                "total": len(run_rows),
                "input_total": expected_total,
                "claim_bearing": canonical_claim,
                "output": output_path.relative_to(ROOT).as_posix(),
                "summary": final_summary,
                "provider": provider_meta,
                "env_state": env_state,
                "elapsed_seconds": round(time.time() - started, 3),
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

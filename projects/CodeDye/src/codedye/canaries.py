from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass
from pathlib import Path

from .benchmarks import (
    load_code_dyebench_tasks,
    load_code_dyebench_spec,
    task_canary_pack_id,
    task_canary_split,
    task_chronology_split,
    task_hidden_test_family,
    task_metadata,
    task_operator_slice,
    task_release_window,
    task_review_status,
    task_target_family,
)
from .protocol import BenchmarkTask
from .reranker import observe_family


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class SemanticCanary:
    token: str
    kind: str
    normalized: str
    protected_asset_id: str
    chronology_tag: str
    chronology_split: str
    release_window: str
    subset: str
    target_family: str
    review_status: str
    canary_pack_id: str
    hidden_test_family: str


@dataclass(frozen=True, slots=True)
class CanaryEvidenceReport:
    coverage: float
    evidence: tuple[str, ...]
    output_visible_evidence: tuple[str, ...]
    diagnostic_evidence: tuple[str, ...]
    prompt_context_evidence: tuple[str, ...]
    direct_output_visible_canary_count: int
    semantic_output_visible_canary_count: int
    hidden_diagnostic_evidence_count: int

    @property
    def output_visible_canary_evidence_count(self) -> int:
        return len(self.output_visible_evidence)

    @property
    def admissible_output_visible_canary_evidence_count(self) -> int:
        return len(self.output_visible_evidence)

    @property
    def diagnostic_evidence_count(self) -> int:
        return len(self.diagnostic_evidence)

    @property
    def hidden_output_visible_canary_count(self) -> int:
        return self.hidden_diagnostic_evidence_count

    @property
    def hidden_test_family_diagnostic_only(self) -> bool:
        return self.hidden_diagnostic_evidence_count > 0


def _split_tokens(raw: str) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(item for item in (part.strip() for part in raw.split("|")) if item)


def compile_task_canaries(task: BenchmarkTask) -> tuple[SemanticCanary, ...]:
    metadata = task_metadata(task)
    protected_asset_id = metadata.get("protected_asset_id", task.task_id)
    chronology_tag = metadata.get("chronology_tag", "")
    chronology_split = task_chronology_split(task)
    release_window = task_release_window(task)
    target_family = task_target_family(task)
    review_status = task_review_status(task)
    canary_pack_id = task_canary_pack_id(task)
    hidden_test_family = task_hidden_test_family(task)
    default_kind = task_canary_split(task)
    tokens = _split_tokens(metadata.get("canaries", ""))
    canaries: list[SemanticCanary] = []
    for token in tokens:
        kind = default_kind
        if token.endswith("_pack"):
            kind = "family_pack"
        elif token.startswith("chronology_marker_"):
            kind = "chronology_marker"
        elif token.endswith("_stability"):
            kind = "rewrite_marker"
        elif token.startswith("hidden_test_marker_"):
            kind = "hidden_test_family"
        elif default_kind == "semantic_pack":
            kind = "semantic_pack"
        canaries.append(
            SemanticCanary(
                token=token,
                kind=kind,
                normalized=token.replace("_", " ").lower(),
                protected_asset_id=protected_asset_id,
                chronology_tag=chronology_tag,
                chronology_split=chronology_split,
                release_window=release_window,
                subset=task.subset,
                target_family=target_family,
                review_status=review_status,
                canary_pack_id=canary_pack_id,
                hidden_test_family=hidden_test_family,
            )
        )
    return tuple(canaries)


def _parse_python(code: str) -> ast.AST | None:
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def _comment_free_code_text(code: str) -> str:
    try:
        stream = io.StringIO(code)
        tokens = [
            (token.type, token.string)
            for token in tokenize.generate_tokens(stream.readline)
            if token.type != tokenize.COMMENT
        ]
        return tokenize.untokenize(tokens).lower()
    except (tokenize.TokenError, IndentationError):
        return code.lower()


def _node_text(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _function_first_guard_return(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.body:
            first_stmt = node.body[0]
            if isinstance(first_stmt, ast.If) and any(isinstance(item, ast.Return) for item in first_stmt.body):
                return True
    return False


def _has_call_attr(tree: ast.AST, attr: str) -> bool:
    return any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == attr
        for node in ast.walk(tree)
    )


def _has_import(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == name for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom) and node.module == name:
            return True
    return False


def _has_list_comp(tree: ast.AST) -> bool:
    return any(isinstance(node, ast.ListComp) for node in ast.walk(tree))


def _has_dict_fromkeys(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "dict"
        and node.func.attr == "fromkeys"
        for node in ast.walk(tree)
    )


def _has_nested_loops(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.For) and any(isinstance(child, ast.For) for child in ast.walk(node) if child is not node)
        for node in ast.walk(tree)
    )


def _has_enumerate_loop(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.For)
        and "enumerate(" in _node_text(node.iter)
        for node in ast.walk(tree)
    )


def _has_index_product_accumulator(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add) and isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Mult):
            return True
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Add):
            left = _node_text(node.value.left)
            right = _node_text(node.value.right)
            if "*" in left or "*" in right:
                return True
    return False


def _has_split_and_strip(tree: ast.AST) -> bool:
    return _has_call_attr(tree, "split") and _has_call_attr(tree, "strip")


def _has_nonempty_filter(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ListComp):
            if node.generators and any(generator.ifs for generator in node.generators):
                return True
    return False


def _has_get_default(tree: ast.AST, *, key_literal: str | None = None) -> bool:
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"):
            continue
        if len(node.args) < 2:
            continue
        if key_literal is None:
            return True
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and first_arg.value == key_literal:
            return True
    return False


def _has_named_accumulator(tree: ast.AST) -> bool:
    interesting_names = {"tmp", "buffer", "scratch", "cache", "result", "total"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.lower() in interesting_names:
                    return True
    return False


def _has_reverse_words_pattern(tree: ast.AST) -> bool:
    has_join = _has_call_attr(tree, "join")
    has_split = _has_call_attr(tree, "split")
    text = _node_text(tree)
    return has_join and has_split and ("reversed(" in text or "[::-1]" in text)


def _has_pair_search_pattern(tree: ast.AST) -> bool:
    has_tuple_append = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append"
        and node.args
        and isinstance(node.args[0], ast.Tuple)
        for node in ast.walk(tree)
    )
    has_nested_loops = _has_nested_loops(tree)
    return has_nested_loops and has_tuple_append


def _has_normpath_join(tree: ast.AST) -> bool:
    text = _node_text(tree)
    return "os.path.join" in text and "os.path.normpath" in text


def _has_regex_lower_tokens(tree: ast.AST) -> bool:
    text = _node_text(tree)
    return ("re.findall" in text or _has_import(tree, "re")) and ".lower()" in text and "[a-z]+" in text.lower()


def _has_matrix_diagonal_pattern(tree: ast.AST) -> bool:
    text = _node_text(tree)
    return "range(" in text and "min(" in text and "[index][index]" in text


def _has_json_projection_pattern(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ListComp) and node.generators:
            generator = node.generators[0]
            if generator.ifs and "'value'" in _node_text(node) and "[\"value\"]" in _node_text(node).replace("'", "\""):
                return True
    return False


def _has_positive_integer_filter(tree: ast.AST) -> bool:
    text = _node_text(tree)
    return "isinstance(" in text and "int" in text and ">=" in text


def _semantic_token_hits(task: BenchmarkTask, tree: ast.AST | None, code_text: str) -> tuple[str, ...]:
    if tree is None:
        return ()
    hits: list[str] = []
    observation = observe_family(code_text, task_target_family(task))
    family_match = observation.observed_bit is not None and observation.confidence >= 0.8
    task_id = task.task_id
    text = _node_text(tree).lower()

    if task_id == "fresh_norm_list_guard":
        if family_match or _function_first_guard_return(tree):
            hits.append("guard_first_pack")
        if _has_positive_integer_filter(tree) and _has_list_comp(tree):
            hits.append("normalized_integer_list")
    elif task_id == "fresh_lookup_default":
        if family_match or _has_get_default(tree):
            hits.append("lookup_idiom_pack")
        if _has_get_default(tree):
            hits.append("default_fallback")
    elif task_id == "chronology_weighted_sum":
        if _has_enumerate_loop(tree) and _has_index_product_accumulator(tree):
            hits.extend(("weighted_sum_pack", "chronology_marker_alpha"))
    elif task_id == "chronology_csv_helper":
        if _has_split_and_strip(tree):
            hits.append("helper_split_pack")
        if _has_split_and_strip(tree) and _has_nonempty_filter(tree):
            hits.append("chronology_marker_beta")
    elif task_id == "semantic_deduplicate_stable":
        if "dict.fromkeys(" in text or ("sorted(" in text and "set(" in text and ".lower(" in text and "split(" in text):
            hits.extend(("stable_output_policy", "container_choice_pack"))
    elif task_id == "semantic_merge_counters":
        if family_match or _has_named_accumulator(tree) or "running +=" in text or "total +=" in text:
            hits.append("temporary_variable_pack")
        if _has_nested_loops(tree) and _has_get_default(tree):
            hits.append("nested_counter_merge")
    elif task_id == "cross_language_reverse_words":
        if "split(" in text and "join(" in text and "reversed(" in text:
            hits.extend(("cross_language_pack", "reverse_word_variant"))
    elif task_id == "cross_language_title_case_words":
        if "split(" in text and "join(" in text and ".capitalize(" in text:
            hits.extend(("title_case_pack", "cross_language_title_marker"))
    elif task_id == "cross_language_join_nonempty":
        if "join(" in text and "if" in text and ("part" in text or "value" in text or "item" in text):
            hits.extend(("join_nonempty_pack", "cross_language_join_marker"))
    elif task_id == "cross_language_filter_truthy":
        if "if value" in text or "if item" in text or "if part" in text or "if segment" in text:
            hits.extend(("filter_truthy_pack", "cross_language_truthy_marker"))
    elif task_id == "cross_language_unique_sorted":
        if "sorted(" in text and "set(" in text and ".lower(" in text and "split(" in text:
            hits.extend(("unique_sorted_pack", "cross_language_unique_marker"))
    elif task_id == "cross_language_segment_lengths":
        if "split('-')" in text and "len(segment)" in text:
            hits.extend(("segment_lengths_pack", "cross_language_length_marker"))
    elif task_id == "cross_language_digit_mask":
        if "isdigit(" in text and "#" in text and "join(" in text:
            hits.extend(("digit_mask_pack", "cross_language_digit_marker"))
    elif task_id == "cross_language_reverse_mapping":
        if "items(" in text and ("for (key, value) in mapping.items()" in text or "for key, value in mapping.items()" in text or "return {value: key for" in text):
            hits.extend(("reverse_mapping_pack", "cross_language_reverse_marker"))
    elif task_id == "cross_language_window_pairs":
        if "range(len(values) - 1)" in text and "values[index], values[index + 1]" in text:
            hits.extend(("window_pairs_pack", "cross_language_pairs_marker"))
    elif task_id == "rewrite_preserving_pairs":
        if _has_pair_search_pattern(tree):
            hits.extend(("pair_search_pack", "rewrite_stability"))
    elif task_id == "rewrite_preserving_chunked_sum":
        if "range(0, len(values), size)" in text and "sum(values[index:index + size])" in text:
            hits.extend(("chunked_sum_pack", "rewrite_chunk_marker"))
    elif task_id == "rewrite_preserving_prefix_scan":
        if "running += value" in text and "append(running)" in text:
            hits.extend(("prefix_scan_pack", "rewrite_prefix_marker"))
    elif task_id == "rewrite_preserving_range_merge":
        if "sorted(ranges)" in text and "merged[-1][1]" in text and "max(" in text:
            hits.extend(("merge_ranges_pack", "rewrite_range_marker"))
    elif task_id == "rewrite_preserving_nested_lookup":
        if "for key in path" in text and "not isinstance(current, dict)" in text and "key not in current" in text:
            hits.extend(("nested_lookup_pack", "rewrite_lookup_marker"))
    elif task_id == "rewrite_preserving_trim_suffixes":
        if "endswith(suffix)" in text and "[:-len(suffix)]" in text:
            hits.extend(("trim_suffix_pack", "rewrite_suffix_marker"))
    elif task_id == "rewrite_preserving_even_positions":
        if "enumerate(values)" in text and "% 2 == 0" in text:
            hits.extend(("even_positions_pack", "rewrite_even_marker"))
    elif task_id == "rewrite_preserving_record_sort":
        if "sorted(records" in text and "key=lambda" in text:
            hits.extend(("record_sort_pack", "rewrite_sort_marker"))
    elif task_id == "rewrite_preserving_difference_pairs":
        if "abs(left - right) == target" in text and "for left in values" in text and "for right in values" in text:
            hits.extend(("difference_pairs_pack", "rewrite_difference_marker"))
    elif task_id == "rewrite_preserving_common_prefix":
        if "startswith(prefix)" in text and "prefix = prefix[:-1]" in text:
            hits.extend(("common_prefix_pack", "rewrite_prefix_common_marker"))
    elif task_id == "budget_sensitive_path_join":
        if _has_normpath_join(tree):
            hits.extend(("query_budget_pack", "path_fragment_pack"))
    elif task_id == "latency_sensitive_counter_sum":
        if _has_get_default(tree, key_literal="value"):
            hits.extend(("latency_budget_pack", "counter_rollup"))
    elif task_id == "holdout_regex_tokens":
        if _has_regex_lower_tokens(tree):
            hits.extend(("regex_token_pack", "hidden_test_marker_regex"))
    elif task_id == "holdout_matrix_diagonal":
        if _has_matrix_diagonal_pattern(tree):
            hits.extend(("matrix_diagonal_pack", "chronology_marker_gamma"))
    elif task_id == "holdout_jsonl_projection":
        if "'value' in record" in text and "record['value']" in text:
            hits.extend(("json_projection_pack", "cross_language_projection"))

    unique_hits: list[str] = []
    seen: set[str] = set()
    for token in hits:
        if token not in seen:
            unique_hits.append(token)
            seen.add(token)
    return tuple(unique_hits)


def _hidden_family_text_variants(hidden_test_family: str) -> tuple[str, ...]:
    raw = hidden_test_family.strip().lower()
    if not raw:
        return ()
    variants = {
        raw,
        raw.replace("_", " "),
        raw.replace("_", "-"),
        raw.replace("-", " "),
        raw.replace("-", "_"),
    }
    return tuple(sorted(item for item in variants if item))


def measure_canary_evidence(
    task: BenchmarkTask,
    code: str,
    *,
    observed_prompt: str | None = None,
) -> CanaryEvidenceReport:
    metadata = task_metadata(task)
    prompt_text = (observed_prompt or "").lower()
    code_text = _comment_free_code_text(code)
    tree = _parse_python(code)
    evidence: list[str] = []
    output_visible: list[str] = []
    diagnostic: list[str] = []
    prompt_context: list[str] = []
    hit_tokens: set[str] = set()
    direct_count = 0
    semantic_count = 0
    hidden_count = 0
    canaries = compile_task_canaries(task)
    for canary in canaries:
        # Direct canary evidence must come from the candidate output/code.
        # The prompt can carry chronology context, but prompt-visible canaries are
        # never counted as contamination evidence by themselves.
        token_hit = canary.token.lower() in code_text
        normalized_hit = canary.normalized in code_text
        if token_hit or normalized_hit:
            hit_tokens.add(canary.token)
            item = f"canary_hit:{canary.kind}:{canary.token}"
            evidence.append(item)
            output_visible.append(item)
            direct_count += 1
    semantic_hits = _semantic_token_hits(task, tree, code)
    if semantic_hits:
        semantic_lookup = {canary.token: canary for canary in canaries}
        for token in semantic_hits:
            canary = semantic_lookup.get(token)
            if canary is None:
                continue
            if token not in hit_tokens:
                hit_tokens.add(token)
                item = f"semantic_canary_hit:{canary.kind}:{canary.token}"
                evidence.append(item)
                output_visible.append(item)
                semantic_count += 1
    chronology_tag = metadata.get("chronology_tag", "")
    if chronology_tag and chronology_tag.lower() in prompt_text:
        item = f"chronology_prompt_hit:{chronology_tag}"
        evidence.append(item)
        prompt_context.append(item)
    hidden_test_family = task_hidden_test_family(task)
    if hidden_test_family and any(variant in code_text for variant in _hidden_family_text_variants(hidden_test_family)):
        item = f"hidden_test_family_hint:{hidden_test_family}"
        evidence.append(item)
        diagnostic.append(item)
        hidden_count += 1
    coverage = len(hit_tokens) / len(canaries) if canaries else 0.0
    return CanaryEvidenceReport(
        coverage=round(coverage, 4),
        evidence=tuple(evidence),
        output_visible_evidence=tuple(output_visible),
        diagnostic_evidence=tuple(diagnostic),
        prompt_context_evidence=tuple(prompt_context),
        direct_output_visible_canary_count=direct_count,
        semantic_output_visible_canary_count=semantic_count,
        hidden_diagnostic_evidence_count=hidden_count,
    )


def measure_canary_coverage(
    task: BenchmarkTask,
    code: str,
    *,
    observed_prompt: str | None = None,
) -> tuple[float, tuple[str, ...]]:
    report = measure_canary_evidence(task, code, observed_prompt=observed_prompt)
    return report.coverage, report.evidence


def summarize_local_benchmark_inventory(root_or_tasks: str | Path | tuple[BenchmarkTask, ...]) -> dict[str, object]:
    root = DEFAULT_REPO_ROOT if isinstance(root_or_tasks, tuple) else Path(root_or_tasks)
    tasks = root_or_tasks if isinstance(root_or_tasks, tuple) else load_code_dyebench_tasks(root_or_tasks)
    spec = load_code_dyebench_spec(root) if root is not None else {}
    subset_counts: dict[str, int] = {}
    subset_ready_counts: dict[str, int] = {}
    subset_pending_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    review_status_counts: dict[str, int] = {}
    chronology_tags: set[str] = set()
    chronology_split_counts: dict[str, int] = {}
    release_window_counts: dict[str, int] = {}
    protected_assets: set[str] = set()
    canary_kind_counts: dict[str, int] = {}
    canary_split_counts: dict[str, int] = {}
    canary_pack_counts: dict[str, int] = {}
    hidden_test_family_counts: dict[str, int] = {}
    operator_slice_counts: dict[str, int] = {}
    target_families: dict[str, int] = {}
    for task in tasks:
        subset_counts[task.subset] = subset_counts.get(task.subset, 0) + 1
        language_counts[task.language] = language_counts.get(task.language, 0) + 1
        review_status = task_review_status(task)
        review_status_counts[review_status] = review_status_counts.get(review_status, 0) + 1
        if review_status == "ready":
            subset_ready_counts[task.subset] = subset_ready_counts.get(task.subset, 0) + 1
        else:
            subset_pending_counts[task.subset] = subset_pending_counts.get(task.subset, 0) + 1
        metadata = task_metadata(task)
        chronology_tag = metadata.get("chronology_tag", "")
        if chronology_tag:
            chronology_tags.add(chronology_tag)
        chronology_split = task_chronology_split(task)
        chronology_split_counts[chronology_split] = chronology_split_counts.get(chronology_split, 0) + 1
        release_window = task_release_window(task)
        release_window_counts[release_window] = release_window_counts.get(release_window, 0) + 1
        canary_split = task_canary_split(task)
        canary_split_counts[canary_split] = canary_split_counts.get(canary_split, 0) + 1
        canary_pack_id = task_canary_pack_id(task)
        canary_pack_counts[canary_pack_id] = canary_pack_counts.get(canary_pack_id, 0) + 1
        hidden_test_family = task_hidden_test_family(task)
        hidden_test_family_counts[hidden_test_family] = hidden_test_family_counts.get(hidden_test_family, 0) + 1
        operator_slice = task_operator_slice(task)
        if operator_slice:
            operator_slice_counts[operator_slice] = operator_slice_counts.get(operator_slice, 0) + 1
        protected_assets.add(metadata.get("protected_asset_id", task.task_id))
        for canary in compile_task_canaries(task):
            canary_kind_counts[canary.kind] = canary_kind_counts.get(canary.kind, 0) + 1
            if canary.target_family:
                target_families[canary.target_family] = target_families.get(canary.target_family, 0) + 1
    frozen_family_target_counts = {
        str(key): int(value) for key, value in dict(spec.get("frozen_family_target_counts", {})).items()
    }
    frozen_family_complete = {
        subset: subset_counts.get(subset, 0) == expected
        for subset, expected in frozen_family_target_counts.items()
    }
    return {
        "task_count": len(tasks),
        "task_count_target": int(spec.get("local_task_count_target", 0) or 0),
        "ready_task_count": review_status_counts.get("ready", 0),
        "ready_task_count_target": int(spec.get("ready_task_count_target", 0) or 0),
        "pending_user_review_count": review_status_counts.get("pending_user_review", 0),
        "pending_user_review_count_target": int(spec.get("pending_user_review_count_target", 0) or 0),
        "review_status_counts": review_status_counts,
        "frozen_family_field": str(spec.get("frozen_family_field", "subset")),
        "frozen_family_target_counts": frozen_family_target_counts,
        "frozen_family_complete": frozen_family_complete,
        "subset_counts": subset_counts,
        "subset_ready_counts": subset_ready_counts,
        "subset_pending_counts": subset_pending_counts,
        "language_counts": language_counts,
        "chronology_tags": sorted(chronology_tags),
        "chronology_split_counts": chronology_split_counts,
        "release_window_counts": release_window_counts,
        "protected_asset_count": len(protected_assets),
        "protected_asset_ids": sorted(protected_assets),
        "canary_kind_counts": canary_kind_counts,
        "canary_split_counts": canary_split_counts,
        "canary_pack_counts": canary_pack_counts,
        "hidden_test_family_counts": hidden_test_family_counts,
        "operator_slice_counts": operator_slice_counts,
        "target_family_counts": target_families,
    }

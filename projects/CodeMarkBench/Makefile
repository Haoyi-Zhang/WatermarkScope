.RECIPEPREFIX = >
ifndef PYTHON
ifneq ("$(wildcard .venv/bin/python)","")
PYTHON := .venv/bin/python
else ifneq ("$(wildcard .venv/Scripts/python.exe)","")
PYTHON := .venv/Scripts/python.exe
else ifdef VIRTUAL_ENV
PYTHON := $(VIRTUAL_ENV)/bin/python
else
$(error Missing Python interpreter. Set PYTHON=/path/to/python, activate a dedicated virtualenv, or create .venv/bin/python)
endif
endif
CONFIG ?= configs/public_humaneval_plus_stone_runtime.yaml
RELEASE_BUNDLE_DIR ?= results/release_bundle
SUITE_MATRIX_MANIFEST ?= configs/matrices/suite_all_models_methods.json
SUITE_MATRIX_PROFILE ?= suite_all_models_methods
PRECHECK_STAGE_A_MANIFEST ?= configs/matrices/suite_canary_heavy.json
PRECHECK_STAGE_A_PROFILE ?= suite_canary_heavy
PRECHECK_STAGE_B_MANIFEST ?= configs/matrices/model_invocation_smoke.json
PRECHECK_STAGE_B_PROFILE ?= model_invocation_smoke
PRECHECK_GATE_OUTPUT ?= results/certifications/suite_precheck_gate.json
SUITE_GPU_SLOTS ?= 8
SUITE_CPU_WORKERS ?= 9
SUITE_MONITOR_INDEX ?= results/matrix/$(SUITE_MATRIX_PROFILE)/matrix_index.json
MATRIX_INDEX ?= $(SUITE_MONITOR_INDEX)
REVIEWER_SUBSET_ARGS ?=

.PHONY: help prepare-fixture prepare-data validate check-zero-legacy test-smoke suite-validate suite-validate-online validate-anonymity package-release export-publish-repo install-tools suite-clean dev-suite-matrix-local dev-suite-matrix-dry-run suite-precheck suite-precheck-dry-run suite-monitor matrix-monitor export-summaries dataset-stats reviewer-browse reviewer-regenerate reviewer-subset capture-environment

help:
> @echo "Targets:"
> @echo "  prepare-fixture Normalize the synthetic debug fixture"
> @echo "  validate        Check one canonical runtime config for local setup issues"
> @echo "  test-smoke      Run release integrity and lightweight no-GPU regression tests"
> @echo "  check-zero-legacy Fail if any tracked tree content still uses the old project name"
> @echo "  suite-validate  Check the canonical release-suite prerequisites"
> @echo "  suite-validate-online Check the canonical release-suite rerun gate including HF access"
> @echo "  validate-anonymity Check anonymous-release hygiene for staged bundles"
> @echo "  package-release Stage a sanitized release bundle"
> @echo "  export-publish-repo Export a clean CodeMarkBench git repo with fresh history"
> @echo "  suite-clean     Delete active suite outputs before a clean rerun"
> @echo "  deployment of record: single-host Linux 8-GPU canonical path (see docs/remote_linux_gpu.md)"
> @echo "  optional throughput reproduction: two-host 8+8 sharded identical-execution-class path"
> @echo "  suite-precheck  Run the two-stage suite precheck"
> @echo "  suite-precheck-dry-run Preview both precheck manifests"
> @echo "  suite-monitor   Watch the active suite matrix index and GPU state"
> @echo "  matrix-monitor  Watch any matrix index; override MATRIX_INDEX=..."
> @echo "  export-summaries Refresh report metadata and export final figures/tables from finished full-run results"
> @echo "  dataset-stats   Export repository-tracked dataset statistics figures/tables"
> @echo "  reviewer-browse Show the canonical reviewer browse path"
> @echo "  reviewer-regenerate Regenerate public figures/tables from a matrix index"
> @echo "  reviewer-subset  Build a reviewer subset manifest; pass REVIEWER_SUBSET_ARGS to filter it"
> @echo "  capture-environment Capture the exact runtime environment"
> @echo "  install-tools   Create local directories and verify prerequisites"

prepare-fixture:
> $(PYTHON) scripts/prepare_data.py --config $(CONFIG)

prepare-data: prepare-fixture

validate:
> $(PYTHON) scripts/validate_setup.py --config $(CONFIG)
> $(PYTHON) scripts/check_zero_legacy_name.py --root .

check-zero-legacy:
> $(PYTHON) scripts/check_zero_legacy_name.py --root .

test-smoke:
> $(PYTHON) scripts/verify_release_integrity.py
> $(PYTHON) scripts/reviewer_workflow.py browse --summary-only
> $(PYTHON) -m pytest tests/test_capture_environment.py tests/test_certify_suite_precheck.py tests/test_reviewer_workflow.py tests/test_suite_manifests.py -q

suite-validate:
> $(PYTHON) scripts/audit_full_matrix.py --manifest $(SUITE_MATRIX_MANIFEST) --profile $(SUITE_MATRIX_PROFILE) --strict-hf-cache --skip-provider-credentials --skip-hf-access

suite-validate-online:
> $(PYTHON) scripts/audit_full_matrix.py --manifest $(SUITE_MATRIX_MANIFEST) --profile $(SUITE_MATRIX_PROFILE) --strict-hf-cache --model-load-smoke --runtime-smoke --skip-provider-credentials

validate-anonymity:
> $(PYTHON) scripts/validate_setup.py --config $(CONFIG) --check-anonymity

package-release: check-zero-legacy
> bash scripts/package_zenodo.sh
> $(PYTHON) scripts/validate_release_bundle.py --bundle $(RELEASE_BUNDLE_DIR)

export-publish-repo: check-zero-legacy
> $(PYTHON) scripts/export_publish_repo.py

suite-clean:
> $(PYTHON) scripts/clean_suite_outputs.py --include-full-matrix --include-release-bundle

dev-suite-matrix-local:
> $(PYTHON) scripts/run_full_matrix.py --manifest $(SUITE_MATRIX_MANIFEST) --profile $(SUITE_MATRIX_PROFILE) --output-root results/matrix/dev_suite_all_models_methods --gpu-slots $(SUITE_GPU_SLOTS) --gpu-pool-mode shared --cpu-workers $(SUITE_CPU_WORKERS) --fail-fast

dev-suite-matrix-dry-run:
> $(PYTHON) scripts/run_full_matrix.py --manifest $(SUITE_MATRIX_MANIFEST) --profile $(SUITE_MATRIX_PROFILE) --output-root results/matrix/dev_suite_all_models_methods --gpu-slots $(SUITE_GPU_SLOTS) --gpu-pool-mode shared --cpu-workers $(SUITE_CPU_WORKERS) --dry-run

suite-precheck:
> $(PYTHON) scripts/certify_suite_precheck.py --full-manifest $(SUITE_MATRIX_MANIFEST) --full-profile $(SUITE_MATRIX_PROFILE) --stage-a-manifest $(PRECHECK_STAGE_A_MANIFEST) --stage-a-profile $(PRECHECK_STAGE_A_PROFILE) --stage-b-manifest $(PRECHECK_STAGE_B_MANIFEST) --stage-b-profile $(PRECHECK_STAGE_B_PROFILE) --output $(PRECHECK_GATE_OUTPUT) --gpu-slots $(SUITE_GPU_SLOTS) --cpu-workers $(SUITE_CPU_WORKERS) --fail-fast

suite-precheck-dry-run:
> $(PYTHON) scripts/run_full_matrix.py --manifest $(PRECHECK_STAGE_A_MANIFEST) --profile $(PRECHECK_STAGE_A_PROFILE) --gpu-slots $(SUITE_GPU_SLOTS) --gpu-pool-mode shared --cpu-workers $(SUITE_CPU_WORKERS) --dry-run
> $(PYTHON) scripts/run_full_matrix.py --manifest $(PRECHECK_STAGE_B_MANIFEST) --profile $(PRECHECK_STAGE_B_PROFILE) --gpu-slots $(SUITE_GPU_SLOTS) --gpu-pool-mode shared --cpu-workers $(SUITE_CPU_WORKERS) --dry-run

suite-monitor:
> $(PYTHON) scripts/monitor_matrix.py --matrix-index $(SUITE_MONITOR_INDEX) --watch-seconds 5

matrix-monitor:
> $(PYTHON) scripts/monitor_matrix.py --matrix-index $(MATRIX_INDEX) --watch-seconds 5

export-summaries:
> $(PYTHON) scripts/refresh_report_metadata.py --matrix-index results/matrix/suite_all_models_methods/matrix_index.json
> $(PYTHON) scripts/export_full_run_tables.py --matrix-index results/matrix/suite_all_models_methods/matrix_index.json --output-dir results/tables/suite_all_models_methods
> $(PYTHON) scripts/render_materialized_summary_figures.py --table-dir results/tables/suite_all_models_methods --output-dir results/figures/suite_all_models_methods --export-identity results/tables/suite_all_models_methods/suite_all_models_methods_export_identity.json --require-times-new-roman

dataset-stats:
> $(PYTHON) scripts/export_dataset_statistics.py

reviewer-browse:
> $(PYTHON) scripts/reviewer_workflow.py browse

reviewer-regenerate:
> $(PYTHON) scripts/reviewer_workflow.py regenerate

reviewer-subset:
> $(PYTHON) scripts/reviewer_workflow.py subset $(REVIEWER_SUBSET_ARGS)

capture-environment:
> CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 $(PYTHON) scripts/capture_environment.py --label formal_execution_host_pre_rerun --execution-mode single_host_canonical --output-json results/environment/runtime_environment.json --output-md results/environment/runtime_environment.md

install-tools:
> bash scripts/install_tools.sh

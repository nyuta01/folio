# Lightweight harness entrypoint for Folio.
#
# Keep this file as the single command surface for agents. Product-specific
# checks should be added behind `make verify` as implementation lands.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
MAKEFLAGS += --no-print-directory

PYTHON ?= python3
UV ?= uv

.DEFAULT_GOAL := help

.PHONY: help
help: ## List documented targets.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: agent-init
agent-init: ## Print restart context and run the current verification gate.
	@bash scripts/agent-init.sh

.PHONY: harness-check
harness-check: ## Validate repository harness shape and structured task state.
	@$(PYTHON) scripts/harness_check.py

.PHONY: drift-check
drift-check: ## Validate plan/failure-log drift invariants.
	@$(PYTHON) scripts/harness_drift.py

.PHONY: validate-docs
validate-docs: ## Validate design docs, ADR structure, and docs-local links.
	@$(PYTHON) scripts/validate_docs.py

.PHONY: sync
sync: ## Install Python dependencies into the project virtual environment.
	@$(UV) sync

.PHONY: python-test
python-test: ## Run Folio Python unit tests.
	@$(UV) run --frozen pytest tests

.PHONY: verify
verify: harness-check drift-check validate-docs python-test ## Run the current single verification gate.
	@echo "verify: ok"

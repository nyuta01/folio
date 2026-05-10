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

.PHONY: cli-smoke
cli-smoke: ## Run the folio CLI smoke against a temporary sheet.
	@bash scripts/smoke-cli.sh

.PHONY: materialize-smoke
materialize-smoke: ## Run the Phase 1 materialize smoke against a stubbed AI client.
	@bash scripts/smoke-materialize.sh

.PHONY: scripts-smoke
scripts-smoke: ## Run the Phase 2 reusable-script smoke against a temporary sheet.
	@bash scripts/smoke-scripts.sh

.PHONY: mcp-smoke
mcp-smoke: ## Run the Phase 3 MCP server smoke through FastMCP's in-process client.
	@bash scripts/smoke-mcp.sh

.PHONY: extension-kinds-smoke
extension-kinds-smoke: ## Run the Phase 4 sql + http extension-kind smoke offline.
	@bash scripts/smoke-extension-kinds.sh

.PHONY: viewer-smoke
viewer-smoke: ## Run the Phase 5 Viewer backend smoke (uvicorn + REST round-trip).
	@bash scripts/smoke-viewer.sh

.PHONY: verify
verify: harness-check drift-check validate-docs python-test cli-smoke materialize-smoke scripts-smoke mcp-smoke extension-kinds-smoke viewer-smoke ## Run the current single verification gate.
	@echo "verify: ok"

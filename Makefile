# ---------------------------------------------------------------------------
#  Telegram Community Bot - developer shortcuts
# ---------------------------------------------------------------------------
PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: venv
venv: ## Create the virtual environment
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip setuptools wheel

.PHONY: install
install: venv ## Install runtime dependencies
	$(BIN)/python -m pip install -r requirements.txt

.PHONY: dev
dev: venv ## Install development dependencies
	$(BIN)/python -m pip install -r requirements-dev.txt

.PHONY: run
run: ## Run the bot
	$(BIN)/python -m bot run

.PHONY: check
check: ## Validate configuration and environment without connecting
	$(BIN)/python -m bot check

.PHONY: test
test: ## Run the test suite
	$(BIN)/python -m pytest

.PHONY: cov
cov: ## Run tests with coverage report
	$(BIN)/python -m pytest --cov --cov-report=term-missing

.PHONY: lint
lint: ## Lint with ruff
	$(BIN)/ruff check .

.PHONY: fmt
fmt: ## Auto-format / auto-fix with ruff
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

.PHONY: typecheck
typecheck: ## Static type check with mypy
	$(BIN)/mypy bot

.PHONY: doctor
doctor: ## Print a full environment report
	bash scripts/doctor.sh

.PHONY: backup
backup: ## Create a timestamped backup archive
	bash scripts/backup.sh

.PHONY: docker
docker: ## Build the docker image
	docker build -f deploy/docker/Dockerfile -t telegram-community-bot:latest .

.PHONY: clean
clean: ## Remove caches and build artefacts
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

.PHONY: ci
ci: ## Run every CI check locally (lint, format, tests, mypy, scripts)
	bash scripts/ci.sh

.PHONY: ci-quick
ci-quick: ## Fast local check: lint, format, tests
	bash scripts/ci.sh --quick

.PHONY: update
update: ## Update an existing installation (backup, pull, deps, migrate, restart)
	bash scripts/update.sh

.PHONY: install-service
install-service: ## Install the systemd service (needs sudo)
	sudo bash scripts/install.sh --service --venv $(VENV)

.PHONY: fresh
fresh: clean ## Remove every cache and the virtual environment
	rm -rf $(VENV)

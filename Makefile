.PHONY: dev down logs test-unit test-integration test-e2e lint fmt coverage

# ── Local development ────────────────────────────────────────────────────────

dev: ## Start the full stack (builds images on first run)
	@test -f .env || cp .env.example .env
	docker compose up --build -d
	@echo ""
	@echo "  Web console:  http://localhost:8000"
	@echo "  API docs:     http://localhost:8000/docs"

down: ## Stop the stack and remove containers
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f

# ── Quality ──────────────────────────────────────────────────────────────────

lint: ## Ruff lint
	ruff check .

fmt: ## Ruff auto-format + fix
	ruff format .
	ruff check --fix .

test-unit: ## Fast unit tests, no infrastructure needed
	pytest

test-integration: ## Cross-service tests (requires: make dev)
	pytest tests/integration -q

test-e2e: ## Black-box end-to-end tests (requires: make dev)
	pytest tests/e2e -q

coverage: ## Unit tests with HTML coverage report
	pytest --cov=shared --cov=services --cov-report=html --cov-report=term
	@echo "open htmlcov/index.html"

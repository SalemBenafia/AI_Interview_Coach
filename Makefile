# AI Interview Coach — Developer Workflow Makefile
# Usage: make <target>
# Run `make help` for a list of all targets.

.PHONY: help setup dev build test test-e2e lint format type-check \
        db-migrate db-seed db-reset \
        docker-up docker-down docker-logs \
        clean install-tools download-voice check-openrouter

# ─── Colors ───────────────────────────────────────────────────────────────────
BOLD    := \033[1m
GREEN   := \033[0;32m
YELLOW  := \033[0;33m
CYAN    := \033[0;36m
RESET   := \033[0m

# ─── Directories ──────────────────────────────────────────────────────────────
BACKEND_DIR   := backend
FRONTEND_DIR  := frontend

# ─── Help ─────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@echo ""
	@echo "  $(BOLD)AI Interview Coach — Development Commands$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-25s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ─── Setup ────────────────────────────────────────────────────────────────────

setup: ## Full first-time setup: install deps, copy .env, init DB
	@echo "$(GREEN)→ Setting up AI Interview Coach...$(RESET)"
	@$(MAKE) install-backend
	@$(MAKE) install-frontend
	@$(MAKE) env-copy
	@echo "$(GREEN)✓ Setup complete. Run 'make docker-up' to start services.$(RESET)"

install-tools: ## Install ruff globally (requires pip)
	@echo "$(YELLOW)→ Installing Python tooling...$(RESET)"
	pip install ruff --quiet
	@echo "$(GREEN)✓ ruff installed$(RESET)"

env-copy: ## Copy .env.example to .env if it doesn't exist (root + backend + frontend)
	@test -f .env || (cp .env.example .env && echo "$(GREEN)✓ .env created from .env.example$(RESET)")
	@test -f $(BACKEND_DIR)/.env || (cp $(BACKEND_DIR)/.env.example $(BACKEND_DIR)/.env && echo "$(GREEN)✓ backend/.env created$(RESET)")
	@test -f $(FRONTEND_DIR)/.env || (cp $(FRONTEND_DIR)/.env.example $(FRONTEND_DIR)/.env && echo "$(GREEN)✓ frontend/.env created$(RESET)")

install-backend: ## Install Python dependencies
	@echo "$(YELLOW)→ Installing backend dependencies...$(RESET)"
	cd $(BACKEND_DIR) && pip install -r requirements.txt --quiet
	@echo "$(GREEN)✓ Backend dependencies installed$(RESET)"

install-frontend: ## Install Node.js dependencies
	@echo "$(YELLOW)→ Installing frontend dependencies...$(RESET)"
	cd $(FRONTEND_DIR) && npm install --quiet
	@echo "$(GREEN)✓ Frontend dependencies installed$(RESET)"

# ─── Model / Voice Downloads ───────────────────────────────────────────────────

check-openrouter: ## Verify OPENROUTER_API_KEY is set and OpenRouter is reachable
	@echo "$(YELLOW)→ Checking OpenRouter connectivity...$(RESET)"
	@docker compose exec -T backend python3 -c "\
import httpx, os; \
key = os.environ.get('OPENROUTER_API_KEY', ''); \
print('OPENROUTER_API_KEY is not set — get one free at https://openrouter.ai/keys') if not key else None; \
r = httpx.get('https://openrouter.ai/api/v1/models', headers={'Authorization': f'Bearer {key}'}, timeout=10) if key else None; \
print('OpenRouter reachable, status:', r.status_code) if r else None"
	@echo "$(GREEN)✓ Check complete$(RESET)"

download-voice: ## Download the default Piper voice model into services/tts-service/voices
	@echo "$(YELLOW)→ Downloading Piper voice en_US-amy-medium...$(RESET)"
	cd services/tts-service && python3 -m piper.download_voices en_US-amy-medium --download-dir ./voices
	@echo "$(GREEN)✓ Voice downloaded$(RESET)"

# ─── Development ──────────────────────────────────────────────────────────────

dev: ## Start full local dev stack (Docker + migrations)
	@echo "$(GREEN)→ Starting AI Interview Coach dev stack...$(RESET)"
	@$(MAKE) docker-up
	@sleep 5
	@$(MAKE) db-migrate

dev-backend: ## Start FastAPI dev server only
	cd $(BACKEND_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start Next.js dev server only
	cd $(FRONTEND_DIR) && npm run dev

dev-celery: ## Start Celery worker
	cd $(BACKEND_DIR) && celery -A app.core.celery_app worker --loglevel=info

dev-voice-agent: ## Start the LiveKit voice-agent worker locally
	cd $(BACKEND_DIR) && python -m app.voice_worker.worker dev

# ─── Database ─────────────────────────────────────────────────────────────────

db-migrate: ## Run Alembic migrations
	@echo "$(YELLOW)→ Running migrations...$(RESET)"
	cd $(BACKEND_DIR) && alembic upgrade head
	@echo "$(GREEN)✓ Migrations applied$(RESET)"

db-revision: ## Autogenerate a new Alembic revision (usage: make db-revision msg="add foo")
	cd $(BACKEND_DIR) && alembic revision --autogenerate -m "$(msg)"

db-seed: ## Seed demo data (admin, candidate, roles, default agents, sample flow)
	@echo "$(YELLOW)→ Seeding database...$(RESET)"
	cd $(BACKEND_DIR) && python seed.py
	@echo "$(GREEN)✓ Seed complete$(RESET)"

db-reset: ## Drop and recreate the database, re-run migrations + seed
	@echo "$(YELLOW)→ Resetting database...$(RESET)"
	docker compose exec -T postgres psql -U coach -c "DROP DATABASE IF EXISTS interview_coach;"
	docker compose exec -T postgres psql -U coach -c "CREATE DATABASE interview_coach;"
	@$(MAKE) db-migrate
	@$(MAKE) db-seed
	@echo "$(GREEN)✓ Database reset complete$(RESET)"

# ─── Docker ───────────────────────────────────────────────────────────────────

docker-up: ## Start all services via Docker Compose
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-logs: ## Tail logs from all services
	docker compose logs -f

docker-logs-backend: ## Tail backend logs only
	docker compose logs -f backend celery_worker celery_beat voice-agent

docker-rebuild: ## Rebuild all images from scratch
	docker compose build --no-cache

# ─── Code Quality ─────────────────────────────────────────────────────────────

lint: ## Lint backend (ruff) and frontend (biome)
	cd $(BACKEND_DIR) && ruff check .
	cd $(FRONTEND_DIR) && npm run lint

lint-fix: ## Auto-fix lint issues on both sides
	cd $(BACKEND_DIR) && ruff check --fix .
	cd $(FRONTEND_DIR) && npm run lint:fix

format: ## Format backend (ruff) and frontend (biome)
	cd $(BACKEND_DIR) && ruff format .
	cd $(FRONTEND_DIR) && npm run format

type-check: ## Type-check both sides
	cd $(BACKEND_DIR) && python -m py_compile $$(find app -name '*.py')
	cd $(FRONTEND_DIR) && npm run type-check

test: ## Run backend test suite
	cd $(BACKEND_DIR) && pytest -v

test-cov: ## Run backend tests with coverage
	cd $(BACKEND_DIR) && pytest --cov=app --cov-report=term-missing

test-e2e: ## Run Playwright E2E suite against the running docker-up stack
	docker compose exec playwright npx playwright test

ci: ## Full CI pipeline (lint + type-check + tests)
	@$(MAKE) lint
	@$(MAKE) type-check
	@$(MAKE) test

# ─── Cleanup ──────────────────────────────────────────────────────────────────

clean: ## Remove caches, build artifacts, __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(FRONTEND_DIR)/.next $(FRONTEND_DIR)/node_modules
	@echo "$(GREEN)✓ Cleaned$(RESET)"

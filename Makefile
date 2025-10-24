.PHONY: help install install-dev build shell test test-cov lint format clean run-api docker-test docker-smoke docker-down

# Help output
help:
	@echo ""
	@echo "Available targets:"
	@echo "  make install         Install prod dependencies"
	@echo "  make install-dev     Install dev + prod dependencies + pre-commit hooks"
	@echo "  make venv            Create and initialize a clean virtualenv"
	@echo "  make build           Build Docker image"
	@echo "  make shell           Run interactive container with mounted code"
	@echo "  make test            Run all tests with pytest"
	@echo "  make test-cov        Run tests with coverage report"
	@echo "  make lint            Run pre-commit on all files"
	@echo "  make format          Format code (black + ruff)"
	@echo "  make clean           Remove __pycache__ and .pyc files"
	@echo "  make run-api         Start FastAPI dev server with hot reload"
	@echo "  make docker-smoke    Run Docker smoke test (build + start + health check)"
	@echo "  make docker-test     Full Docker test suite (includes all checks)"
	@echo "  make docker-down     Stop and remove Docker containers"
	@echo ""

# Install only production dependencies
install:
	pip install -r requirements.txt

# Install all dev tools + prod deps + pre-commit hooks
install-dev: install
	pip install -r dev-requirements.txt
	pre-commit install
	@echo ""
	@echo "✅ Pre-commit hooks installed successfully!"
	@echo "   Hooks will run automatically on 'git commit'"
	@echo ""

# Install all dev tools + prod deps in a virtual environment
venv:
	python3 -m venv venv && source venv/bin/activate && make install-dev

# Build Docker image
build:
	docker build -t sync-airbnb .

# Run an interactive shell in the container
shell:
	docker run -it --rm \
		--env-file=.env \
		-v $(PWD):/app \
		-w /app \
		sync-airbnb \
		/bin/bash

# Run tests inside the container
test-container:
	docker run --rm \
		--env-file=.env \
		-v $(PWD):/app \
		-w /app \
		sync-airbnb \
		make test

# Run all local tests
test:
	pytest -v --tb=short

# Run tests with coverage
test-cov:
	pytest -v --cov=sync_airbnb --cov-report=term-missing --cov-report=html
	@echo ""
	@echo "📊 Coverage report generated:"
	@echo "   Terminal: see above"
	@echo "   HTML: open htmlcov/index.html"
	@echo ""

# Run pre-commit on all files
lint:
	pre-commit run --all-files

# Format code with Black
format:
	black .

# Remove caches and pyc
clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -r {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage

# Start FastAPI dev server with hot reload
run-api:
	uvicorn sync_airbnb.main:app --host 0.0.0.0 --port 8000 --reload

# Quick Docker smoke test - just verifies container starts and is healthy
docker-smoke:
	@echo "Running Docker smoke test..."
	@echo ""
	@# Stop any running containers
	@docker-compose down -v 2>/dev/null || true
	@# Build and start
	@echo "Building Docker image..."
	@docker-compose build --quiet
	@echo "Starting containers..."
	@docker-compose up -d
	@# Wait for health check
	@echo "Waiting for application to be healthy..."
	@timeout 60 bash -c 'until curl -sf http://localhost:8000/health > /dev/null 2>&1; do sleep 2; done' || { \
		echo ""; \
		echo "FAILED: Application failed to start within 60 seconds"; \
		echo ""; \
		echo "Container logs:"; \
		docker-compose logs app; \
		docker-compose down -v; \
		exit 1; \
	}
	@echo ""
	@echo "PASSED: Docker smoke test passed!"
	@echo "   Application is running at http://localhost:8000"
	@echo ""
	@echo "To stop: make docker-down"
	@echo "To view logs: docker-compose logs -f app"
	@echo ""

# Comprehensive Docker test - build, start, health checks, error scanning
docker-test:
	@echo "Running comprehensive Docker tests..."
	@echo ""
	@# Stop any running containers
	@docker-compose down -v 2>/dev/null || true
	@# Build and start
	@echo "1/5 Building Docker image..."
	@docker-compose build --quiet
	@echo "2/5 Starting containers..."
	@docker-compose up -d
	@# Wait for health check
	@echo "3/5 Waiting for application to be healthy..."
	@timeout 60 bash -c 'until curl -sf http://localhost:8000/health > /dev/null 2>&1; do sleep 2; done' || { \
		echo ""; \
		echo "FAILED: Application failed to start within 60 seconds"; \
		echo ""; \
		echo "Container logs:"; \
		docker-compose logs app; \
		docker-compose down -v; \
		exit 1; \
	}
	@# Test health endpoint
	@echo "4/5 Testing health endpoint..."
	@response=$$(curl -s http://localhost:8000/health); \
	if ! echo "$$response" | grep -q '"status":"ok"'; then \
		echo ""; \
		echo "FAILED: Health check failed"; \
		echo "Response: $$response"; \
		docker-compose logs app; \
		docker-compose down -v; \
		exit 1; \
	fi
	@# Test ready endpoint
	@echo "5/5 Testing ready endpoint..."
	@response=$$(curl -s http://localhost:8000/health/ready); \
	if ! echo "$$response" | grep -q '"status":"ready"'; then \
		echo ""; \
		echo "FAILED: Ready check failed"; \
		echo "Response: $$response"; \
		docker-compose logs app; \
		docker-compose down -v; \
		exit 1; \
	fi
	@# Check for errors in logs
	@echo "Scanning logs for errors..."
	@if docker-compose logs app | grep -iE "error|exception|traceback" | grep -v "continue-on-error" > /dev/null 2>&1; then \
		echo ""; \
		echo "WARNING: Found errors in application logs:"; \
		docker-compose logs app | grep -iE "error|exception|traceback" | grep -v "continue-on-error"; \
		echo ""; \
		echo "Full logs:"; \
		docker-compose logs app; \
		docker-compose down -v; \
		exit 1; \
	fi
	@echo ""
	@echo "PASSED: All Docker tests passed!"
	@echo "   Application is running at http://localhost:8000"
	@echo "   Health: http://localhost:8000/health"
	@echo "   Ready: http://localhost:8000/health/ready"
	@echo ""
	@echo "To stop: make docker-down"
	@echo "To view logs: docker-compose logs -f app"
	@echo ""

# Stop and remove Docker containers
docker-down:
	docker-compose down -v

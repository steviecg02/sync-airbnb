.PHONY: help install install-dev build shell test test-cov lint format clean run-api

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

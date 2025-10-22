l.PHONY: help install install-dev build shell test lint format clean

# Help output
help:
	@echo ""
	@echo "Available targets:"
	@echo "  make install         Install prod dependencies"
	@echo "  make install-dev     Install dev + prod dependencies"
	@echo "  make venv            Create and initialize a clean virtualenv"
	@echo "  make build           Build Docker image"
	@echo "  make shell           Run interactive container with mounted code"
	@echo "  make test            Run all tests with pytest"
	@echo "  make lint            Run linter (ruff)"
	@echo "  make format          Format code (black)"
	@echo "  make clean           Remove __pycache__ and .pyc files"
	@echo ""

# Install only production dependencies
install:
	pip install -r requirements.txt

# Install all dev tools + prod deps
install-dev: install
	pip install -r dev-requirements.txt

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

# Run Ruff linter
lint:
	ruff check . --fix

# Format code with Black
format:
	black .

# Remove caches and pyc
clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -r {} +
	find . -type d -name '__pycache__' -exec rm -r {} +
	rm -rf .pytest_cache .ruff_cache venv

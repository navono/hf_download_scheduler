.PHONY: help install test test-unit test-integration test-e2e lint format format-check lint-fix type-check check clean build

# Default target
help:
	@echo "Available commands:"
	@echo "  install      - Install dependencies with uv"
	@echo "  test         - Run all tests"
	@echo "  test-unit    - Run unit tests only"
	@echo "  test-integration - Run integration tests"
	@echo "  test-e2e     - Run end-to-end tests"
	@echo "  lint         - Run linting with ruff"
	@echo "  format       - Format code with ruff"
	@echo "  format-check - Check code formatting"
	@echo "  lint-fix     - Fix linting issues automatically"
	@echo "  type-check   - Run type checking with mypy"
	@echo "  check        - Run all checks (format, lint, type-check, test)"
	@echo "  clean        - Clean build artifacts"
	@echo "  build        - Build the package"
	@echo "  db-init      - Initialize database"
	@echo "  db-clean     - Clean database"
	@echo "  cli          - Run CLI command"

# Installation and setup
install:
	uv sync

test:
	uv run pytest -v

test-unit:
	uv run pytest -v -m unit

test-integration:
	uv run pytest -v -m integration

test-e2e:
	uv run pytest -v -m e2e

test-cov:
	uv run pytest -v --cov=src/hf_downloader --cov-report=term-missing

# Code quality
lint:
	uv run ruff check src tests

format:
	uv run ruff format src tests

format-check:
	uv run ruff format --check src tests

type-check:
	uv run mypy src

# Quick fixes with ruff
lint-fix:
	uv run ruff check --fix src tests

# Development workflow
check: format-check lint type-check test-cov

# Database management
db-init:
	uv run python -c "from src.hf_downloader.models.database import DatabaseManager; db = DatabaseManager('./hf_downloader.db'); print('Database initialized')"

db-clean:
	rm -f ./hf_downloader.db

# Application management
cli:
	uv run hf-downloader

start:
	uv run hf-downloader start

foreground:
	uv run hf-downloader start --foreground

stop:
	uv run hf-downloader stop

status:
	uv run hf-downloader status

# Build and distribution
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	uv build

# Development shortcuts
dev-install: install
	make db-init

dev-test: test-unit lint format-check

# Quick test during development
quick-test:
	uv run pytest -v tests/contract/ -x

# Test keyboard interrupt handling
test-interrupt:
	uv run python test_keyboard_interrupt.py
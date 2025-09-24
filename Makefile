# Makefile for AI Compliance Agent

.PHONY: help install test lint format clean run docker-build docker-run

# Default target
help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies and setup environment"
	@echo "  test        - Run all tests"
	@echo "  test-unit   - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  lint        - Run linting checks"
	@echo "  format      - Format code with black and isort"
	@echo "  type-check  - Run type checking with mypy"
	@echo "  clean       - Clean up temporary files"
	@echo "  run         - Run the application"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run  - Run with Docker Compose"
	@echo "  docs        - Generate documentation"

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e .

# Run all tests
test:
	@echo "Running all tests..."
	pytest tests/ -v --cov=src --cov-report=term-missing

# Run unit tests only
test-unit:
	@echo "Running unit tests..."
	pytest tests/unit/ -v

# Run integration tests only
test-integration:
	@echo "Running integration tests..."
	pytest tests/integration/ -v

# Linting
lint:
	@echo "Running linting checks..."
	flake8 src/ tests/
	black --check src/ tests/
	isort --check-only src/ tests/

# Format code
format:
	@echo "Formatting code..."
	black src/ tests/
	isort src/ tests/

# Type checking
type-check:
	@echo "Running type checks..."
	mypy src/

# Clean up
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/

# Run the application
run:
	@echo "Starting AI Compliance Agent..."
	python main.py

# Development server with reload
dev:
	@echo "Starting development server..."
	uvicorn src.compliance_agent.api.main:app --reload --host 0.0.0.0 --port 8000

# Build Docker image
docker-build:
	@echo "Building Docker image..."
	docker build -t ai-compliance-agent .

# Run with Docker Compose
docker-run:
	@echo "Starting with Docker Compose..."
	docker-compose up -d

# Stop Docker services
docker-stop:
	@echo "Stopping Docker services..."
	docker-compose down

# Generate documentation
docs:
	@echo "Generating documentation..."
	mkdocs build

# Serve documentation locally
docs-serve:
	@echo "Serving documentation..."
	mkdocs serve

# Check security vulnerabilities
security-check:
	@echo "Checking for security vulnerabilities..."
	pip audit

# Pre-commit hooks setup
pre-commit-install:
	@echo "Installing pre-commit hooks..."
	pre-commit install

# Run pre-commit on all files
pre-commit-all:
	@echo "Running pre-commit on all files..."
	pre-commit run --all-files

# Database migrations (when implemented)
migrate:
	@echo "Running database migrations..."
	alembic upgrade head

# Create new migration
migration:
	@echo "Creating new migration..."
	@read -p "Enter migration message: " message; \
	alembic revision --autogenerate -m "$$message"

# Backup database
backup-db:
	@echo "Backing up database..."
	pg_dump $(DATABASE_URL) > backup_$$(date +%Y%m%d_%H%M%S).sql

# Load test data
load-test-data:
	@echo "Loading test data..."
	python scripts/load_test_data.py

# Performance test
perf-test:
	@echo "Running performance tests..."
	locust -f tests/performance/locustfile.py
# Makefile for WhatsApp Hotel Bot

.PHONY: help install test test-unit test-integration test-green-api test-webhook test-coverage clean lint format

# Default target
help:
	@echo "WhatsApp Hotel Bot - Available Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install dependencies"
	@echo "  install-dev      Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-green-api   Run Green API tests"
	@echo "  test-webhook     Run webhook tests"
	@echo "  test-celery      Run Celery task tests"
	@echo "  test-coverage    Run tests with coverage report"
	@echo "  test-fast        Run fast tests only (exclude slow)"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             Run linting checks"
	@echo "  format           Format code with black and isort"
	@echo "  type-check       Run type checking with mypy"
	@echo ""
	@echo "Development:"
	@echo "  run-dev          Run development server"
	@echo "  run-worker       Run Celery worker"
	@echo "  run-beat         Run Celery beat scheduler"
	@echo ""
	@echo "Database:"
	@echo "  db-upgrade       Run database migrations"
	@echo "  db-downgrade     Rollback database migrations"
	@echo "  db-reset         Reset database (drop and recreate)"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean            Clean up temporary files"
	@echo "  clean-cache      Clean Python cache files"
	@echo "  clean-coverage   Clean coverage reports"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# Testing
test:
	python scripts/run_tests.py --all

test-unit:
	python -m pytest tests/unit/ -v --tb=short

test-integration:
	python -m pytest tests/integration/ -v --tb=short

test-green-api:
	python -m pytest tests/unit/test_green_api_client.py tests/unit/test_webhook_processor.py tests/unit/test_message_parser.py -v --tb=short

test-webhook:
	python -m pytest -m webhook -v --tb=short

test-celery:
	python -m pytest -m celery -v --tb=short

test-coverage:
	python -m pytest --cov=app --cov-report=term-missing --cov-report=html:htmlcov --cov-fail-under=85 --cov-branch

test-fast:
	python -m pytest -m "not slow" -v --tb=short

test-green-api-integration:
	python -m pytest tests/integration/test_green_api_integration.py -v --tb=short

# Code Quality
lint:
	flake8 app tests
	pylint app

format:
	black app tests scripts
	isort app tests scripts

type-check:
	mypy app

# Development
run-dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	celery -A app.core.celery_app worker --loglevel=info

run-beat:
	celery -A app.core.celery_app beat --loglevel=info

# Database
db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-reset:
	alembic downgrade base
	alembic upgrade head

# Docker
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-test:
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Cleanup
clean: clean-cache clean-coverage
	find . -type f -name "*.log" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-cache:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

clean-coverage:
	rm -rf htmlcov/
	rm -f coverage.xml
	rm -f .coverage
	rm -f .coverage.*

# Green API specific commands
green-api-test-all:
	@echo "Running all Green API tests..."
	python -m pytest tests/unit/test_green_api_client.py -v
	python -m pytest tests/unit/test_webhook_processor.py -v
	python -m pytest tests/unit/test_message_parser.py -v
	python -m pytest tests/integration/test_green_api_integration.py -v

green-api-mock-server:
	@echo "Starting Green API mock server for testing..."
	python tests/mocks/green_api_mock_server.py

# Coverage reports
coverage-report:
	coverage report --show-missing

coverage-html:
	coverage html
	@echo "HTML coverage report generated in htmlcov/"

coverage-xml:
	coverage xml
	@echo "XML coverage report generated as coverage.xml"

# Security
security-check:
	bandit -r app/
	safety check

# Documentation
docs-build:
	cd docs && make html

docs-serve:
	cd docs/_build/html && python -m http.server 8080

# Performance testing
perf-test:
	python -m pytest tests/performance/ -v --tb=short

load-test:
	locust -f tests/load/locustfile.py --host=http://localhost:8000

# Monitoring
monitor-celery:
	celery -A app.core.celery_app flower

# Environment setup
setup-env:
	cp .env.example .env
	@echo "Please edit .env file with your configuration"

# Git hooks
install-hooks:
	pre-commit install

run-hooks:
	pre-commit run --all-files

# Quick development setup
dev-setup: install-dev setup-env db-upgrade
	@echo "Development environment setup complete!"
	@echo "Run 'make run-dev' to start the development server"

# CI/CD helpers
ci-test:
	python -m pytest --cov=app --cov-report=xml --cov-fail-under=85 --tb=short

ci-lint:
	flake8 app tests --format=junit-xml --output-file=flake8-report.xml
	pylint app --output-format=parseable --reports=no > pylint-report.txt || true

# Release helpers
bump-version:
	bump2version patch

release-patch:
	bump2version patch
	git push origin main --tags

release-minor:
	bump2version minor
	git push origin main --tags

release-major:
	bump2version major
	git push origin main --tags

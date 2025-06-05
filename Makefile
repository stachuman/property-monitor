# Property Monitor - Development Makefile

.PHONY: help install install-dev run run-dev test test-cov clean lint format check docker-build docker-run backup

# Default target
help:
	@echo "Property Monitor - Available commands:"
	@echo ""
	@echo "  install      Install production dependencies"
	@echo "  install-dev  Install development dependencies"
	@echo "  run          Run the application in production mode"
	@echo "  run-dev      Run the application in development mode"
	@echo "  test         Run tests"
	@echo "  test-cov     Run tests with coverage report"
	@echo "  lint         Run linting checks"
	@echo "  format       Format code with black and isort"
	@echo "  check        Run all quality checks"
	@echo "  clean        Clean up generated files"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run   Run application in Docker"
	@echo "  backup       Create database backup"
	@echo ""

# Installation targets
install:
	pip install -r requirements.txt

install-dev: install
	pip install -r requirements-dev.txt || pip install pytest black flake8 mypy isort pre-commit
	pre-commit install

# Run targets
run:
	python main_service.py

run-dev:
	FLASK_ENV=development FLASK_DEBUG=true python main_service.py

# Test targets
test:
	python -m pytest

test-cov:
	python -m pytest --cov=. --cov-report=html --cov-report=term-missing

# Code quality targets
lint:
	flake8 .
	mypy .

format:
	black .
	isort .

check: format lint test
	@echo "All quality checks passed!"

# Cleanup targets
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/

# Docker targets
docker-build:
	docker build -t property-monitor:latest .

docker-run: docker-build
	docker run -d \
		--name property-monitor \
		-p 80:80 \
		-p 8080:8080 \
		-v property_data:/var/lib/property_monitor \
		-v property_logs:/var/log/property_monitor \
		property-monitor:latest

docker-stop:
	docker stop property-monitor || true
	docker rm property-monitor || true

docker-logs:
	docker logs -f property-monitor

# Database targets
backup:
	@if [ -f "/var/lib/property_monitor/properties.db" ]; then \
		cp /var/lib/property_monitor/properties.db backup_$(shell date +%Y%m%d_%H%M%S).db; \
		echo "Backup created: backup_$(shell date +%Y%m%d_%H%M%S).db"; \
	else \
		echo "Database file not found"; \
	fi

init-db:
	python -c "from database import DatabaseManager; DatabaseManager().init_database()"

# CLI shortcuts
status:
	python cli_tools.py status

scrape:
	python cli_tools.py scrape

geocode:
	python cli_tools.py geocode

# Development helpers
dev-setup: install-dev init-db
	@echo "Development environment setup complete!"

dev-reset: clean init-db
	@echo "Development environment reset complete!"

# Production helpers
prod-install:
	pip install --no-dev -r requirements.txt

prod-deploy: prod-install init-db
	sudo systemctl restart property-monitor
	@echo "Production deployment complete!"

# Monitoring helpers
logs:
	tail -f /var/log/property_monitor/property_monitor.log

health:
	python monitor.py --check-only

# Git helpers
pre-commit: format lint
	@echo "Pre-commit checks passed!"

release-patch:
	@echo "Creating patch release..."
	@current_version=$$(grep version pyproject.toml | head -1 | cut -d'"' -f2); \
	new_version=$$(python -c "v='$$current_version'.split('.'); v[2]=str(int(v[2])+1); print('.'.join(v))"); \
	sed -i "s/version = \"$$current_version\"/version = \"$$new_version\"/" pyproject.toml; \
	git add pyproject.toml; \
	git commit -m "chore: bump version to $$new_version"; \
	git tag "v$$new_version"; \
	echo "Created release v$$new_version"

release-minor:
	@echo "Creating minor release..."
	@current_version=$$(grep version pyproject.toml | head -1 | cut -d'"' -f2); \
	new_version=$$(python -c "v='$$current_version'.split('.'); v[1]=str(int(v[1])+1); v[2]='0'; print('.'.join(v))"); \
	sed -i "s/version = \"$$current_version\"/version = \"$$new_version\"/" pyproject.toml; \
	git add pyproject.toml; \
	git commit -m "chore: bump version to $$new_version"; \
	git tag "v$$new_version"; \
	echo "Created release v$$new_version"

# Documentation helpers
docs-serve:
	@echo "Starting documentation server..."
	@echo "README available at: http://localhost:8000"
	python -m http.server 8000

# System service helpers (requires sudo)
service-install:
	sudo cp property-monitor.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable property-monitor

service-start:
	sudo systemctl start property-monitor

service-stop:
	sudo systemctl stop property-monitor

service-restart:
	sudo systemctl restart property-monitor

service-status:
	sudo systemctl status property-monitor

service-logs:
	sudo journalctl -u property-monitor -f

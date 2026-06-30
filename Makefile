.PHONY: setup test lint format security clean docker-build docker-up docker-down

# Setup development environment
setup:
	@echo "🔧 Setting up development environment..."
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	./venv/bin/pip install -r requirements-dev.txt
	@echo "✅ Setup complete! Activate with: source venv/bin/activate"

# Run all tests
test:
	@echo "🧪 Running comprehensive test suite..."
	python -m pytest tests/ -v --cov=. --cov-report=html --cov-report=term
	@echo "📊 Coverage report generated in htmlcov/"

# Run linting
lint:
	@echo "🔍 Running code quality checks..."
	python -m ruff check .
	python -m mypy . --ignore-missing-imports
	@echo "✅ Linting complete"

# Format code
format:
	@echo "🎨 Formatting code..."
	python -m black .
	python -m ruff --fix .
	@echo "✅ Code formatted"

# Run security scan
security:
	@echo "🔒 Running security scans..."
	python -m safety check -r requirements.txt
	python -m bandit -r . -f json -o security-report.json
	@echo "✅ Security scan complete"

# Clean up generated files
clean:
	@echo "🧹 Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/
	@echo "✅ Cleanup complete"

# Build Docker images
docker-build:
	@echo "🐳 Building Docker images..."
	docker-compose build
	@echo "✅ Docker images built"

# Start all services
docker-up:
	@echo "🚀 Starting all services..."
	docker-compose up -d
	@echo "✅ Services started"
	@echo "📊 Grafana: http://localhost:3000 (admin/admin123)"
	@echo "📈 Prometheus: http://localhost:9090"
	@echo "🔧 Task Manager: http://localhost:8001"

# Stop all services
docker-down:
	@echo "🛑 Stopping all services..."
	docker-compose down
	@echo "✅ Services stopped"

# Initialize repository
init:
	@echo "🎯 Initializing AI Apps repository..."
	python ai_apps_manager.py initialize --repo-path .
	@echo "✅ Repository initialized"

# Run health monitoring
monitor:
	@echo "🏥 Starting health monitoring..."
	python ai_apps_manager.py monitor --config-file monitoring_config.json

# Create follow-up tasks (for testing)
test-followup:
	@echo "📋 Testing follow-up task creation..."
	python ai_apps_manager.py create-followup-tasks \
		--app-name test-app \
		--deployment-id test-deployment-123 \
		--environment staging

# Run comprehensive application test
test-app:
	@echo "🧪 Running comprehensive application tests..."
	python ai_apps_manager.py test-app --app-path ./starter_ai_agents/agno_starter

# Check all applications
check-all:
	@echo "🔍 Checking all applications..."
	for app in starter_ai_agents/*/ simple_ai_agents/*/ mcp_ai_agents/*/ rag_apps/*/ advance_ai_agents/*/; do \
		if [ -f "$app/requirements.txt" ]; then \
			echo "Checking $app"; \
			python ai_apps_manager.py test-app --app-path "$app"; \
		fi \
	done

# Development workflow
dev: format lint test security
	@echo "🎉 Development workflow complete!"

# Production deployment preparation
prod-prep: clean test security docker-build
	@echo "🚀 Production deployment preparation complete!"

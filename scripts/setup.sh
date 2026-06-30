#!/bin/bash
set -e

echo "🚀 Setting up AI Apps Repository Enhancement System"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install additional tools
pip install \
    asyncio \
    aiohttp \
    aiofiles \
    click \
    pydantic \
    sqlalchemy \
    alembic \
    redis \
    celery \
    prometheus-client \
    slack-sdk \
    PyGithub \
    safety \
    bandit \
    black \
    ruff \
    mypy \
    pytest \
    pytest-asyncio \
    pytest-cov

# Create necessary directories
mkdir -p logs task_data monitoring/dashboards scripts/health_checks

# Initialize task management database
python scripts/init_database.py

# Create configuration files
python scripts/create_configs.py

# Set up git hooks
cp scripts/pre-commit-hook .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# Build Docker images
docker-compose build

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and configure your API keys"
echo "2. Run 'python ai_apps_manager.py initialize' to initialize the repository"
echo "3. Run 'docker-compose up -d' to start monitoring services"
echo "4. Visit http://localhost:3000 for Grafana dashboard (admin/admin123)"

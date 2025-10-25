#!/bin/bash

# Start local development environment

set -e

echo "Starting Claude AI local development environment..."

cd "$(dirname "$0")/../docker"

# Check if .env file exists
if [ ! -f "../config/.env" ]; then
    echo "Error: .env file not found. Please run setup.sh first."
    exit 1
fi

# Load environment variables
export $(cat ../config/.env | grep -v '^#' | xargs)

# Start services
echo "Starting Docker Compose services..."
docker-compose up -d

echo ""
echo "Services started successfully!"
echo ""
echo "Available services:"
echo "- Claude App: http://localhost:8000"
echo "- Redis: localhost:6379"
echo "- PostgreSQL: localhost:5432"
echo "- Nginx: http://localhost:80"
echo ""
echo "View logs:"
echo "  docker-compose logs -f"
echo ""
echo "Stop services:"
echo "  docker-compose down"
echo ""

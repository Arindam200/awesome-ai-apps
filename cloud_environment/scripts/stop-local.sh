#!/bin/bash

# Stop local development environment

set -e

echo "Stopping Claude AI local development environment..."

cd "$(dirname "$0")/../docker"

# Stop services
docker-compose down

echo ""
echo "Services stopped successfully!"
echo ""
echo "To remove all data (volumes):"
echo "  docker-compose down -v"
echo ""

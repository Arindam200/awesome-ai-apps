#!/bin/bash

# Cleanup script - removes all containers, volumes, and images

set -e

echo "=========================================="
echo "Claude AI Environment Cleanup"
echo "=========================================="
echo ""
echo "WARNING: This will remove:"
echo "  - All Docker containers"
echo "  - All Docker volumes (data will be lost)"
echo "  - All Docker images for this project"
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
echo

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

cd "$(dirname "$0")/../docker"

echo "Stopping and removing containers..."
docker-compose down -v

echo "Removing Docker images..."
docker-compose down --rmi all

echo "Pruning unused Docker resources..."
docker system prune -f

echo ""
echo "Cleanup completed successfully!"
echo ""

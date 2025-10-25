#!/bin/bash

# Setup script for Claude AI Cloud Environment
# This script helps set up the local development environment

set -e

echo "=========================================="
echo "Claude AI Cloud Environment Setup"
echo "=========================================="

# Check if running in the correct directory
if [ ! -d "cloud_environment" ]; then
    echo "Error: Please run this script from the repository root directory"
    exit 1
fi

# Check Docker installation
echo "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

echo "Docker version:"
docker --version

# Check Docker Compose installation
echo "Checking Docker Compose installation..."
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose is not installed."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f "cloud_environment/config/.env" ]; then
    echo "Creating .env file from template..."
    cp cloud_environment/config/.env.example cloud_environment/config/.env
    echo "Please edit cloud_environment/config/.env and add your API keys"

    # Prompt for Anthropic API key
    echo ""
    echo "Enter your Anthropic API key (or press Enter to skip):"
    read -r ANTHROPIC_API_KEY

    if [ -n "$ANTHROPIC_API_KEY" ]; then
        # Update the .env file with the API key
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/ANTHROPIC_API_KEY=your_anthropic_api_key_here/ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY/" cloud_environment/config/.env
        else
            # Linux
            sed -i "s/ANTHROPIC_API_KEY=your_anthropic_api_key_here/ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY/" cloud_environment/config/.env
        fi
        echo "API key saved to .env file"
    fi
else
    echo ".env file already exists, skipping creation"
fi

# Make deployment scripts executable
echo "Making deployment scripts executable..."
chmod +x cloud_environment/deployment/aws/deploy.sh
chmod +x cloud_environment/deployment/gcp/deploy.sh
chmod +x cloud_environment/deployment/azure/deploy.sh
chmod +x cloud_environment/scripts/*.sh

echo ""
echo "=========================================="
echo "Setup completed successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit cloud_environment/config/.env with your configuration"
echo "2. Review cloud_environment/docker/docker-compose.yml"
echo "3. Start local development:"
echo "   cd cloud_environment/docker"
echo "   docker-compose up -d"
echo ""
echo "For cloud deployment:"
echo "- AWS: ./cloud_environment/deployment/aws/deploy.sh"
echo "- GCP: ./cloud_environment/deployment/gcp/deploy.sh"
echo "- Azure: ./cloud_environment/deployment/azure/deploy.sh"
echo ""

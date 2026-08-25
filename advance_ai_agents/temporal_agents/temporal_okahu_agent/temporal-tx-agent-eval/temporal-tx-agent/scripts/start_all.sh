#!/bin/bash

# Script to start all application services
# Usage: ./scripts/start_all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "🚀 Starting Transaction AI Application"
echo "======================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if Temporal is running
echo "🔍 Checking Temporal server..."
if ! curl -s http://localhost:8080 > /dev/null 2>&1; then
    echo "⚠️  Temporal server not running"
    echo "   Starting Temporal with Docker Compose..."
    
    # Create network if doesn't exist
    docker network create temporal-network 2>/dev/null || true
    
    # Clone docker-compose if needed
    if [ ! -d "docker-compose" ]; then
        echo "   Cloning Temporal docker-compose..."
        git clone https://github.com/temporalio/docker-compose.git
    fi
    
    # Start Temporal
    cd docker-compose
    docker-compose up -d
    cd ..
    
    echo "   Waiting for Temporal to start..."
    sleep 10
    
    if curl -s http://localhost:8080 > /dev/null 2>&1; then
        echo "   ✅ Temporal is now running"
    else
        echo "   ⚠️  Temporal may still be starting. Wait a bit and check: curl http://localhost:8080"
    fi
else
    echo "   ✅ Temporal server is running"
fi

echo ""
echo "📋 Starting Application Services"
echo "================================="
echo ""
echo "You need 3 terminal windows. This script will help you start them."
echo ""
echo "Press Enter to continue, or Ctrl+C to cancel..."
read

# Function to start service in new terminal
start_service() {
    local service_name=$1
    local command=$2
    
    echo ""
    echo "Starting $service_name..."
    echo "Command: $command"
    echo ""
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS - use osascript to open new terminal
        osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_DIR' && source venv/bin/activate && $command\""
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux - use gnome-terminal or xterm
        if command -v gnome-terminal &> /dev/null; then
            gnome-terminal -- bash -c "cd '$PROJECT_DIR' && source venv/bin/activate && $command; exec bash"
        elif command -v xterm &> /dev/null; then
            xterm -e "cd '$PROJECT_DIR' && source venv/bin/activate && $command" &
        else
            echo "   ⚠️  Please open a new terminal and run:"
            echo "      cd $PROJECT_DIR"
            echo "      source venv/bin/activate"
            echo "      $command"
        fi
    else
        echo "   ⚠️  Please open a new terminal and run:"
        echo "      cd $PROJECT_DIR"
        echo "      source venv/bin/activate"
        echo "      $command"
    fi
}

# Start services
start_service "Temporal Worker" "python -m temporal.run_worker"
sleep 2

start_service "FastAPI Server" "uvicorn api.main:app --reload --port 8000"
sleep 2

start_service "Streamlit Dashboard" "streamlit run app.py --server.port 8501"

echo ""
echo "✅ All services starting!"
echo ""
echo "📊 Access Points:"
echo "   - Dashboard: http://localhost:8501"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Temporal UI: http://localhost:8080"
echo "   - Health Check: http://localhost:8000/health"
echo ""
echo "⚠️  Keep all terminal windows open!"
echo ""
echo "To stop services, press Ctrl+C in each terminal window."
echo ""


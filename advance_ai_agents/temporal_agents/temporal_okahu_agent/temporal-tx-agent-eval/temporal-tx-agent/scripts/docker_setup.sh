#!/bin/bash

set -e

echo "🚀 Docker Setup for Transaction Processing System"
echo "================================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your couchbaseDB capella URI and OpenAI credentials"
    echo "   Then re-run this script."
    exit 1
fi

# Source .env file
export $(cat .env | grep -v '^#' | xargs)

# Check required environment variables
if [ -z "$couchbaseDB_URI" ]; then
    echo "❌ couchbaseDB_URI not set in .env file"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  OpenAI API key not set. AI features will use mock mode."
fi

# Start Temporal if not already running
echo "🐳 Checking Temporal setup..."
docker network inspect temporal-network >/dev/null 2>&1 || {
    echo "📦 Creating temporal-network..."
    docker network create temporal-network
}

# Check if Temporal is running
if ! docker ps | grep -q temporal; then
    echo "🚀 Starting Temporal..."
    if [ ! -d docker-compose ]; then
        git clone https://github.com/temporalio/docker-compose.git
    fi
    cd docker-compose
    grep -q "external: true" docker-compose.yml || echo -e "    external: true" >> docker-compose.yml
    docker-compose up -d
    cd ..
    echo "⏳ Waiting for Temporal to be ready..."
    sleep 10
else
    echo "✅ Temporal is already running"
fi

# Build and start application services
echo "🏗️  Building application containers..."
docker-compose build

echo "🚀 Starting application services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Setup couchbaseDB collections and indexes
echo ""
echo "🗄️ Setting up couchbaseDB collections and indexes..."
docker-compose exec -T api python -m scripts.setup_couchbasedb || {
    echo "⚠️  couchbaseDB setup failed. This might be because:"
    echo "   - couchbaseDB URI is not configured correctly"
    echo "   - couchbaseDB Capella is not accessible"
    echo "   - Collections might already exist"
    echo ""
    echo "   You can manually run setup later with:"
    echo "   docker-compose exec api python -m scripts.setup_couchbasedb"
}

# Additional wait for couchbaseDB setup
sleep 30

# Define URLs
DASHBOARD_URL="http://localhost:8501"
API_URL="http://localhost:8000"
TEMPORAL_URL="http://localhost:8080"

# Function to open URL in browser
open_browser() {
    local url=$1
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        open "$url" &>/dev/null
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        xdg-open "$url" &>/dev/null || sensible-browser "$url" &>/dev/null || echo "Please open $url in your browser"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        # Windows
        start "$url" &>/dev/null
    else
        echo "Please open $url in your browser"
    fi
}

# Monitor and auto-launch when ready
echo ""
echo "🔍 Waiting for services to be ready..."
echo "================================"

# Wait for all services to be ready
MAX_ATTEMPTS=30
ATTEMPT=0
ALL_READY=false

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    API_READY=false
    STREAMLIT_READY=false
    TEMPORAL_READY=false

    # Check each service
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        API_READY=true
    fi

    if curl -s http://localhost:8501 >/dev/null 2>&1; then
        STREAMLIT_READY=true
    fi

    if curl -s http://localhost:8080 >/dev/null 2>&1; then
        TEMPORAL_READY=true
    fi

    # Check if all services are ready
    if [ "$API_READY" = true ] && [ "$STREAMLIT_READY" = true ] && [ "$TEMPORAL_READY" = true ]; then
        ALL_READY=true
        echo ""
        echo "✅ All services are ready!"
        echo ""
        echo "🚀 Launching applications in browser..."

        # Launch Dashboard first (main UI)
        echo "   📊 Opening Dashboard: $DASHBOARD_URL"
        open_browser "$DASHBOARD_URL"
        sleep 2

        # Launch Temporal UI
        echo "   ⚙️  Opening Temporal UI: $TEMPORAL_URL"
        open_browser "$TEMPORAL_URL"
        sleep 1

        # Launch API Docs
        echo "   📚 Opening API Docs: $API_URL/docs"
        open_browser "$API_URL/docs"

        break
    else
        # Show status
        echo -n "⏳ Waiting for services... ["
        [ "$API_READY" = true ] && echo -n "API ✓" || echo -n "API ✗"
        echo -n " | "
        [ "$STREAMLIT_READY" = true ] && echo -n "Dashboard ✓" || echo -n "Dashboard ✗"
        echo -n " | "
        [ "$TEMPORAL_READY" = true ] && echo -n "Temporal ✓" || echo -n "Temporal ✗"
        echo "] (Attempt $((ATTEMPT+1))/$MAX_ATTEMPTS)"

        ATTEMPT=$((ATTEMPT + 1))
        sleep 5
    fi
done

if [ "$ALL_READY" = false ]; then
    echo ""
    echo "⚠️  Some services did not start within the expected time."
    echo "    You can check the logs with: docker-compose logs -f"
    echo ""
    echo "    Manual URLs:"
    echo "    • Dashboard: $DASHBOARD_URL"
    echo "    • API Docs: $API_URL/docs"
    echo "    • Temporal UI: $TEMPORAL_URL"
fi

echo ""
echo "🎉 Docker setup complete!"
echo ""
echo "📋 Quick Commands:"
echo "  • View logs: docker-compose logs -f [service-name]"
echo "  • Stop all: docker-compose down"
echo "  • Restart service: docker-compose restart [service-name]"
echo ""
echo "Services: api, streamlit, temporal-worker"
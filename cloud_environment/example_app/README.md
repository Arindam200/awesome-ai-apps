# Example Claude AI Application

A FastAPI-based template application demonstrating how to build and deploy Claude AI services using the cloud environment infrastructure.

## Features

- RESTful API with FastAPI
- Claude AI integration using Anthropic SDK
- Health check endpoints
- Streaming support
- CORS configuration
- Environment-based configuration
- Production-ready structure

## Quick Start

### Local Development

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set up environment variables:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
export ENVIRONMENT=development
export PORT=8000
```

3. Run the application:

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --reload --port 8000
```

### Using Docker

From the cloud_environment directory:

```bash
cd docker
docker-compose up -d
```

## API Endpoints

### Health Check

```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "1.0.0"
}
```

### Chat

```bash
POST /api/chat
Content-Type: application/json

{
  "message": "Hello, Claude!",
  "max_tokens": 1024,
  "temperature": 1.0
}
```

Response:
```json
{
  "response": "Hello! How can I help you today?",
  "model": "claude-3-5-sonnet-20241022",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 15
  }
}
```

### Streaming Chat

```bash
POST /api/chat/stream
Content-Type: application/json

{
  "message": "Tell me a story",
  "max_tokens": 1024
}
```

## Testing

### Using curl

```bash
# Health check
curl http://localhost:8000/health

# Send a message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is AI?",
    "max_tokens": 500
  }'
```

### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/chat",
    json={
        "message": "What is AI?",
        "max_tokens": 500
    }
)

print(response.json())
```

## Configuration

Environment variables:

- `ANTHROPIC_API_KEY` (required): Your Anthropic API key
- `ENVIRONMENT` (optional): development|production (default: development)
- `PORT` (optional): Server port (default: 8000)
- `LOG_LEVEL` (optional): Logging level (default: INFO)

## Deployment

This application is designed to work with the cloud environment infrastructure. See the main cloud_environment README for deployment instructions.

## Interactive API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Extending the Application

### Adding New Endpoints

Add new endpoints to `main.py`:

```python
@app.post("/api/custom")
async def custom_endpoint(data: CustomModel):
    # Your logic here
    return {"result": "success"}
```

### Adding Database Support

1. Install dependencies:
```bash
pip install sqlalchemy psycopg2-binary
```

2. Configure database connection in main.py

### Adding Caching

1. Install Redis client:
```bash
pip install redis
```

2. Configure Redis connection

## License

Part of the awesome-ai-apps repository under MIT License.

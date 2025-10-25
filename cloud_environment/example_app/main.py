"""
Example Claude AI Application
This is a template FastAPI application for deploying Claude-based AI services.
"""

import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Claude AI Application",
    description="A template application for Claude AI services",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Anthropic client
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY environment variable is required")

client = anthropic.Anthropic(api_key=api_key)


# Request/Response models
class MessageRequest(BaseModel):
    message: str
    max_tokens: Optional[int] = 1024
    temperature: Optional[float] = 1.0


class MessageResponse(BaseModel):
    response: str
    model: str
    usage: dict


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "version": "1.0.0"
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Claude AI Application",
        "status": "running",
        "docs": "/docs"
    }


# Chat endpoint
@app.post("/api/chat", response_model=MessageResponse)
async def chat(request: MessageRequest):
    """
    Send a message to Claude and get a response

    Args:
        request: MessageRequest containing the user's message

    Returns:
        MessageResponse with Claude's response
    """
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=[
                {"role": "user", "content": request.message}
            ]
        )

        return MessageResponse(
            response=message.content[0].text,
            model=message.model,
            usage={
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens
            }
        )
    except anthropic.APIError as e:
        raise HTTPException(status_code=500, detail=f"Claude API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# Example streaming endpoint
@app.post("/api/chat/stream")
async def chat_stream(request: MessageRequest):
    """
    Stream responses from Claude

    Args:
        request: MessageRequest containing the user's message
    """
    try:
        # For actual streaming, you'd use FastAPI's StreamingResponse
        # This is a simplified example
        with client.messages.stream(
            model="claude-3-5-sonnet-20241022",
            max_tokens=request.max_tokens,
            messages=[
                {"role": "user", "content": request.message}
            ]
        ) as stream:
            response_text = ""
            for text in stream.text_stream:
                response_text += text

            return {
                "response": response_text,
                "model": "claude-3-5-sonnet-20241022"
            }
    except anthropic.APIError as e:
        raise HTTPException(status_code=500, detail=f"Claude API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development"
    )

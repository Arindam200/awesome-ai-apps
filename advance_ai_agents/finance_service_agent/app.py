"""
Finance Service Agent FastAPI Application

A comprehensive FastAPI application providing stock market data, analysis,
and AI-powered financial insights through RESTful API endpoints.
"""

import logging
from typing import Optional

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from utils.redisCache import lifespan, get_cache
from routes.stockRoutes import router as stock_router
from routes.agentRoutes import router as agent_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('finance_service.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured application instance
    """
    try:
        # Create FastAPI app with lifespan for Redis management
        app = FastAPI(
            title="Finance Service Agent API",
            description="AI-powered financial analysis and stock market data service",
            version="1.0.0",
            lifespan=lifespan
        )
        
        # Configure CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Include routers
        app.include_router(stock_router, prefix="/api/v1", tags=["stocks"])
        app.include_router(agent_router, prefix="/api/v1", tags=["agent"])
        
        logger.info("FastAPI application created successfully")
        return app
        
    except Exception as e:
        logger.error(f"Failed to create FastAPI application: {e}")
        raise


# Create application instance
app = create_app()


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint.
    
    Returns:
        dict: Health status information
    """
    return {
        "status": "healthy",
        "service": "Finance Service Agent",
        "version": "1.0.0"
    }
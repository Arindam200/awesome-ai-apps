"""
Rediscache

Module description goes here.
"""

from typing import List, Dict, Optional, Union, Any
from fastapi_cache.backends.redis import RedisBackend
from contextlib import asynccontextmanager
from redis import asyncio as aioredis
from fastapi_cache import FastAPICache
from fastapi import FastAPI
import os
import dotenv

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


dotenv.load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

@asynccontextmanager
async def lifespan(_: FastAPI):
    redis_client = None  

    try:
        redis_client = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        FastAPICache.init(RedisBackend(redis_client), prefix="fastapi-cache")
        logger.info("✅ Redis cache initialized successfully!")
        yield
        
    except Exception as e:
        print(f"❌ Redis Connection Error: {e}")
        yield 
    finally:
        try:
            await FastAPICache.clear()
            if redis_client:
                await redis_client.close()  
                logger.info("🔴 Redis connection closed!")
        except Exception as e:
            print(f"❌ Error while closing Redis: {e}")

def get_cache():
    return FastAPICache.get_backend()

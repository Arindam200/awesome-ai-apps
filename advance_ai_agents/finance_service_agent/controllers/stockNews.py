"""
Stock News Controller

Handles fetching and processing of financial news from various sources
including Finnhub API for market-related news and insights.
"""

import logging
import os
import time
from typing import List, Dict, Optional, Union, Any

import finnhub
import requests
import dotenv

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

# Load environment variables
dotenv.load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

if not NEWS_API_KEY:
    raise ValueError("Please provide a NEWS API key")

# Configure requests session
session = requests.Session()
session.headers.update({
    "User-Agent": "Chrome/122.0.0.0"
})


def fetch_news() -> List[List[str]]:
    """Fetch latest financial news from Finnhub API.
    
    Returns:
        List of news items, each containing headline and URL
        
    Raises:
        Exception: If API request fails or data processing errors occur
    """
    try:
        finnhub_client = finnhub.Client(api_key=NEWS_API_KEY)
        news_list = finnhub_client.general_news('general', min_id=4)
        
        news_stack = []
        for news in news_list[:10]:
            news_stack.append([news['headline'], news['url']])
            
        logger.info("✅ Data fetching done successfully!")   
        return news_stack
        
    except Exception as e:
        logger.error(f"❌ Error fetching news: {e}")
        return []  # Return empty list on error
        
    time.sleep(5)  # Rate limiting
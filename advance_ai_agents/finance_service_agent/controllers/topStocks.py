"""
Top Stocks Controller

Handles fetching and processing of top performing stocks data
using yfinance API for real-time market information.
"""

import logging
import time
from typing import List, Dict, Optional, Union, Any

import yfinance as yf
import requests

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

# Configure requests session
session = requests.Session()
session.headers.update({
    "User-Agent": "Chrome/122.0.0.0"
})


def get_top_stock_info() -> List[Dict[str, Any]]:
    """Get top performing stocks information.
    
    Returns:
        List of dictionaries containing stock information including
        symbol, current price, and percentage change
        
    Raises:
        Exception: If data fetching or processing fails
    """
    tickers_list = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK-B", "JPM", 
        "JNJ", "V", "PG", "UNH", "MA", "HD", "XOM", "PFE", "NFLX", "DIS", "PEP",
        "KO", "CSCO", "INTC", "ORCL", "CRM", "NKE", "WMT", "BA", "CVX", "T", "UL",
        "IBM", "AMD"
    ]
    
    stock_data = []
    
    try:
        data = yf.download(tickers_list, period="2d", interval="1d", group_by='ticker', auto_adjust=True)
        changes = []

        for ticker in tickers_list:
            try:
                close_prices = data[ticker]['Close']
                percent_change = ((close_prices.iloc[-1] - close_prices.iloc[-2]) / close_prices.iloc[-2]) * 100
                changes.append((ticker, round(percent_change, 2)))
            except Exception as e:
                logger.warning(f"Failed to process ticker {ticker}: {e}")
                continue

        # Sort by absolute percent change and pick top 5
        top_5_tickers = [ticker for ticker, _ in sorted(changes, key=lambda x: abs(x[1]), reverse=True)[:5]]
        tickers = yf.Tickers(top_5_tickers)
        
        for stock_symbol in top_5_tickers:
            try:
                info = tickers.tickers[stock_symbol].info
                stock_info = {
                    'symbol': stock_symbol,
                    'name': info.get('shortName', 'N/A'),
                    'currentPrice': info.get('currentPrice', 'N/A'),
                    'previousClose': info.get('previousClose', 'N/A'),
                    'sector': info.get('sector', 'N/A')
                }
                stock_data.append(stock_info)
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch info for {stock_symbol}: {e}")
        
        logger.info("✅ Data fetching done successfully!")
        return stock_data

    except Exception as e:
        logger.error(f"❌ Error fetching stock data: {e}")
        return []


def get_stock(symbol: str) -> Dict[str, Any]:
    """Get detailed information for a specific stock symbol.
    
    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'MSFT')
        
    Returns:
        Dictionary containing stock information
        
    Raises:
        Exception: If stock data fetching fails
    """
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        stock_info = {
            'symbol': symbol,
            'name': info.get('shortName', 'N/A'),
            'currentPrice': info.get('currentPrice', 'N/A'),
            'previousClose': info.get('previousClose', 'N/A'),
            'sector': info.get('sector', 'N/A')
        }
        logger.info(f"✅ Data fetching done successfully for {symbol}!")
        return stock_info
        
    except Exception as e:
        logger.error(f"❌ Error fetching {symbol}: {e}")
        time.sleep(5)
        return {}

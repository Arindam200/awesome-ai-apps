"""
skills.py — Deterministic data-fetching tools for the Argus agent.

All skills use yfinance (free, no API key needed) to pull real financial data
from Yahoo Finance. They are registered as @app.skill decorators so AgentField
exposes them as REST endpoints AND the Reasoners can call them directly.

Skills intentionally return plain JSON-serialisable dicts/lists so the LLM
can reason over them without needing to understand yfinance objects.
"""
import asyncio
from typing import Optional

import yfinance as yf

from src import app


def _df_to_records(df) -> dict:
    """Convert a pandas DataFrame (yfinance financials) to a clean dict."""
    if df is None or df.empty:
        return {}
    # Transpose so rows = metrics, cols = dates; convert to string keys
    try:
        df = df.fillna(0)
        return {
            str(col.date()): df[col].to_dict() for col in df.columns
        }
    except Exception:
        return df.to_dict()


@app.skill()
async def validate_ticker(ticker: str) -> dict:
    """
    Check whether a ticker is actively tradable on a major exchange.

    Returns a dict with:
      - valid (bool): True if the ticker has live market data
      - reason (str): human-readable explanation if invalid
      - current_price (float | None): last known price
      - quote_type (str): EQUITY / ETF / CRYPTOCURRENCY / MUTUALFUND / etc.
      - exchange (str): exchange name
    """
    app.note(f"[skill] Validating ticker: {ticker}")

    def _fetch() -> dict:
        t = yf.Ticker(ticker)
        try:
            info = t.info or {}
        except Exception as exc:
            return {
                "valid": False,
                "reason": f"yfinance raised an error: {exc}",
                "current_price": None,
                "quote_type": None,
                "exchange": None,
            }

        if not info:
            return {
                "valid": False,
                "reason": (
                    f"No data returned for '{ticker}'. "
                    "It may be delisted, never listed, private, or misspelled."
                ),
                "current_price": None,
                "quote_type": None,
                "exchange": None,
            }

        price = info.get("regularMarketPrice") or info.get("currentPrice")
        quote_type = info.get("quoteType", "UNKNOWN")
        exchange = info.get("exchange") or info.get("fullExchangeName", "")

        if not price:
            name = info.get("longName") or info.get("shortName") or ticker
            return {
                "valid": False,
                "reason": (
                    f"'{ticker}' ({name}) has no live market price. "
                    "It is likely delisted, suspended, or no longer trading."
                ),
                "current_price": None,
                "quote_type": quote_type,
                "exchange": exchange,
            }

        return {
            "valid": True,
            "reason": "OK",
            "current_price": price,
            "quote_type": quote_type,
            "exchange": exchange,
        }

    return await asyncio.get_event_loop().run_in_executor(None, _fetch)


@app.skill()
async def get_income_statement(ticker: str, period: str = "annual") -> dict:
    """
    Fetch income statement data for a ticker using yfinance.

    Args:
        ticker: Stock ticker symbol (e.g. 'AAPL').
        period: 'annual' or 'quarterly'.

    Returns:
        Dict mapping date → {metric: value} for revenue, net income, EBITDA, etc.
    """
    app.note(f"[skill] Fetching income statement: {ticker} ({period})")

    def _fetch():
        t = yf.Ticker(ticker)
        df = t.income_stmt if period == "annual" else t.quarterly_income_stmt
        return _df_to_records(df)

    result = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    return result


@app.skill()
async def get_balance_sheet(ticker: str, period: str = "annual") -> dict:
    """
    Fetch balance sheet data for a ticker.

    Args:
        ticker: Stock ticker symbol.
        period: 'annual' or 'quarterly'.

    Returns:
        Dict mapping date → {metric: value} for assets, liabilities, equity, etc.
    """
    app.note(f"[skill] Fetching balance sheet: {ticker} ({period})")

    def _fetch():
        t = yf.Ticker(ticker)
        df = t.balance_sheet if period == "annual" else t.quarterly_balance_sheet
        return _df_to_records(df)

    result = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    return result


@app.skill()
async def get_cash_flow_statement(ticker: str, period: str = "annual") -> dict:
    """
    Fetch cash flow statement for a ticker.

    Args:
        ticker: Stock ticker symbol.
        period: 'annual' or 'quarterly'.

    Returns:
        Dict mapping date → {metric: value} for operating/investing/financing CF.
    """
    app.note(f"[skill] Fetching cash flow: {ticker} ({period})")

    def _fetch():
        t = yf.Ticker(ticker)
        df = t.cashflow if period == "annual" else t.quarterly_cashflow
        return _df_to_records(df)

    result = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    return result


@app.skill()
async def search_market_news(ticker: str, limit: int = 10) -> list[dict]:
    """
    Fetch recent news articles for a ticker via yfinance.

    Args:
        ticker: Stock ticker symbol.
        limit: Max number of articles to return (default 10).

    Returns:
        List of dicts with keys: title, publisher, link, providerPublishTime, type.
    """
    app.note(f"[skill] Fetching news: {ticker} (limit={limit})")

    def _fetch():
        t = yf.Ticker(ticker)
        news = t.news or []
        clean = []
        for article in news[:limit]:
            clean.append({
                "title": article.get("title", ""),
                "publisher": article.get("publisher", ""),
                "link": article.get("link", ""),
                "published_at": article.get("providerPublishTime", 0),
                "type": article.get("type", ""),
                "summary": article.get("summary", ""),
            })
        return clean

    result = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    return result


@app.skill()
async def get_company_facts(ticker: str) -> dict:
    """
    Fetch key company facts and fundamentals for a ticker.

    Includes: sector, industry, market cap, P/E ratio, EPS, dividend yield,
    52-week range, description, and analyst recommendations.

    Args:
        ticker: Stock ticker symbol.

    Returns:
        Dict of fundamental metrics.
    """
    app.note(f"[skill] Fetching company facts: {ticker}")

    def _fetch() -> dict:
        t = yf.Ticker(ticker)
        info = t.info or {}
        # Extract the most useful fields for financial analysis
        fields = [
            "shortName", "longName", "sector", "industry",
            "country", "website", "longBusinessSummary",
            "marketCap", "enterpriseValue",
            "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months",
            "trailingEps", "forwardEps",
            "revenueGrowth", "earningsGrowth", "grossMargins", "operatingMargins", "profitMargins",
            "totalRevenue", "ebitda", "totalDebt", "totalCash",
            "currentRatio", "debtToEquity",
            "dividendYield", "payoutRatio",
            "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "currentPrice",
            "recommendationMean", "recommendationKey", "numberOfAnalystOpinions",
            "beta", "sharesOutstanding", "floatShares",
        ]
        return {k: info.get(k) for k in fields if info.get(k) is not None}

    result = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    return result


@app.skill()
async def get_analyst_targets(ticker: str) -> dict:
    """
    Fetch sell-side analyst price targets and recommendation consensus.

    Returns:
        Dict with current price, mean/low/high targets, upside %, and
        recommendation distribution (strongBuy/buy/hold/sell/strongSell counts).
    """
    app.note(f"[skill] Fetching analyst targets: {ticker}")

    def _fetch() -> dict:
        t = yf.Ticker(ticker)
        info = t.info or {}

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        mean_target   = info.get("targetMeanPrice")
        low_target    = info.get("targetLowPrice")
        high_target   = info.get("targetHighPrice")

        upside = None
        if current_price and mean_target:
            upside = round((mean_target - current_price) / current_price * 100, 1)

        # Recommendation trend (last period)
        rec_trend = {}
        try:
            trend_df = t.recommendations_summary
            if trend_df is not None and not trend_df.empty:
                latest = trend_df.iloc[0]
                rec_trend = {
                    "strongBuy":  int(latest.get("strongBuy",  0)),
                    "buy":        int(latest.get("buy",        0)),
                    "hold":       int(latest.get("hold",       0)),
                    "sell":       int(latest.get("sell",       0)),
                    "strongSell": int(latest.get("strongSell", 0)),
                }
        except Exception:
            pass

        return {
            "current_price":          current_price,
            "target_mean":            mean_target,
            "target_low":             low_target,
            "target_high":            high_target,
            "implied_upside_percent": upside,
            "analyst_count":          info.get("numberOfAnalystOpinions"),
            "consensus_rating":       info.get("recommendationKey"),
            "consensus_score":        info.get("recommendationMean"),  # 1=strong buy, 5=strong sell
            "recommendation_breakdown": rec_trend,
        }

    result = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    return result


@app.skill()
async def get_insider_transactions(ticker: str, limit: int = 10) -> list[dict]:
    """
    Fetch recent insider buy/sell transactions for a ticker.

    Insider buying is a bullish signal; heavy insider selling is bearish.

    Args:
        ticker: Stock ticker symbol.
        limit:  Max number of transactions to return.

    Returns:
        List of dicts with insider name, title, transaction type, shares, and value.
    """
    app.note(f"[skill] Fetching insider transactions: {ticker}")

    def _fetch() -> list:
        t = yf.Ticker(ticker)
        try:
            df = t.insider_transactions
            if df is None or df.empty:
                return []
            records = []
            for _, row in df.head(limit).iterrows():
                records.append({
                    "insider":      str(row.get("Insider", "")),
                    "title":        str(row.get("Position", "")),
                    "transaction":  str(row.get("Transaction", "")),
                    "shares":       int(row.get("Shares", 0) or 0),
                    "value_usd":    float(row.get("Value", 0) or 0),
                    "date":         str(row.get("Start Date", row.get("Date", ""))),
                })
            return records
        except Exception:
            return []

    result = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    return result

import os
import streamlit as st
from dotenv import load_dotenv

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.tools.yfinance import YFinanceTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.calculator import CalculatorTools

load_dotenv()


INSTRUCTIONS = """You are an expert Stock Portfolio Analyst.

Your job is to analyze a user's stock portfolio and produce a clear,
actionable report. For every portfolio you receive, you should:

1. Fetch live data for each ticker using YFinanceTools
   (stock_price, stock_fundamentals, analyst_recommendations,
    company_news, historical_prices).
2. Compute each position's current market value and the overall
   portfolio value using CalculatorTools. Then compute each
   position's weight (%) in the portfolio.
3. Compute each position's unrealized P/L in absolute dollars and as
   a percentage versus the user-provided average buy price.
4. Summarize portfolio-level metrics: total cost basis, total market
   value, total unrealized P/L, and sector/asset concentration.
5. Call out risk flags: over-concentration in a single ticker or
   sector, high P/E relative to peers, recent negative news, or
   weak analyst sentiment. Use DuckDuckGoTools when you need broader
   market context that YFinance does not cover.
6. Finish with a short "Recommendations" section: 3-5 bullet points
   on rebalancing ideas, positions worth trimming, and positions
   worth adding to. Be specific but always remind the user this is
   informational, not financial advice.

Formatting rules:
- Use Markdown tables for all numerical data (holdings, fundamentals,
  analyst recommendations).
- Use bullet points for qualitative commentary.
- Keep the tone professional and concise.
"""


def build_agent(model_id: str) -> Agent:
    return Agent(
        name="Stock Portfolio Analyst",
        model=Nebius(id=model_id, api_key=os.getenv("NEBIUS_API_KEY")),
        tools=[
            YFinanceTools(
                stock_price=True,
                stock_fundamentals=True,
                analyst_recommendations=True,
                company_news=True,
                historical_prices=True,
            ),
            DuckDuckGoTools(),
            CalculatorTools(),
        ],
        instructions=[INSTRUCTIONS],
        show_tool_calls=True,
        markdown=True,
    )


def parse_portfolio(rows):
    holdings = []
    for row in rows:
        ticker = (row.get("Ticker") or "").strip().upper()
        if not ticker:
            continue
        try:
            shares = float(row.get("Shares") or 0)
            avg_price = float(row.get("Avg Buy Price") or 0)
        except ValueError:
            continue
        if shares <= 0:
            continue
        holdings.append(
            {"ticker": ticker, "shares": shares, "avg_price": avg_price}
        )
    return holdings


def format_prompt(holdings, question: str) -> str:
    lines = ["Here is my current stock portfolio:", ""]
    lines.append("| Ticker | Shares | Avg Buy Price (USD) |")
    lines.append("|--------|--------|---------------------|")
    for h in holdings:
        lines.append(f"| {h['ticker']} | {h['shares']} | {h['avg_price']} |")
    lines.append("")
    lines.append(question.strip() or "Analyze my portfolio end-to-end.")
    return "\n".join(lines)


def main() -> None:
    st.set_page_config(
        page_title="Stock Portfolio Analyst",
        page_icon="📈",
        layout="wide",
    )

    st.title("📈 Stock Portfolio Analyst")
    st.caption(
        "Agno agent + Nebius Token Factory + YFinance + DuckDuckGo + Calculator"
    )

    with st.sidebar:
        st.header("⚙️ Settings")
        model_id = st.selectbox(
            "Nebius model",
            [
                "meta-llama/Llama-3.3-70B-Instruct",
                "Qwen/Qwen3-30B-A3B",
                "deepseek-ai/DeepSeek-V3-0324",
            ],
            index=0,
        )
        if not os.getenv("NEBIUS_API_KEY"):
            st.warning("Set NEBIUS_API_KEY in your .env file.")
        st.markdown(
            "Get a key at [Nebius Token Factory](https://dub.sh/AIStudio)."
        )

    st.subheader("Your Holdings")
    default_rows = [
        {"Ticker": "AAPL", "Shares": 10, "Avg Buy Price": 150.0},
        {"Ticker": "MSFT", "Shares": 5, "Avg Buy Price": 310.0},
        {"Ticker": "NVDA", "Shares": 4, "Avg Buy Price": 420.0},
    ]
    edited = st.data_editor(
        default_rows,
        num_rows="dynamic",
        use_container_width=True,
        key="portfolio_editor",
    )

    question = st.text_area(
        "What would you like the analyst to focus on?",
        value=(
            "Give me a full portfolio review: valuation, risk, "
            "concentration, and rebalancing recommendations."
        ),
        height=100,
    )

    if st.button("Analyze Portfolio", type="primary"):
        holdings = parse_portfolio(edited)
        if not holdings:
            st.error("Add at least one holding with a ticker and shares > 0.")
            return
        if not os.getenv("NEBIUS_API_KEY"):
            st.error("NEBIUS_API_KEY is missing.")
            return

        agent = build_agent(model_id)
        prompt = format_prompt(holdings, question)

        with st.spinner("Crunching your portfolio..."):
            response = agent.run(prompt)

        st.markdown("### 📊 Analyst Report")
        st.markdown(getattr(response, "content", str(response)))


if __name__ == "__main__":
    main()

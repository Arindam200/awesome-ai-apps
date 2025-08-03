# import necessary python libraries
from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.tools.yfinance import YFinanceTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.playground import Playground, serve_playground_app
import os
from dotenv import load_dotenv
# load environment variables
load_dotenv()
# create the AI finance agent
agent = Agent(
    name="xAI Finance Agent",
    model=Nebius(
            id="meta-llama/Llama-3.3-70B-Instruct",
            api_key=os.getenv("NEBIUS_API_KEY")
    ),
    tools=[DuckDuckGoTools(), YFinanceTools(stock_price=True, analyst_recommendations=True, stock_fundamentals=True)],
    instructions = ["Always use tables to display financial/numerical data. For text data use bullet points and small paragrpahs."],
    show_tool_calls = True,
    markdown = True,
    )

# UI for finance agent
app = Playground(agents=[agent]).get_app()

if __name__ == "__main__":
    serve_playground_app("xai_finance_agent:app", reload=True)
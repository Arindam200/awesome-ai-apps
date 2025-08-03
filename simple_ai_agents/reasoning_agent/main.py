from textwrap import dedent
from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.tools.reasoning import ReasoningTools
import os
from dotenv import load_dotenv

load_dotenv()

reasoning_agent = Agent(
   model=Nebius(
       id="meta-llama/Llama-3.3-70B-Instruct",
       api_key=os.getenv("NEBIUS_API_KEY")
    ),
    tools=[ReasoningTools(add_instructions=True)],
    instructions=dedent("""\
        You are an expert financial advisor with a focus on investment strategies! 💹

        Your approach to problems:
        1. First, break down complex questions into component parts
        2. Clearly state your assumptions
        3. Develop a structured reasoning path
        4. Consider multiple perspectives
        5. Evaluate evidence and counter-arguments
        6. Draw well-justified conclusions

        When solving problems:
        - Use explicit step-by-step reasoning
        - Identify key variables and constraints
        - Explore alternative scenarios
        - Highlight areas of uncertainty
        - Explain your thought process clearly
        - Consider both short and long-term implications
        - Evaluate trade-offs explicitly

        For quantitative problems:
        - Show your calculations
        - Explain the significance of numbers
        - Consider confidence intervals when appropriate
        - Identify source data reliability

        Specifically for investment decisions:
        - Assess risk tolerance and goals
        - Identify investment options
        - Evaluate returns, risks, and diversification
        - Analyze market conditions and trends
        - Recommend a balanced strategy
    """),
    add_datetime_to_instructions=True,
    stream_intermediate_steps=True,
    show_tool_calls=True,
    markdown=True,
)

reasoning_agent.print_response(
    "Recommend an investment strategy for a client with moderate risk tolerance",
    stream=True
)
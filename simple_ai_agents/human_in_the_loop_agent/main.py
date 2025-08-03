import os
from typing import Iterator
from agno.agent import Agent
from agno.exceptions import RetryAgentRun, StopAgentRun
from agno.models.nebius import Nebius
from agno.tools import FunctionCall, tool
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt

load_dotenv()
console = Console()

MAX_RETRIES = 3
retry_counter = {"count": 0}  # For mutable retry count inside hook

# Pre-hook shared across all tools
def pre_hook(fc: FunctionCall):
    live = console._live # type: ignore
    live.stop() # type: ignore

    console.print(f"\n🔍 [bold]Preparing to run:[/bold] [cyan]{fc.function.name}[/cyan]")
    console.print(f"📦 [bold]Arguments:[/bold] {fc.arguments}")

    choice = (Prompt.ask(
        "\n🤔 Do you want to continue?",
        choices=["y", "n", "retry"],
        default="y"
    ).strip().lower())

    live.start() # type: ignore

    if choice == "n":
        console.print("❌ [red]Operation cancelled by user.[/red]")
        raise StopAgentRun("Cancelled by user", agent_message="I don't have any tool calls to make.")

    if choice == "retry":
        retry_counter["count"] += 1
        if retry_counter["count"] >= MAX_RETRIES:
            console.print("❌ [red]Maximum retries reached.[/red]")
            raise StopAgentRun("Too many retries", agent_message="Stopped after several retries.")
        console.print(f"🔄 [yellow]Retrying... (Attempt {retry_counter['count']} of {MAX_RETRIES})[/yellow]")
        raise RetryAgentRun("Retrying with new data", agent_message="Let me try again!")
    
    # Reset retry counter when user chooses to continue
    retry_counter["count"] = 0

# Tool 1: Get an interesting fact
@tool(pre_hook=pre_hook)
def get_fact(fact: str) -> Iterator[str]:
    yield fact

# Tool 2: Get a motivational quote
@tool(pre_hook=pre_hook)
def get_quote(quote: str) -> Iterator[str]:
    yield quote

# Tool 3: Get a joke
@tool(pre_hook=pre_hook)
def get_joke(joke: str) -> Iterator[str]:
    yield joke

# Initialize the agent
agent = Agent(
    description="An agent that shares fun stuff like facts, quotes, or jokes.",
    instructions="""
    You are a fun and informative agent. Use the appropriate tool to share either:
    - a fun fact
    - a motivational quote
    - or a joke

    When you get a response from a tool:
    1. For facts, start with "Here's an interesting fact: " followed by the tool's output
    2. For quotes, start with "Here's a motivational quote: " followed by the tool's output
    3. For jokes, start with "Here's a joke: " followed by the tool's output

    Ask the user before sharing, and retry only if they say so. Stop after 3 retries.

    If you have no tools to use, you should say "I don't have any tools to use."
    """,
    tools=[get_fact, get_quote, get_joke],
    markdown=True,
    model=Nebius(
        id="meta-llama/Llama-3.3-70B-Instruct",
        api_key=os.getenv("NEBIUS_API_KEY")
    )
)

# Run the agent
retry_counter["count"] = 0
agent.print_response("Share something fun!", stream=True, console=console)

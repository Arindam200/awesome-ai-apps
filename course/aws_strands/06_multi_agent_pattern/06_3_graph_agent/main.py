import logging
from strands import Agent
from strands.multiagent import GraphBuilder
from strands.models.litellm import LiteLLMModel
import os
from dotenv import load_dotenv

load_dotenv()

model = LiteLLMModel(
    client_args={
        "api_key": os.getenv("NEBIUS_API_KEY"),
    },
    model_id="nebius/zai-org/GLM-4.5",
)

# Enable debug logs
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)

researcher = Agent(
    name="researcher",
    model=model,
    system_prompt="You are a research specialist focused on gathering comprehensive data and information.",
)
analyst = Agent(
    name="analyst",
    model=model,
    system_prompt="You are a data analysis specialist who processes and interprets research data.",
)
fact_checker = Agent(
    name="fact_checker",
    model=model,
    system_prompt="You are a fact checking specialist who validates information accuracy.",
)
report_writer = Agent(
    name="report_writer",
    model=model,
    system_prompt="You are a report writing specialist who creates structured, comprehensive reports.",
)

# Build the graph
builder = GraphBuilder()

# Add nodes
builder.add_node(researcher, "research")
builder.add_node(analyst, "analysis")
builder.add_node(fact_checker, "fact_check")
builder.add_node(report_writer, "report")

# Add edges (dependencies)
builder.add_edge("research", "analysis")
builder.add_edge("research", "fact_check")
builder.add_edge("analysis", "report")
builder.add_edge("fact_check", "report")

# Set entry points (optional - will be auto-detected if not specified)
builder.set_entry_point("research")

# Optional: Configure execution limits for safety
builder.set_execution_timeout(600)  # 10 minute timeout

# Build the graph
graph = builder.build()

# Execute the graph on a task
result = graph(
    "Research the impact of AI on healthcare and create a comprehensive report"
)

# Access the results
print(f"\nStatus: {result.status}")
print(f"Execution order: {[node.node_id for node in result.execution_order]}")

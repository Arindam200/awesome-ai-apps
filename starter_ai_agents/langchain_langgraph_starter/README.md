# ReAct agent from scratch with Nebius Token Factory and LangGraph

LangGraph is a framework for building stateful LLM applications, making it a good choice for constructing ReAct (Reasoning and Acting) Agents.

ReAct agents combine LLM reasoning with action execution. They iteratively think, use tools, and act on observations to achieve user goals, dynamically adapting their approach.

While LangGraph offers a prebuilt ReAct agent (create_react_agent), it shines when you need more control and customization for your ReAct implementations.

LangGraph models agents as graphs using three key components:

State: Shared data structure (typically TypedDict or Pydantic BaseModel) representing the application's current snapshot.
Nodes: Encodes logic of your agents. They receive the current State as input, perform some computation or side-effect, and return an updated State, such as LLM calls or tool calls.
Edges: Define the next Node to execute based on the current State, allowing for conditional logic and fixed transitions.

# Example

To better understand how to implement a ReAct agent using LangGraph, let's walk through a practical example. You will create a simple agent whose goal is to use a tool to find the current weather for a specified location.

For this weather agent, its State will need to maintain the ongoing conversation history (as a list of messages) and a counter for the number of steps taken to further illustrate state management.

LangGraph provides a convenient helper, add_messages, for updating message lists in the state. It functions as a reducer, meaning it takes the current list and new messages, then returns a combined list. It smartly handles updates by message ID and defaults to an "append-only" behavior for new, unique messages.

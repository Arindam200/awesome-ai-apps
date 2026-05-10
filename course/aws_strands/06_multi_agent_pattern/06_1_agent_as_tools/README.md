# Lesson 6.1: Agent as Tools

The **Agent as Tools** pattern is a powerful way to build complex systems by creating a hierarchy of agents. It involves a main **"orchestrator"** agent that delegates tasks to a group of specialized **"worker"** agents.

## 🎯 What You'll Learn

- How to create specialized worker agents for specific domains
- How to use the `@tool` decorator to expose agents as callable tools
- How to design an orchestrator agent with intelligent routing logic
- How to chain multiple agents together for complex problem-solving
- Best practices for hierarchical agent systems

## 🏗️ Architecture Overview

```
User Query
    ↓
Orchestrator Agent (Router)
    ↓
┌─────────────────┬─────────────────┬─────────────────┐
│ Research Agent  │ Product Agent   │ Travel Agent    │
│ (Factual Info)  │ (Recommendations)│ (Itineraries)   │
└─────────────────┴─────────────────┴─────────────────┘
    ↓
Combined Response
```

## 💡 Key Concepts

### 1. **Worker Agents as Tools**

Each worker agent is an expert in a specific domain (research, travel planning, product recommendations). By decorating functions with `@tool`, we expose these agents as callable tools for the orchestrator.

### 2. **Intelligent Orchestration**

The orchestrator analyzes user queries and routes them to the most appropriate specialist(s). It can even chain multiple agents together for complex, multi-step problems.

### 3. **Hierarchical Control**

This pattern provides clear separation of concerns, making systems easier to debug, maintain, and extend.

## 📁 Code Structure

This pattern involves two main files:

### `specialized_agents.py` (The "Workers")

Defines our team of specialists. Each function is decorated with `@tool`, making the agent callable by the orchestrator.

```python
@tool
def research_assistant(query: str) -> str:
    """
    A specialized agent for research-related queries.
    Uses retrieve and http_request tools to find factual information.
    """
    print(f"--- Delegating to Research Assistant ---")
    research_agent = Agent(
        model=LLM,
        system_prompt="""You are a specialized research assistant.
        Your sole purpose is to provide factual, well-sourced information.
        Always cite your sources when possible.""",
        tools=[retrieve, http_request],
    )
    return str(research_agent(query))

@tool
def product_recommendation_assistant(query: str) -> str:
    """
    A specialized agent for product recommendations.
    Provides personalized suggestions based on user preferences.
    """
    # ... implementation details
```

### `main.py` (The "Orchestrator")

Defines the main orchestrator agent with intelligent routing logic.

```python
ORCHESTRATOR_SYSTEM_PROMPT = """
You are a master assistant that routes complex queries to a team of specialized agents.

- For research questions → Use research_assistant
- For product recommendations → Use product_recommendation_assistant
- For travel planning → Use trip_planning_assistant
- For simple questions → Answer directly

If a query requires multiple steps, call the necessary assistants in sequence.
"""

def create_orchestrator_agent() -> Agent:
    return Agent(
        model=model,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        tools=[
            research_assistant,
            product_recommendation_assistant,
            trip_planning_assistant,
        ],
    )
```

## 🚀 Running the Example

1. **Install dependencies:**

   ```bash
   uv sync
   ```

2. **Set up environment variables:**

   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run the orchestrator:**
   ```bash
   uv run python main.py
   ```

## 🎯 Example Use Cases

### Simple Query

**Input:** "What's the weather like in Tokyo?"
**Process:** Orchestrator answers directly (no delegation needed)
**Output:** Direct weather information

### Single Agent Delegation

**Input:** "I need hiking boots for a mountain trip"
**Process:** Orchestrator → Product Recommendation Agent
**Output:** Personalized boot recommendations with features and brands

### Multi-Agent Chain

**Input:** "I'm planning a hiking trip to Patagonia and need waterproof boots"
**Process:**

1. Orchestrator → Trip Planning Agent (for Patagonia context)
2. Orchestrator → Product Agent (for boot recommendations with context)
   **Output:** Comprehensive response combining travel advice and product recommendations

## ⚙️ Configuration Options

### Model Configuration

```python
model = LiteLLMModel(
    client_args={"api_key": os.getenv("NEBIUS_API_KEY")},
    model_id="nebius/moonshotai/Kimi-K2-Instruct",
)
```

### Agent Customization

Each worker agent can be customized with:

- **System prompts** for domain-specific behavior
- **Tools** for specialized capabilities
- **Model parameters** for different performance characteristics

## 🔧 Advanced Patterns

### Adding New Specialists

1. Create a new function in `specialized_agents.py`
2. Decorate it with `@tool`
3. Add it to the orchestrator's tools list
4. Update the orchestrator's system prompt

### Chaining Agents

The orchestrator can intelligently chain agents:

```python
# Complex query requiring multiple agents
user_query = "Research AI trends and create a travel itinerary for a tech conference"
# Orchestrator will call: research_assistant → trip_planning_assistant
```

### Error Handling

Each worker agent can implement its own error handling and fallback strategies.

## 🎓 Best Practices

1. **Clear Domain Boundaries**: Each worker agent should have a well-defined, non-overlapping domain
2. **Descriptive System Prompts**: The orchestrator's system prompt is crucial for proper routing
3. **Tool Documentation**: Use clear docstrings for worker agent functions
4. **Modular Design**: Keep worker agents independent and reusable
5. **Testing**: Test each worker agent individually before integration

## 🚨 Common Pitfalls

- **Overlapping Responsibilities**: Avoid agents with similar capabilities
- **Poor Routing Logic**: Vague system prompts lead to incorrect delegations
- **Tight Coupling**: Worker agents should be independent
- **Missing Error Handling**: Always handle agent failures gracefully

## 🔍 Troubleshooting

### Agent Not Being Called

- Check the orchestrator's system prompt for routing logic
- Verify the agent is included in the tools list
- Ensure the `@tool` decorator is applied correctly

### Poor Delegation Decisions

- Refine the orchestrator's system prompt
- Add more specific routing criteria
- Consider adding examples to the system prompt

### Performance Issues

- Use appropriate model sizes for each agent
- Consider caching for frequently used agents
- Monitor token usage and costs

---

### Further Learning

- **Watch the Video:** [AWS Strands Course Playlist](https://www.youtube.com/playlist?list=PLMZM1DAlf0Lrc43ZtUXAwYu9DhnqxzRKZ)
- **Read the Docs:** [Official Strands Documentation](https://strandsagents.com/latest/documentation/docs/)


---

### Navigation

| Previous Lesson                       | Next Lesson                                               |
| :------------------------------------ | :-------------------------------------------------------- |
| [Lesson 6: Multi-Agent Patterns](../) | [Sub-Lesson 6.2: Swarm Intelligence](../06_2_swarm_agent) |

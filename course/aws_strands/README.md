# AWS Strands Course for Beginners

![banner](./logo.png)

Welcome to this comprehensive hands-on course on building AI agents with the AWS Strands SDK!

This course will guide you through the fundamentals of creating powerful and flexible AI agents using Strands. We'll start with the basics and progressively build more complex and capable agents, covering everything from simple tools to advanced multi-agent systems.

## What You'll Learn

- **Agent Fundamentals**: Create, configure, and deploy AI agents
- **Tool Integration**: Connect agents to external services and APIs
- **Multi-Agent Systems**: Build complex workflows with multiple collaborating agents
- **Safety & Security**: Implement guardrails and safety measures
- **Production Patterns**: Best practices for real-world deployments

## Table of Contents

| Lesson | Topic                                                                  | Description                                                                                              |
| :----- | :--------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------- |
| 01     | [Basic Agent](./01_basic_agent)                                        | Learn how to create your first agent, configure a model, and make it perform a simple task using a tool. |
| 02     | [Session Management](./02_session_management)                          | Discover how to persist conversations and agent state, allowing for context-aware interactions.          |
| 03     | [Structured Output](./03_structured_output)                            | Extract structured data (like JSON) from unstructured text using Pydantic models.                        |
| 04     | [MCP Agent](./04_mcp_agent)                                            | Integrate external tools and services into your agent using the Multi-Capability Protocol (MCP).         |
| 05     | [Human-in-the-Loop](./05_human_in_the_loop_agent)                      | Learn how to pause agent execution to request human input or approval before continuing.                 |
| 06     | [Multi-Agent Patterns](./06_multi_agent_pattern)                       | Explore advanced patterns for building complex systems with multiple collaborating agents.               |
|        | ↳ [Agent as Tools](./06_multi_agent_pattern/06_1_agent_as_tools)       | Build an orchestrator agent that delegates tasks to specialized agents.                                  |
|        | ↳ [Swarm Intelligence](./06_multi_agent_pattern/06_2_swarm_agent)      | Create a dynamic group of agents that can hand off tasks to each other to solve complex problems.        |
|        | ↳ [Graph-Based Workflows](./06_multi_agent_pattern/06_3_graph_agent)   | Define explicit, structured workflows for multi-agent collaboration using a graph.                       |
|        | ↳ [Sequential Workflows](./06_multi_agent_pattern/06_4_workflow_agent) | Sequential multi-agent research pipelines                                                                |
| 07     | [Observability](./07_observability)                                    | Monitor and debug agents with OpenTelemetry and Langfuse                                                 |
| 08     | [Safety Guardrails](./08_guardrails)                                   | Implement safety measures and content filtering                                                          |


## Learning Path

### **Beginner Path** (Lessons 1-3)

Start here if you're new to AI agents:

- Basic Agent → Session Management → Structured Output

### **Intermediate Path** (Lessons 4-6)

Build on fundamentals with tools and multi-agent patterns:

- MCP Agent → Human-in-the-Loop → Multi-Agent Patterns

### **Advanced Path** (Lessons 7-8)

Production-ready patterns and safety:

- Observability → Safety Guardrails

## Further Learning

- **Watch this Playlist:** [AWS Strands Course Playlist](https://www.youtube.com/playlist?list=PLMZM1DAlf0Lrc43ZtUXAwYu9DhnqxzRKZ)
- **Read the Docs:** [Official Strands Documentation](https://strandsagents.com/latest/documentation/docs/)

## Getting Started

1. **Start with Lesson 01**: Navigate to `01_basic_agent` and follow the README
2. **Set up your environment**: Install dependencies and configure API keys
3. **Run the examples**: Execute the code and experiment with modifications
4. **Progress through lessons**: Follow the recommended learning path
5. **Build your own agents**: Apply what you learn to your own projects

## Contributing

Found an issue or want to improve the course? We welcome contributions!

- **Report Issues**: Use GitHub Issues for bugs and suggestions
- **Submit PRs**: Contribute improvements and new examples
- **Share Feedback**: Help us make the course better

---

**Ready to start building AI agents?** Begin with [Lesson 01: Basic Agent](./01_basic_agent) and start your journey into the world of intelligent agents!

Happy building!

# Lesson 6.4: Workflow Agent

The **Workflow Agent** pattern demonstrates how to create sophisticated multi-agent workflows using Strands. This lesson shows you how to build a complete research pipeline with specialized agents that work together to research topics, fact-check claims, and generate comprehensive reports.

## 🎯 What You'll Learn

- How to create specialized agents for different tasks (research, analysis, writing)
- How to chain agents together in a sequential workflow
- How to implement conditional logic and branching in workflows
- How to handle different types of inputs (research queries vs. fact-checking)
- How to build stateful workflows that maintain context between steps

## 🏗️ Architecture Overview

```
User Input (Research Query or Fact Claim)
    ↓
┌─────────────────────────────────────────────────────────┐
│                Multi-Agent Workflow                     │
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │ Researcher  │───▶│   Analyst   │───▶│   Writer    │ │
│  │ Agent       │    │   Agent     │    │   Agent     │ │
│  │ (Web Tools) │    │ (Verification)│    │ (Report)    │ │
│  └─────────────┘    └─────────────┘    └─────────────┘ │
│         │                   │                   │       │
│         ▼                   ▼                   ▼       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │ Web Search  │    │ Fact Check  │    │ Structured  │ │
│  │ & Sources   │    │ & Analysis  │    │ Report      │ │
│  └─────────────┘    └─────────────┘    └─────────────┘ │
└─────────────────────────────────────────────────────────┘
    ↓
Final Report with Sources
```

## 💡 Key Concepts

### 1. **Specialized Agent Roles**

Each agent has a specific role and expertise:

- **Researcher Agent**: Gathers information from web sources
- **Analyst Agent**: Verifies and analyzes information
- **Writer Agent**: Creates structured reports

### 2. **Sequential Workflow Processing**

Information flows through agents in a specific order, with each agent building upon the previous one's output.

### 3. **Context Preservation**

Each agent receives the full context from previous steps, allowing for comprehensive analysis and reporting.

### 4. **Tool Integration**

Agents can use external tools (like web requests) to gather real-time information and verify claims.

## 🚀 Implementation

This lesson includes a complete working example of a multi-agent research workflow. The implementation demonstrates:

- **Research Pipeline**: Automated research on any topic with web sources
- **Fact-Checking System**: Verification of claims with evidence analysis
- **Report Generation**: Structured output with sources and analysis

## 💻 Code Examples

### 1. **Agent Creation**

```python
# Researcher Agent with web capabilities
researcher_agent = Agent(
    model=model,
    system_prompt=(
        "You are a Researcher Agent that gathers information from the web. "
        "1. Determine if the input is a research query or factual claim "
        "2. Use your research tools (http_request, retrieve) to find relevant information "
        "3. Include source URLs and keep findings under 500 words"
    ),
    tools=[http_request],
)

# Analyst Agent for verification
analyst_agent = Agent(
    model=model,
    system_prompt=(
        "You are an Analyst Agent that verifies information. "
        "1. For factual claims: Rate accuracy from 1-5 and correct if needed "
        "2. For research queries: Identify 3-5 key insights "
        "3. Evaluate source reliability and keep analysis under 400 words"
    ),
)
```

### 2. **Workflow Execution**

```python
def run_research_workflow(user_input: str):
    """Execute the complete research workflow."""
    # Step 1: Research
    research_response = researcher_agent(
        f"Research: '{user_input}'. Use tools to find reliable sources with URLs."
    )

    # Step 2: Analysis
    analyst_response = analyst_agent(
        f"Analyze these findings about '{user_input}':\n\n{research_response}"
    )

    # Step 3: Writing
    final_report = writer_agent(
        f"Create a report on '{user_input}' based on:\n\n{analyst_response}"
    )

    return {
        "query": user_input,
        "research": str(research_response),
        "analysis": str(analyst_response),
        "report": str(final_report),
    }
```

### 3. **Conditional Workflows**

```python
def run_fact_check(claim: str):
    """Execute fact-checking workflow."""
    # Research the claim
    research = researcher_agent(
        f"Fact-check: '{claim}'. Find evidence for/against this claim with sources."
    )

    # Analyze evidence
    analysis = analyst_agent(
        f"Analyze evidence for: '{claim}'\n\nResearch: {str(research)}\n\n"
        f"Provide verdict (TRUE/FALSE/PARTIALLY TRUE), confidence level, and evidence."
    )

    # Create fact-check report
    report = writer_agent(
        f"Create fact-check report for: '{claim}'\n\nAnalysis: {str(analysis)}"
    )

    return {
        "claim": claim,
        "research": str(research),
        "analysis": str(analysis),
        "report": str(report),
    }
```

## 🎯 Use Cases

### 1. **Research Automation**

- **Topic Research**: Automatically research any topic with web sources
- **Fact Verification**: Verify claims and statements with evidence
- **Report Generation**: Create structured reports with sources and analysis

### 2. **Content Fact-Checking**

- **Claim Verification**: Check the accuracy of specific claims
- **Source Analysis**: Evaluate the reliability of information sources
- **Evidence Compilation**: Gather supporting or contradicting evidence

### 3. **Information Processing**

- **Multi-Source Research**: Combine information from multiple sources
- **Quality Assessment**: Evaluate the reliability and accuracy of information
- **Structured Output**: Generate well-formatted reports and summaries

## 🚀 Getting Started

### Prerequisites

- Complete lessons 6.1, 6.2, and 6.3
- Understanding of Strands agents and tools
- Familiarity with web APIs and HTTP requests
- Basic Python knowledge

### Installation

```bash
# Install dependencies
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Environment Setup

```bash
# Required environment variables
NEBIUS_API_KEY=your_nebius_api_key_here
```

### Running the Example

```bash
# Run the research workflow
python main.py
```

### Example Output

```
🔬 Multi-Agent Research Workflow Demo
==================================================

📝 Query: Latest developments in AI safety
✅ Research completed (1247 chars)
✅ Analysis completed (892 chars)
✅ Report completed (1156 chars)

📊 Final Report:
------------------------------
[Generated research report with sources and analysis]

==================================================

📝 Claim: OpenAI's GPT-4 was released in March 2023
✅ Research completed (987 chars)
✅ Analysis completed (654 chars)
✅ Report completed (743 chars)

📊 Fact-Check Report:
------------------------------
[Generated fact-check report with verdict and evidence]
```

## 🎓 Best Practices

### 1. **Agent Design**

- **Clear Roles**: Define specific responsibilities for each agent
- **Focused Prompts**: Write clear, task-specific system prompts
- **Tool Selection**: Choose appropriate tools for each agent's role
- **Output Formatting**: Specify desired output formats in prompts

### 2. **Workflow Management**

- **Sequential Processing**: Ensure proper order of agent execution
- **Context Passing**: Pass full context between workflow steps
- **Error Handling**: Implement proper error handling for each step
- **Progress Tracking**: Log progress through the workflow

### 3. **Performance Optimization**

- **Prompt Efficiency**: Keep prompts concise but comprehensive
- **Tool Usage**: Use tools efficiently to avoid unnecessary API calls
- **Output Limits**: Set reasonable limits on output length
- **Resource Management**: Monitor API usage and costs

## 🚨 Common Issues & Troubleshooting

### 1. **API Key Issues**

- **Problem**: `NEBIUS_API_KEY` not found or invalid
- **Solution**: Check your `.env` file and ensure the API key is correctly set

### 2. **Web Request Failures**

- **Problem**: HTTP requests failing or timing out
- **Solution**: Check network connectivity and API rate limits

### 3. **Agent Output Issues**

- **Problem**: Agents not following prompts or producing unexpected output
- **Solution**: Refine system prompts and add more specific instructions

### 4. **Context Loss**

- **Problem**: Information lost between workflow steps
- **Solution**: Ensure full context is passed between agents

## 🔧 Customization

### Adding New Agents

```python
# Create a specialized agent
custom_agent = Agent(
    model=model,
    system_prompt="Your custom agent prompt here",
    tools=[your_custom_tools],
)

# Integrate into workflow
def custom_workflow(input_data):
    # Your custom workflow logic
    result = custom_agent(input_data)
    return result
```

### Modifying Workflow Steps

```python
# Add conditional logic
def enhanced_research_workflow(user_input: str):
    if "fact-check" in user_input.lower():
        return run_fact_check(user_input)
    else:
        return run_research_workflow(user_input)
```

### Tool Integration

```python
# Add custom tools
from strands_tools import your_custom_tool

researcher_agent = Agent(
    model=model,
    system_prompt="...",
    tools=[http_request, your_custom_tool],
)
```

## 🤝 Contributing

We welcome contributions to the Workflow Agent pattern! If you're interested in contributing:

1. **Join our Discord**: [discord.gg/strands](https://discord.gg/strands)
2. **Check our GitHub**: [github.com/strands/strands](https://github.com/strands/strands)
3. **Read our Contributing Guide**: [CONTRIBUTING.md](../../CONTRIBUTING.md)

---

### Further Learning

- **Watch the Video:** [AWS Strands Course Playlist](https://www.youtube.com/playlist?list=PLMZM1DAlf0Lrc43ZtUXAwYu9DhnqxzRKZ)
- **Read the Docs:** [Official Strands Documentation](https://strandsagents.com/latest/documentation/docs/)

---

### Navigation

| Previous Lesson                                          | Next Lesson         |
| :------------------------------------------------------- | :------------------ |
| [Sub-Lesson: Graph-Based Workflows](../06_3_graph_agent) | [Observability](/course/aws_strands/07_observability) |

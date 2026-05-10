# Lesson 6.3: Graph-Based Workflows

The **Graph-Based Workflows** pattern allows you to define structured, predictable workflows for your agents using a directed acyclic graph (DAG). This gives you explicit control over the order of execution and the dependencies between agents.

## 🎯 What You'll Learn

- How to design structured, predictable multi-agent workflows
- How to use GraphBuilder to create complex agent dependencies
- How to handle parallel execution and sequential dependencies
- How to configure execution timeouts and safety parameters
- Best practices for production-ready agent workflows

## 🏗️ Architecture Overview

```
User Task
    ↓
Graph Entry Point
    ↓
┌─────────────────────────────────────────────────────────┐
│                    Graph Workflow                       │
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │ Researcher  │───▶│   Analyst   │───▶│Report Writer│ │
│  │ (Data)      │    │ (Processing)│    │ (Output)    │ │
│  └─────────────┘    └─────────────┘    └─────────────┘ │
│         │                   ▲                           │
│         │                   │                           │
│         ▼                   │                           │
│  ┌─────────────┐            │                           │
│  │Fact Checker │────────────┘                           │
│  │ (Validation)│                                         │
│  └─────────────┘                                         │
└─────────────────────────────────────────────────────────┘
    ↓
Final Result
```

## 💡 Key Concepts

### 1. **Directed Acyclic Graph (DAG)**

The workflow is represented as a graph where:

- **Nodes** represent agents or processing steps
- **Edges** represent dependencies between nodes
- **Acyclic** means no circular dependencies (no infinite loops)

### 2. **Explicit Dependencies**

You explicitly define which agents must complete before others can start, ensuring predictable execution order.

### 3. **Parallel Execution**

Independent agents can run simultaneously, improving efficiency and reducing total execution time.

### 4. **Production Reliability**

Graph-based workflows are ideal for production systems where reliability, auditability, and predictable behavior are crucial.

## 🚀 Code Example

```python
import logging
from strands import Agent
from strands.multiagent import GraphBuilder

# Enable debug logging to see execution flow
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

# Create specialized agents
researcher = Agent(
    name="researcher",
    system_prompt="You are a research specialist focused on gathering comprehensive data..."
)

analyst = Agent(
    name="analyst",
    system_prompt="You are a data analysis specialist who processes and interprets data..."
)

fact_checker = Agent(
    name="fact_checker",
    system_prompt="You are a fact checking specialist who validates information accuracy..."
)

report_writer = Agent(
    name="report_writer",
    system_prompt="You are a report writing specialist who creates structured documents..."
)

# Build the graph
builder = GraphBuilder()

# Add nodes (agents) to the graph
builder.add_node(researcher, "research")
builder.add_node(analyst, "analysis")
builder.add_node(fact_checker, "fact_check")
builder.add_node(report_writer, "report")

# Add edges (dependencies)
# Both analysis and fact_check depend on research
builder.add_edge("research", "analysis")
builder.add_edge("research", "fact_check")

# Report writer depends on both analysis and fact_check
builder.add_edge("analysis", "report")
builder.add_edge("fact_check", "report")

# Set entry point (optional - auto-detected if not specified)
builder.set_entry_point("research")

# Configure execution limits for safety
builder.set_execution_timeout(600)  # 10 minute timeout

# Build the graph
graph = builder.build()

# Execute the graph
result = graph("Research the impact of AI on healthcare and create a comprehensive report")

# Access results
print(f"Status: {result.status}")
print(f"Execution order: {[node.node_id for node in result.execution_order]}")
```

## ⚙️ Configuration Options

### Graph Building

```python
# Basic node addition
builder.add_node(agent, "node_id")

# Edge creation (dependency)
builder.add_edge("source_node", "target_node")

# Entry point configuration
builder.set_entry_point("node_id")

# Execution limits
builder.set_execution_timeout(seconds)
```

### Advanced Configuration

```python
# Custom node configuration
builder.add_node(
    agent,
    "node_id",
    timeout=300,  # Individual node timeout
    retry_count=3,  # Retry attempts
    dependencies=["node1", "node2"]  # Explicit dependencies
)

# Conditional edges
builder.add_conditional_edge(
    "source_node",
    "target_node",
    condition=lambda result: result.status == "success"
)
```

## 🎯 Example Use Cases

### Research and Report Generation

**Workflow:**

1. **Researcher** → Gathers data from multiple sources
2. **Analyst** → Processes and analyzes the data (parallel with fact_checker)
3. **Fact Checker** → Validates information accuracy (parallel with analyst)
4. **Report Writer** → Creates final report (waits for both analyst and fact_checker)

### Software Development Pipeline

**Workflow:**

1. **Requirements Analyst** → Gathers and documents requirements
2. **Architect** → Designs system architecture (parallel with tester)
3. **Tester** → Creates test plans (parallel with architect)
4. **Developer** → Implements the solution (waits for architect)
5. **Quality Assurance** → Tests the implementation (waits for developer and tester)

### Content Creation Pipeline

**Workflow:**

1. **Researcher** → Gathers topic information
2. **Writer** → Creates content (parallel with fact_checker)
3. **Fact Checker** → Validates content accuracy (parallel with writer)
4. **Editor** → Polishes the content (waits for writer and fact_checker)
5. **Publisher** → Formats and publishes (waits for editor)

## 🔧 Advanced Patterns

### Parallel Execution

```python
# These nodes can run in parallel
builder.add_edge("research", "analysis")
builder.add_edge("research", "fact_check")
# Both analysis and fact_check start after research completes
```

### Sequential Execution

```python
# These nodes run sequentially
builder.add_edge("analysis", "report")
builder.add_edge("fact_check", "report")
# Report waits for both analysis and fact_check
```

### Conditional Workflows

```python
# Add conditional logic
def should_continue(result):
    return result.quality_score > 0.8

builder.add_conditional_edge(
    "quality_check",
    "final_report",
    condition=should_continue
)
```

## 🎓 Best Practices

### 1. **Graph Design**

- **Clear Dependencies**: Define explicit, logical dependencies between agents
- **Minimize Coupling**: Keep agents as independent as possible
- **Parallel Opportunities**: Identify tasks that can run in parallel
- **Error Handling**: Plan for failure scenarios and recovery paths

### 2. **Node Configuration**

- **Descriptive IDs**: Use clear, meaningful node identifiers
- **Appropriate Timeouts**: Set reasonable timeouts for each node
- **Retry Logic**: Implement retry mechanisms for transient failures
- **Resource Management**: Consider resource constraints and limits

### 3. **Production Considerations**

- **Monitoring**: Implement comprehensive logging and monitoring
- **Auditability**: Track execution paths and decision points
- **Scalability**: Design for horizontal scaling when possible
- **Testing**: Create comprehensive test suites for workflows

## 🚨 Common Pitfalls

### 1. **Circular Dependencies**

- **Problem**: Creating cycles in the graph (A → B → C → A)
- **Solution**: Ensure the graph remains acyclic (DAG)

### 2. **Over-Complex Graphs**

- **Problem**: Creating graphs that are too complex to understand or maintain
- **Solution**: Break down complex workflows into smaller, manageable sub-graphs

### 3. **Inadequate Error Handling**

- **Problem**: Not planning for node failures or edge cases
- **Solution**: Implement comprehensive error handling and recovery strategies

### 4. **Poor Resource Management**

- **Problem**: Not considering resource constraints and limits
- **Solution**: Implement proper resource monitoring and limits

## 🔍 Troubleshooting

### Graph Execution Issues

- **Check Dependencies**: Verify all required dependencies are properly defined
- **Validate Graph**: Ensure the graph is acyclic and well-formed
- **Monitor Resources**: Check for resource constraints and bottlenecks

### Performance Problems

- **Optimize Parallel Execution**: Identify opportunities for parallel processing
- **Review Timeouts**: Adjust timeouts based on actual execution times
- **Resource Allocation**: Ensure adequate resources for all nodes

### Debugging Execution Flow

```python
# Enable detailed logging
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)

# Track execution order
result = graph("Your task here")
print(f"Execution path: {[node.node_id for node in result.execution_order]}")
print(f"Node results: {[node.result for node in result.execution_order]}")
```

## 📊 Monitoring and Analytics

### Execution Tracking

```python
# Monitor execution metrics
result = graph("Your task here")

# Execution statistics
print(f"Total execution time: {result.total_time}")
print(f"Node execution times: {result.node_times}")
print(f"Success rate: {result.success_rate}")
```

### Performance Optimization

- **Identify Bottlenecks**: Find nodes that take the longest time
- **Optimize Parallel Execution**: Look for opportunities to run nodes in parallel
- **Resource Usage**: Monitor memory and CPU usage across nodes
- **Cost Analysis**: Track token usage and API costs

---

### Further Learning

- **Watch the Video:** [AWS Strands Course Playlist](https://www.youtube.com/playlist?list=PLMZM1DAlf0Lrc43ZtUXAwYu9DhnqxzRKZ)
- **Read the Docs:** [Official Strands Documentation](https://strandsagents.com/latest/documentation/docs/)

---

### Navigation

| Previous Lesson                                       | Next Lesson                                          |
| :---------------------------------------------------- | :--------------------------------------------------- |
| [Sub-Lesson: Swarm Intelligence](../06_2_swarm_agent) | [Sub-Lesson: Workflow Agent](../06_4_workflow_agent) |

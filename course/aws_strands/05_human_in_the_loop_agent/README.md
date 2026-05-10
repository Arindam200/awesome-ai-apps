# Lesson 5: Human-in-the-Loop Agent

Human-in-the-Loop (HITL) is a critical pattern in AI agent development that enables agents to pause execution and request human input when needed. This creates safer, more interactive, and collaborative AI systems that can work alongside humans rather than operating in complete autonomy.

### What You'll Learn

- How to implement human-in-the-loop patterns in AI agents
- Using the `handoff_to_user` tool for interactive workflows
- Two key use cases: approval requests and task completion handoffs
- Best practices for building collaborative AI systems

### Prerequisites

- Basic understanding of AWS Strands framework
- Python environment with required dependencies
- API key for your chosen language model (Nebius, OpenAI, etc.)

## Use Cases

Human-in-the-loop patterns are essential for several real-world scenarios:

### 🔐 **Security-Critical Operations**

- **File system operations**: Formatting drives, deleting important files
- **Database modifications**: Dropping tables, updating critical data
- **System administration**: Restarting services, changing configurations

### 🤝 **Collaborative Decision Making**

- **Content approval**: Reviewing generated content before publishing
- **Strategy decisions**: Getting human input on business logic
- **Quality control**: Human verification of AI-generated outputs

### ❓ **Clarification and Context**

- **Ambiguous requests**: When user intent is unclear
- **Missing information**: Requesting additional details needed for task completion
- **Edge cases**: Handling situations not covered in training data

### 🎯 **Task Completion Handoffs**

- **Workflow transitions**: Passing control between different systems
- **Status updates**: Informing users of completed tasks
- **Next steps**: Guiding users on what to do after agent completion

---

## Implementation

### Code: `main.py`

This script demonstrates two fundamental use cases for the `handoff_to_user` tool:

1. **Approval Request**: Agent asks for permission before proceeding with a potentially risky operation
2. **Task Completion**: Agent completes its work and hands control back to the user

### Key Components

The implementation consists of three main functions:

- **`create_interactive_agent()`**: Sets up an agent with the `handoff_to_user` tool
- **`format_handoff_summary()`**: Formats the response for better readability
- **`main()`**: Demonstrates both use cases

## Key Concepts

### 🔧 **The `handoff_to_user` Tool**

This special tool enables agents to pause execution and request human input. When added to an agent's toolset, it provides the ability to create interactive, collaborative workflows.

### ⏸️ **Execution Control**

The tool is invoked via `agent.tool.handoff_to_user()` with two critical parameters:

| Parameter          | Type    | Description                                  |
| ------------------ | ------- | -------------------------------------------- |
| `message`          | string  | The question or prompt presented to the user |
| `breakout_of_loop` | boolean | Controls agent behavior after user response  |

### 🔄 **Execution Flow Control**

#### `breakout_of_loop=False` (Approval Mode)

- Agent pauses and waits for user input
- After receiving input, agent **continues** its execution
- Perfect for: approval requests, clarifications, additional information
- Use case: "Should I proceed with this risky operation?"

#### `breakout_of_loop=True` (Completion Mode)

- Agent pauses and waits for user input
- After receiving input, agent **stops** its execution
- Perfect for: task completion, handoffs, status updates
- Use case: "Task completed. Here's the result."

### 📊 **Response Handling**

The `handoff_to_user` function returns a structured dictionary:

```python
{
    "content": [{"text": "Agent's message to user"}],
    "userInput": [{"text": "User's response"}],
    "status": "SUCCESS",
    "toolUseId": "unique_reference_id"
}
```

### 🎯 **When to Use Human-in-the-Loop**

This pattern is essential for:

- **Safety-critical operations** (file deletion, system changes)
- **Quality control** (content review, decision validation)
- **Collaborative workflows** (human-AI teamwork)
- **Ambiguous situations** (clarification needed)

## Quick Start

### 1. **Setup Environment**

```bash
# Install dependencies
uv sync

# Set up your API key
export NEBIUS_API_KEY="your-api-key-here"
```

### 2. **Run the Example**

```bash
uv run main.py
```

### 3. **Expected Output**

You'll see two interactive scenarios:

- **Approval Request**: Agent asks for permission to format a hard drive
- **Task Completion**: Agent completes a task and hands control back to you

---

## Further Learning

### 📚 **Resources**

- **Video Tutorial**: [AWS Strands Course Playlist](https://www.youtube.com/playlist?list=PLMZM1DAlf0Lrc43ZtUXAwYu9DhnqxzRKZ)
- **Documentation**: [Official Strands Documentation](https://strandsagents.com/latest/documentation/docs/)
- **Community**: [GitHub Discussions](https://github.com/aws-strands/strands/discussions)

### 🔗 **Related Lessons**

- **Previous**: [Lesson 4: MCP Agent](/course/aws_strands/04_mcp_agent) - Model Context Protocol integration
- **Next**: [Lesson 6: Multi-Agent Patterns](/course/aws_strands/06_multi_agent_pattern) - Coordinating multiple agents

---

## Navigation

| ← Previous                                    | Next →                                                             |
| :-------------------------------------------- | :----------------------------------------------------------------- |
| [MCP Agent](/course/aws_strands/04_mcp_agent) | [Multi-Agent Patterns](/course/aws_strands/06_multi_agent_pattern) |

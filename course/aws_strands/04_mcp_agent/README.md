# Lesson 4: Extending Agents with External Tools (MCP)

In this lesson, you'll learn how to make your agent dramatically more powerful by connecting it to external tool servers using the **Multi-Capability Protocol (MCP)**.

MCP allows an agent to dynamically discover and use new tools without requiring any changes to its own code. We'll connect our agent to public servers that provide tools for searching AWS documentation, web search, and accommodation booking, turning our general-purpose agent into a specialized expert.

## 🚀 What You'll Learn

- **Dynamic Tool Discovery**: How agents can discover and use new capabilities at runtime
- **Multi-Server Integration**: Connecting to multiple MCP servers simultaneously
- **Real-time Data Access**: Using external tools to access current information
- **Error Handling**: Robust error handling for external service connections

## 📁 Files in This Lesson

- **`main.py`**: Single MCP server integration with AWS documentation
- **`multiple_mcp.py`**: Multi-MCP server integration with web search and accommodation tools

## 🔧 Key Concepts Explained

### 1. MCP Client (`MCPClient`)

The bridge between your agent and external tool servers. Configured to start servers using `uvx` or `npx`, which downloads and runs packages without manual installation.

### 2. Dynamic Tool Discovery

The magic happens inside the `with mcp_client:` block. The client:

- Starts the server process
- Connects to it via stdio
- Discovers available tools using `mcp_client.list_tools_sync()`
- Manages the server lifecycle

### 3. Agent with Dynamic Tools

Tools fetched from servers are passed directly to the `Agent` constructor. The agent learns about tools and their functions at runtime, without needing prior knowledge.

### 4. Tool-Powered Expertise

When asked questions, the agent's LLM brain:

- Sees available tools from connected servers
- Intelligently decides which tools to use
- Finds accurate, up-to-date information
- Avoids relying on potentially outdated training data

## 🛠️ Prerequisites

### Required Environment Variables

```bash
# For the language model
NEBIUS_API_KEY="your_nebius_api_key"

# For web search capabilities (multiple_mcp.py)
EXA_API_KEY="your_exa_api_key"
```

### Installation

```bash
# Install dependencies
uv sync

# Or with pip
pip install -r requirements.txt
```

## 🎯 Usage Examples

### Single MCP Server (AWS Documentation)

```python
# Run the AWS documentation agent
python main.py
```

**Example Query**: "What is the maximum invocation payload size for AWS Lambda?"

### Multiple MCP Servers (Web Search + Accommodation)

```python
# Run the multi-server agent
python multiple_mcp.py
```

**Example Queries**:

- "What's the fastest way to get to Barcelona from London?"
- "What listings are available in Cape Town for 2 people for 3 nights?"

## 🌟 Benefits of MCP

1. **Extensibility**: Add new capabilities without code changes
2. **Maintainability**: Update tools on servers, agents gain new abilities instantly
3. **Modularity**: Mix and match tools from different servers
4. **Real-time Data**: Access current information from external sources
5. **Specialization**: Transform general agents into domain experts

## 🚨 Error Handling

The enhanced code includes comprehensive error handling:

- **Configuration Errors**: Missing API keys
- **Connection Errors**: Network or server issues
- **Runtime Errors**: Unexpected failures during execution

## 🔗 Further Learning

- **Watch the Video:** [AWS Strands Course Playlist](https://www.youtube.com/playlist?list=PLMZM1DAlf0Lrc43ZtUXAwYu9DhnqxzRKZ)
- **Read the Docs:** [Official Strands Documentation](https://strandsagents.com/latest/documentation/docs/)
- **MCP Protocol:** [Model Context Protocol](https://modelcontextprotocol.io/)

## 🧭 Navigation

| Previous Lesson                                                         | Next Lesson                                                                   |
| :---------------------------------------------------------------------- | :---------------------------------------------------------------------------- |
| [Lesson 3: Structured Output](/course/aws_strands/03_structured_output) | [Lesson 5: Human-in-the-Loop](/course/aws_strands/05_human_in_the_loop_agent) |

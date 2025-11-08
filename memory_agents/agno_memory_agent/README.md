# Simple Memory Agents with Agno & Nebius

A demonstration of AI agents with persistent memory capabilities using the Agno framework and Nebius Token Factory models. This project showcases how to create intelligent agents that can remember user information across conversations and provide personalized responses.

## 🚀 Features

- **Persistent Memory**: Agents remember user information across sessions using SQLite database
- **Agentic Memory**: Agents can actively update and manage their own memories
- **User Memories**: Automatic memory creation and retrieval based on user interactions
- **Chat History**: Complete conversation history storage and retrieval
- **Streaming Responses**: Real-time streaming of agent responses with intermediate steps
- **Rich Output**: Beautiful formatted output using Rich library

## 🛠️ Prerequisites

- Python 3.11+
- Nebius API key


## 📦 Installation

1. Clone the repository and navigate to the project directory:

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd simple_ai_agents/memory_agent
```

2. Install dependencies:

```bash
uv sync
```

3. Set up your environment variables:

```bash
# Create a .env file
echo "NEBIUS_API_KEY=your_nebius_api_key_here" > .env
```

## 🔧 Configuration

The application uses the following configuration:

- **Model**: DeepSeek-V3-0324 via Nebius
- **Database**: SQLite with two tables:
  - `user_memories`: Stores user-specific memories
  - `agent_sessions`: Stores chat history
- **User ID**: Configurable user identifier for memory isolation
- **History**: Keeps last 3 conversation runs in context

## 🎯 Usage

Run the main application:

```bash
uv run main.py
```

### What the Demo Does

The application demonstrates a three-step conversation flow:

1. **Introduction**: User introduces themselves ("My name is Arindam and I support Mohun Bagan.")
2. **Location Query**: User asks for recommendations based on their location ("I live in Kolkata, where should i move within a 4 hour drive?")
3. **Memory Recall**: User asks the agent to recall information about them ("Tell me about Arindam")

After each interaction, the application displays the current memories stored about the user.

## 🏗️ Architecture

### Core Components

1. **Memory System** (`agno.memory.v2`):

   - Uses Nebius model for memory creation
   - SQLite database for persistent storage
   - Automatic memory extraction from conversations

2. **Agent Configuration**:

   - `enable_agentic_memory=True`: Allows agent to update memories
   - `enable_user_memories=True`: Automatic memory management
   - `add_history_to_messages=True`: Includes chat history in context
   - `num_history_runs=3`: Maintains last 3 conversations

3. **Storage System**:
   - SQLite-based storage for chat sessions
   - Persistent across application restarts

### Key Features Explained

- **Agentic Memory**: The agent can actively create, update, and manage memories about users
- **User Memories**: Automatically extracts and stores relevant information from conversations
- **Streaming**: Real-time response generation with intermediate step visibility
- **Memory Retrieval**: Can recall and display stored memories about specific users

## 📊 Database Schema

The application creates two main tables:

- **user_memories**: Stores extracted memories with user associations
- **agent_sessions**: Stores complete conversation history

## 🔍 Example Output

The application will show:

- Streaming agent responses
- Intermediate processing steps
- Current memories about the user after each interaction
- How memories evolve and accumulate over time

## 🎨 Customization

You can easily customize the application by:

- Changing the `user_id` for different users
- Modifying the database file path
- Adjusting the number of history runs
- Using different Nebius models
- Adding more conversation examples

## 🤝 Contributing

Feel free to contribute by:

- Adding new conversation examples
- Implementing additional memory features
- Improving the documentation
- Adding error handling and validation

## 📄 License

This project is part of the awesome-llm-apps collection.

## 🔗 Related Projects

- [Agno Framework](https://github.com/agno-ai/agno)
- [Nebius Token Factory](https://dub.sh/nebius)

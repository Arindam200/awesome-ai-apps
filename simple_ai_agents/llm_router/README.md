![Demo](./image.png)

# RouteLLM Chat with Nebius Token Factory

An intelligent AI chat application that automatically routes queries between cost-effective and high-performance models using RouteLLM. Experience cost-optimized conversations with automatic model selection that balances performance and cost.

## 🚀 Features

### 🤖 Intelligent Model Routing

- **Automatic Model Selection**: RouteLLM intelligently routes queries to the most appropriate model
- **Cost Optimization**: Uses Nebius Llama (weak model) for simpler queries, saving costs
- **Performance Balance**: Routes complex queries to GPT-4o-mini (strong model) for better quality
- **Transparent Routing**: See which model handled each query with color-coded badges

### 💬 Chat Interface

- **Modern UI**: Beautiful Streamlit interface with gradient styling
- **Chat History**: Maintains conversation context across messages
- **Model Tracking**: Visual badges showing which model processed each response
- **Real-time Feedback**: Loading spinners and status updates during processing
- **Easy Configuration**: Sidebar-based API key management

### 🎯 Key Capabilities

- **Dual Model Setup**:
  - **Strong Model**: GPT-4o-mini for complex, nuanced tasks
  - **Weak Model**: Nebius Llama 3.1 70B for cost-effective responses
- **Smart Routing**: RouteLLM's MF (Model Forwarding) router automatically selects the best model
- **Cost Savings**: Reduce API costs by routing simple queries to cheaper models
- **Seamless Experience**: Users don't need to choose models manually

## 🛠️ Tech Stack

- **Framework**: [RouteLLM](https://github.com/RouteLLM/routellm) - Intelligent model routing library
- **UI**: [Streamlit](https://streamlit.io/) - Modern web interface framework
- **Strong Model**: OpenAI GPT-4o-mini via OpenAI API
- **Weak Model**: Meta Llama 3.1 70B Instruct via Nebius Token Factory
- **API Integration**: OpenAI-compatible API for seamless provider switching

## 📋 Prerequisites

- Python 3.11 or higher
- OpenAI API key ([Get it here](https://platform.openai.com/api-keys))
- Nebius Token Factory API key ([Get it here](https://studio.nebius.ai/))
- Internet connection for API calls

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/Arindam200/awesome-llm-apps.git
cd awesome-llm-apps/simple_ai_agents/llm_router
```

### 2. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 3. Set Up Environment Variables

Create a `.env` file in the project directory:

```bash
OPENAI_API_KEY=your_openai_api_key_here
NEBIUS_API_KEY=your_nebius_api_key_here
```

**How to get your API keys:**

1. **OpenAI API Key**:

   - Visit [OpenAI Platform](https://platform.openai.com/api-keys)
   - Sign up or log in
   - Create a new API key
   - Copy it to your `.env` file

2. **Nebius API Key**:
   - Visit [Nebius Studio](https://studio.nebius.ai/)
   - Sign up or log in
   - Navigate to API keys section
   - Generate a new API key
   - Copy it to your `.env` file

### 4. Run the Application

```bash
streamlit run main.py
```

The application will start and be available at `http://localhost:8501` (or the port shown in the terminal).

## 💡 Usage

### Basic Usage

1. **Configure API Keys**: Enter your OpenAI and Nebius API keys in the sidebar
2. **Start Chatting**: Type your message in the chat input at the bottom
3. **View Responses**: See responses with model badges indicating which model handled the query
4. **Clear Chat**: Use the "Clear Chat" button to start a new conversation

### How RouteLLM Works

RouteLLM uses a **Model Forwarding (MF)** router that:

1. **Analyzes the query** to determine complexity
2. **Routes simple queries** to the weak model (Nebius Llama) for cost savings
3. **Routes complex queries** to the strong model (GPT-4o-mini) for quality
4. **Returns the response** with model information

### Example Queries

Try these example queries to see RouteLLM in action:

- **Simple queries** (likely routed to Nebius Llama):

  - "What is the capital of France?"
  - "Explain photosynthesis in one sentence"
  - "List three benefits of exercise"

- **Complex queries** (likely routed to GPT-4o-mini):
  - "Write a detailed analysis comparing Python and JavaScript for web development"
  - "Explain quantum computing concepts and their practical applications"
  - "Create a comprehensive marketing strategy for a tech startup"

## 🔧 Configuration

### Model Configuration

The application is configured with:

- **Router**: MF (Model Forwarding) - `router-mf-0.11593`
- **Strong Model**: `gpt-4o-mini` (OpenAI)
- **Weak Model**: `meta-llama/Meta-Llama-3.1-70B-Instruct` (Nebius Token Factory)

### Customization

You can modify the models in `main.py`:

```python
client = Controller(
    routers=["mf"],
    strong_model="gpt-4o-mini",  # Change strong model here
    weak_model="meta-llama/Meta-Llama-3.1-70B-Instruct",  # Change weak model here
)
```

### API Configuration

- **OpenAI Base URL**: Uses default OpenAI API endpoint
- **Nebius Base URL**: `https://api.tokenfactory.nebius.com/v1` (configured automatically)

## 🏗️ Architecture

### Core Components

#### RouteLLM Controller

The `Controller` class manages model routing:

- **Router Selection**: Uses MF router for intelligent routing
- **Model Configuration**: Defines strong and weak models
- **API Compatibility**: Works with OpenAI-compatible APIs

#### Streamlit UI

- **Sidebar**: API key configuration and information
- **Main Area**: Chat interface with message history
- **Chat Input**: User message input with real-time processing
- **Model Badges**: Visual indicators for which model processed each response

### Data Flow

1. User enters a message
2. Message is added to chat history
3. RouteLLM Controller analyzes the query
4. Router selects appropriate model (strong or weak)
5. Query is sent to selected model via API
6. Response is received and displayed
7. Model information is shown with color-coded badge

## 📊 Model Badges

The application uses color-coded badges to show which model handled each query:

- **Blue Badge** (`#667eea`): GPT-4o-mini (strong model)
- **Purple Badge** (`#764ba2`): Nebius Llama (weak model)

## 🔒 Security & Privacy

- **API Keys**: Stored securely in environment variables or session state
- **No Data Storage**: Chat history is only stored in browser session
- **Secure Transmission**: All API calls use HTTPS
- **No Logging**: Conversations are not logged or stored permanently

## 🐛 Troubleshooting

### Common Issues

1. **"Failed to initialize RouteLLM client"**

   - Ensure both API keys are correctly configured
   - Check that API keys are valid and have sufficient credits
   - Verify internet connection

2. **"Please configure your API keys"**

   - Enter API keys in the sidebar
   - Click "Save API Keys" button
   - Refresh the page if needed

3. **Model routing not working as expected**

   - RouteLLM's routing decisions are based on query complexity
   - Simple queries may still go to strong model if RouteLLM determines it's needed
   - This is expected behavior for optimal quality

4. **Import errors**
   - Ensure all dependencies are installed: `uv sync` or `pip install -e .`
   - Check Python version (3.11+ required)

### Getting Help

If you encounter issues:

1. Check that all dependencies are installed correctly
2. Verify your API keys are valid and have credits
3. Ensure you have Python 3.11+ installed
4. Check the terminal output for error messages
5. Review RouteLLM documentation for routing behavior

## 📚 Learn More

### RouteLLM

- **GitHub**: [RouteLLM Repository](https://github.com/RouteLLM/routellm)
- **Documentation**: Check RouteLLM docs for advanced configuration
- **Routing Logic**: Understand how MF router makes routing decisions

### Nebius Token Factory

- **Website**: [Nebius Token Factory](https://console.nebius.ai/)
- **Documentation**: [Nebius Docs](https://docs.tokenfactory.nebius.com/)
- **Models**: Browse available models for customization

### OpenAI

- **Platform**: [OpenAI Platform](https://platform.openai.com/)
- **Documentation**: [OpenAI API Docs](https://platform.openai.com/docs)
- **Models**: Explore available models

## 🤝 Contributing

We welcome contributions! To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is part of the [Awesome AI Apps](https://github.com/Arindam200/awesome-llm-apps) collection and is licensed under the MIT License.

## 🙏 Acknowledgments

- [RouteLLM](https://github.com/RouteLLM/routellm) for the intelligent routing framework
- [Nebius Token Factory](https://console.nebius.ai/) for providing cost-effective LLM access
- [OpenAI](https://openai.com/) for GPT-4o-mini model
- [Streamlit](https://streamlit.io/) for the web framework
- [Meta](https://ai.meta.com/) for the Llama models

---

**Built with ❤️ using intelligent model routing**

Developed by [Arindam](https://www.youtube.com/c/Arindam_1729)

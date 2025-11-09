![Nebius Chat](assets/nebius.png)
# Nebius Token Factory Chat

A powerful Streamlit-based chat interface for interacting with Nebius Token Factory's advanced language models and image generation capabilities.


## 🚀 Features

### 🤖 Chat Capabilities

- **Multi-Model Support**: Chat with DeepSeek-R1-0528 and Qwen3-235B-A22B models
- **Conversation Memory**: Maintains chat history with context awareness
- **Custom Instructions**: Set system prompts and use preset instruction templates
- **Advanced Parameters**: Fine-tune temperature, top-p, max tokens, and other generation settings
- **Thinking Visualization**: View model reasoning process with expandable thinking sections

### 🖼️ Image Generation

- **Multiple Models**: Support for Flux Schnell, Flux Dev, and SDXL models
- **Flexible Output**: Generate images in PNG, JPG, JPEG, or WebP formats
- **Advanced Controls**: Customize width, height, inference steps, negative prompts, and seeds
- **LoRA Support**: Apply custom LoRA models for specialized image generation

### 📊 Analytics & Management

- **Usage Statistics**: Track token usage, conversation counts, and average tokens per conversation
- **Export Functionality**: Download complete conversation history as JSON
- **Session Management**: Clear conversations and manage chat sessions

## 🛠️ Installation

### Prerequisites

- Python 3.11 or higher
- Nebius Token Factory API key

### Setup

1. **Clone the repository**

   ```bash
   git clone git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd simple_ai_agents/nebius-chat
   ```

2. **Install dependencies**

   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -r requirements.txt
   ```

3. **Environment Setup**

   ```bash
   # Create .env file
   echo "NEBIUS_API_KEY=your_api_key_here" > .env
   ```

4. **Run the application**
   ```bash
   streamlit run app.py
   ```

## 🔧 Configuration

### API Key Setup

1. Sign up at [Nebius Token Factory](https://console.nebius.ai/ai/llm)
2. Generate your API key from the console
3. Add the key to your `.env` file or enter it in the sidebar

### Model Selection

- **DeepSeek-R1-0528**: General-purpose model with strong reasoning capabilities
- **Qwen3-235B-A22B**: Large multilingual model with advanced capabilities

### Image Generation Models

- **Flux Schnell**: Fast image generation with high quality
- **Flux Dev**: Development version with latest features
- **SDXL**: Stable Diffusion XL for high-resolution images

## 📖 Usage

### Chat Mode

1. Select "Chat" from the tool selector
2. Choose your preferred model
3. Adjust generation parameters (temperature, top-p, max tokens)
4. Set custom instructions or use preset templates
5. Start chatting with the AI assistant

### Image Generation Mode

1. Select "Image Generation" from the tool selector
2. Choose an image generation model
3. Configure image parameters (size, format, inference steps)
4. Enter your prompt and optional negative prompt
5. Generate and download your images

### Custom Instructions

Use preset templates or create custom system prompts:

- **Default**: General AI assistant
- **Creative Writer**: Storytelling and narrative assistance
- **Business Assistant**: Professional business advice
- **Language Tutor**: Language learning support
- **Technical Expert**: Technical information and solutions

## 🏗️ Architecture

### Core Components

#### `NebiusStudioChat` Class

- **API Integration**: Handles all Nebius Token Factory API communications
- **Conversation Management**: Maintains chat history and context
- **Image Generation**: Manages image generation requests
- **Usage Tracking**: Monitors token usage and statistics

#### Key Methods

- `send_message()`: Process chat completions
- `generate_image()`: Handle image generation requests
- `export_conversation()`: Export chat history
- `get_usage_stats()`: Calculate usage statistics

### UI Components

- **Streamlit Interface**: Modern, responsive web interface
- **Sidebar Configuration**: Model selection and parameter tuning
- **Chat Display**: Real-time message rendering with thinking visualization
- **Image Gallery**: Generated image display and download

## 🔌 API Integration

### Chat Completions

```python
POST https://api.tokenfactory.nebius.com/v1/chat/completions
```

### Image Generation

```python
POST https://api.tokenfactory.nebius.com/v1/images/generations
```

### Supported Parameters

- **Temperature**: 0.0-1.0 (creativity control)
- **Top-p**: 0.1-1.0 (nucleus sampling)
- **Max Tokens**: 50-500 (response length)
- **Presence Penalty**: 0.63 (default)
- **Top-k**: 51 (default)

## 📊 Usage Statistics

The application tracks comprehensive usage metrics:

- Total conversations
- Token usage (prompt, completion, total)
- Average tokens per conversation
- Model-specific statistics

## 🚀 Deployment

### Local Development

```bash
streamlit run app.py
```

### Production Deployment

1. Set up environment variables
2. Configure reverse proxy (nginx)
3. Use process manager (PM2, systemd)
4. Enable HTTPS with SSL certificates

### Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501"]
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Nebius Token Factory](https://console.nebius.ai/) for providing the API
- [Streamlit](https://streamlit.io/) for the web framework
- [DeepSeek](https://www.deepseek.com/) and [Qwen](https://qwen.ai/) for the language models

## 📞 Support

For support and questions:

- Create an issue in the repository
- Check the [Nebius Token Factory documentation](https://docs.tokenfactory.nebius.com/)
- Review the application logs for debugging

## 🔄 Changelog

### Version 0.1.0

- Initial release with chat and image generation capabilities
- Support for DeepSeek and Qwen models
- Basic conversation management and export features
- Streamlit-based user interface

# DeepSeek Finance Agent 🐳

A powerful AI-powered finance agent built with the Agno framework that provides real-time financial data, stock analysis, and market insights using natural language queries.

## 🚀 Features

- **Real-time Stock Data**: Get current stock prices, historical data, and market trends
- **Financial Analysis**: Access analyst recommendations and fundamental data
- **Web Search**: Search for the latest financial news and market information
- **Interactive UI**: Beautiful web interface for easy interaction
- **Structured Output**: Financial data displayed in organized tables and bullet points

## 🛠️ Tech Stack

- **Framework**: [Agno](https://www.agno.com/) - Modern AI agent framework
- **LLM Model**: DeepSeek-V3-0324 via Nebius AI Studio
- **Financial Data**: [YFinance](https://pypi.org/project/yfinance/) - Yahoo Finance API wrapper
- **Web Search**: [DuckDuckGo](https://duckduckgo.com/) - Privacy-focused search engine
- **UI**: Agno Playground - Interactive web interface

## 📋 Prerequisites

- Python 3.10 or higher
- Nebius AI Studio API key
- Internet connection for real-time data

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/simple_ai_agents/finance_agent
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Create a `.env` file in the project directory:

```bash
NEBIUS_API_KEY=your_nebius_api_key_here
```

**How to get your Nebius API key:**

1. Visit [Nebius AI Studio](https://dub.sh/AIStudio)
2. Sign up or log in to your account
3. Navigate to the API section
4. Generate a new API key
5. Copy the key to your `.env` file

### 4. Run the Application

```bash
python main.py
```

The application will start and be available at `http://localhost:8000` (or the port shown in the terminal).

## 💡 Usage Examples

Once the application is running, you can interact with the finance agent using natural language queries like:

- **"What's the current stock price of Apple?"**
- **"Show me analyst recommendations for Tesla"**
- **"Get the latest financial news about cryptocurrency"**
- **"What are the fundamentals of Microsoft stock?"**
- **"Compare the performance of Google and Amazon stocks"**

## 🔧 Configuration

The agent is configured with the following features:

- **Model**: Meta Llama-3.3-70B-Instruct (70B parameter model)
- **Tools**:
  - YFinance Tools (stock prices, analyst recommendations, fundamentals)
  - DuckDuckGo Tools (web search for latest information)
- **Display**: Tables for financial data, bullet points for text
- **UI**: Interactive web playground with real-time responses

## 📊 Available Tools

### YFinance Tools

- **Stock Price**: Real-time and historical stock prices
- **Analyst Recommendations**: Buy/sell/hold recommendations from financial analysts
- **Stock Fundamentals**: P/E ratios, market cap, revenue, earnings, and more

### DuckDuckGo Tools

- **Web Search**: Search for latest financial news and market information
- **Privacy-focused**: No tracking or personal data collection

## 🎯 Example Queries

Here are some example queries you can try with the finance agent:

```
"What's the current price of AAPL stock?"
"Show me analyst recommendations for TSLA"
"Get the latest news about Bitcoin"
"What are the fundamentals of MSFT?"
"Compare GOOGL and AMZN performance over the last month"
"What's the market cap of NVIDIA?"
"Show me the P/E ratio of Amazon"
"Get the latest earnings report for Apple"
```

## 🔒 Security & Privacy

- **API Keys**: Stored securely in environment variables
- **No Data Storage**: The agent doesn't store your queries or personal data
- **Privacy**: Uses DuckDuckGo for web searches (no tracking)

## 🐛 Troubleshooting

### Common Issues

1. **API Key Error**: Make sure your `NEBIUS_API_KEY` is correctly set in the `.env` file
2. **Port Already in Use**: The application will automatically find an available port
3. **Network Issues**: Ensure you have a stable internet connection for real-time data

### Getting Help

If you encounter any issues:

1. Check that all dependencies are installed correctly
2. Verify your API key is valid and has sufficient credits
3. Ensure you have Python 3.10+ installed
4. Check the terminal output for error messages

## 🤝 Contributing

We welcome contributions! To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is part of the [Awesome AI Apps](https://github.com/Arindam200/awesome-ai-apps) collection and is licensed under the MIT License.

## 🙏 Acknowledgments

- [Nebius AI Studio](https://dub.sh/AIStudio) for providing the LLM infrastructure
- [Agno](https://www.agno.com/) for the powerful agent framework
- [YFinance](https://pypi.org/project/yfinance/) for financial data access
- [DuckDuckGo](https://duckduckgo.com/) for privacy-focused web search

---

**Built with ❤️ using modern AI technologies**

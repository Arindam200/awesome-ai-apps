# Brand Reputation Monitor

A powerful AI-powered brand reputation monitoring tool that analyzes news coverage, sentiment, and brand insights to help businesses track their reputation in real-time. This application uses Nebius Token Factory for intelligent analysis, Memori for persistent context, Bright Data for real-time web scraping, and Agno agents for comprehensive brand intelligence.

## Features ✨

📰 **News Analysis**: Real-time monitoring of news articles and press coverage about your brand  
💭 **Sentiment Analysis**: AI-powered sentiment tracking (positive, negative, neutral)  
🔍 **Brand Insights**: Actionable insights extracted from news and public perception  
🤖 **Conversational AI**: Natural chat interface with Nebius Token Factory-powered follow-up questions  
💾 **Memory Integration**: Stores conversation context using Memori with SQLite for persistent learning  
🌐 **Real-Time Web Scraping**: Uses Bright Data to extract current news and brand data  
🎯 **Keyword-Based Monitoring**: Custom search queries for targeted brand tracking  
📱 **Interactive Chat**: Natural conversation flow with contextual responses  
🔄 **Context-Aware Responses**: Searches memory before answering for consistent insights  
⚙️ **Easy Configuration**: Simple setup with API keys via intuitive sidebar  
🔒 **Evidence-Based Analysis**: Only includes real URLs and sources from actual web research  

## Prerequisites 🛠️

- Python 3.10+
- Nebius Token Factory API key ([Get it here](https://studio.nebius.ai/))
- Bright Data API credentials
- SQLite (included with Python)

## Installation 📥

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/brand-reputation-monitor.git
cd memory_agents/brand_reputation_monitor
```

2. **Install the required dependencies:**
```bash
pip install -r requirements.txt
```

3. **Create a `.env` file in the project root and add your API credentials:**
```env
# Nebius Token Factory Configuration
NEBIUS_API_KEY=your_nebius_api_key

# Bright Data Configuration
BRIGHTDATA_API_KEY=your_brightdata_api_key
```

> **Note:** This application uses **Nebius Token Factory** for intelligent brand analysis. Get your API key from [Nebius Token Factory](https://studio.nebius.ai/).

## Usage 🚀

1. **Start the Streamlit application:**
```bash
streamlit run app.py
```

2. **Open your web browser** and navigate to the provided local URL (typically `http://localhost:8501`)

3. **Configure your API keys** in the sidebar:
   - Nebius Token Factory API Key
   - Bright Data API Key
   - Click "Save API Keys"

4. **Start monitoring your brand:**
   - Enter your company name
   - Provide search keywords (e.g., "apple news, apple reviews, apple controversy")
   - Let the AI analyze and provide insights
   - Ask follow-up questions about the results

## How It Works 🔄

### 1. Brand Monitoring Workflow

The application uses a sophisticated workflow to monitor and analyze brand reputation:

#### **News Collection**
- Searches Google News for relevant articles using your keywords
- Scrapes news pages to extract comprehensive content
- Identifies the most relevant articles for brand reputation monitoring

#### **Content Analysis**
- Scrapes individual news articles for detailed content
- Uses AI to extract titles, summaries, and sentiment
- Generates actionable insights about brand reputation

#### **Sentiment Analysis**
- Analyzes sentiment as positive, negative, or neutral
- Provides context for sentiment drivers
- Tracks sentiment patterns across different news sources

#### **Insight Generation**
- Extracts 3-5 actionable insights per article
- Focuses on brand reputation implications
- Provides concise, strategic recommendations

### 2. Conversation Flow

**Step 1: Company Introduction**
- System asks for your company name
- Stores context for personalized monitoring

**Step 2: Keyword Configuration**
- Specify search keywords for brand monitoring
- Examples: "company news", "company reviews", "company controversy"
- System validates and processes keywords

**Step 3: Real-Time Analysis**
- AI system performs comprehensive web research using Bright Data
- Scrapes news articles and analyzes content
- Generates detailed brand reputation report
- All findings stored in Memori for future reference

**Step 4: Interactive Follow-Up**
- Ask questions about the analysis results
- Request clarification on insights or sentiment
- System searches Memori before answering for consistency
- All conversations tracked for context-aware responses

## Example Workflow 🔄

1. **Launch App**: Open the application and enter your API keys
2. **Enter Company**: "Apple"
3. **Set Keywords**: "apple news, apple reviews, apple controversy, apple announcement"
4. **AI Analysis**: System scrapes and analyzes relevant news articles
5. **Review Report**: Receive detailed analysis with sentiment and insights
6. **Follow-Up**: Ask questions like "What's the overall sentiment?" or "What are the main concerns?"
7. **New Analysis**: Request analysis with different keywords or ask for deeper insights

## Brand Analysis 📊

The AI system analyzes your brand across multiple dimensions:

### News Coverage Analysis
📰 **Article Titles**: Key headlines mentioning your brand  
📝 **Content Summaries**: Concise summaries of news content  
🔗 **Source URLs**: Direct links to original articles  
📊 **Coverage Volume**: Number of articles and mentions  

### Sentiment Analysis
😊 **Positive Sentiment**: Positive news and favorable coverage  
😞 **Negative Sentiment**: Critical coverage and negative mentions  
😐 **Neutral Sentiment**: Factual reporting without bias  
📈 **Sentiment Trends**: Patterns in sentiment over time  

### Brand Insights
💡 **Strategic Insights**: Actionable recommendations for brand management  
⚠️ **Risk Indicators**: Potential reputation risks and concerns  
🎯 **Opportunity Areas**: Positive trends and growth opportunities  
📋 **Action Items**: Specific steps to improve brand reputation  

## API Configuration 🔑

### Nebius Token Factory
- **Model**: Qwen/Qwen3-Coder-480B-A35B-Instruct (via Nebius Token Factory)
- **Purpose**: News analysis, sentiment analysis, and insight generation
- **Framework**: Agno agents for structured AI interactions
- **Get API Key**: [Nebius Token Factory](https://studio.nebius.ai/)

### Bright Data
- **SERP Zone**: `sdk_serp` (for Google News searches)
- **Web Unlocker Zone**: `unlocker` (for article scraping)
- **Purpose**: Real-time web data extraction
- **Scope**: News websites, press releases, media coverage

### Memori with SQLite
- **Database**: SQLite (local file: `memori.db`)
- **Purpose**: Persistent conversation memory and context storage
- **Features**: Automatic context search, conversation tracking
- **Advantage**: No external database setup required

## Architecture 🏗️

### Modular Design
- **UI Layer** (`app.py`): Streamlit interface and conversation flow
- **Workflow Layer** (`workflow.py`): Core brand monitoring functions
- **Memory Layer**: Memori integration for context persistence
- **Scraping Layer**: Bright Data tools for web research

### Key Components
1. **Conversation Manager**: Handles user interaction and flow states
2. **Brand Analysis Engine**: Nebius Token Factory-powered news analysis with Agno agents
3. **Web Research Engine**: Bright Data integration for real-time scraping
4. **Memory System**: Memori for context storage and retrieval
5. **Context Search**: Automatic memory search before responding

## Intelligence Features 📱

### Keyword-Based Monitoring ✅
- Custom search queries for targeted brand tracking
- Flexible keyword combinations for comprehensive coverage
- Real-time news aggregation and analysis
- Focused reputation monitoring

### Source Verification ✅
- Only includes exact URLs actually scraped
- Never fabricates or adds placeholder sources
- Complete transparency in research sources
- Direct links to original news articles

### Memory-First Approach ✅
- Always searches Memori before answering
- Maintains conversation context across sessions
- Provides consistent insights over time
- Learns from all previous analyses

## Example Use Cases 💡

### Brand Monitoring
- "Monitor Apple's reputation with keywords: apple news, apple reviews"
- "Track Tesla's sentiment with: tesla news, tesla controversy, tesla stock"
- "Analyze Microsoft's brand perception with: microsoft news, microsoft reviews"

### Crisis Management
- "What's the current sentiment about our brand?"
- "Are there any negative mentions we should address?"
- "What are the main concerns mentioned in recent news?"

### Competitive Analysis
- "Compare our sentiment to competitor X"
- "What are customers saying about our brand vs competitors?"
- "How is our brand performing in the news compared to last month?"

### Follow-Up Analysis
- "Explain the insights from the analysis"
- "What company are we analyzing?"
- "What keywords did we search for?"
- "Can you summarize the key findings?"

## File Structure 📁

```
brand-reputation-monitor/
├── app.py                 # Main Streamlit application
├── workflow.py           # Core brand monitoring functions
├── config.json           # Default configuration
├── requirements.txt      # Python dependencies
├── README.md            # This file
├── assets/              # Logo and image files
│   ├── gibson.svg       # GibsonAI logo
│   └── brightdata_logo.png
└── memori.db           # SQLite database (created automatically)
```

## Contributing 🤝

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Troubleshooting 🔧

### API Key Errors
- Check API keys are correctly entered in sidebar
- Verify environment variables in `.env` file
- Ensure both Nebius Token Factory and Bright Data keys are valid
- Get Nebius Token Factory API key from [Nebius Token Factory](https://studio.nebius.ai/)

### Bright Data Issues
- Ensure Bright Data API key is valid and has credits
- Check internet connection for web scraping
- Verify Bright Data zones are properly configured

### Memori Initialization
- SQLite database created automatically on first use
- Check file permissions in project directory
- Database file `memori.db` should be created automatically

### Analysis Performance
- First analysis may take 2-5 minutes (web research)
- Ensure Bright Data has sufficient credits
- Check internet connection for web scraping
- Large keyword lists may take longer to process

## License 📄

This project is licensed under the MIT License - see the LICENSE file for details.
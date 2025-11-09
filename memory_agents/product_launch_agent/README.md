# Smart Product Launch Agent

A powerful AI-powered competitive intelligence tool that analyzes competitor product launches, market sentiment, and launch metrics to help founders make data-driven launch decisions. This application uses multi-agent AI architecture with Memori for persistent context, Bright Data for real-time web scraping, and OpenAI GPT-4o for intelligent analysis.

## Features ✨

**Product Launch Analysis**: Deep evaluation of competitor positioning, launch tactics, strengths, and weaknesses  
**Market Sentiment Analysis**: Real-time social media sentiment tracking and customer feedback analysis  
**Launch Metrics Analysis**: Track competitor KPIs, adoption rates, press coverage, and performance indicators  
**Multi-Agent AI System**: Specialized AI agents coordinating for comprehensive competitive intelligence  
**Memory Integration**: Stores conversation context using Memori with MongoDB for long-term learning  
**Real-Time Web Scraping**: Uses Bright Data to extract current competitor data from the web  
**Competitor Relevance Validation**: Automatically verifies competitor relevance before analysis  
**Conversational Interface**: Natural chat experience with follow-up question support  
**Context-Aware Responses**: Searches memori before answering for accurate, consistent insights  
**Easy Configuration**: Simple setup with API keys via intuitive sidebar  
**Evidence-Based Analysis**: Only includes real URLs and sources from actual web research  

## Prerequisites 🛠️

- Python 3.10+
- Nebius Token Factory API key ([Get it here](https://studio.nebius.ai/))
- [MemoriSDK](https://github.com/GibsonAI/memori) 
- Bright Data API credentials
- MongoDB (local or cloud instance)

## Installation 📥

1. **Clone the repository:**
```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd memory_agents/product_launch_agent
```

2. **Install the required dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up MongoDB:**
   - Install MongoDB locally or use MongoDB Atlas
   - Default connection: `mongodb://localhost:27017/` or use your mongoDB connection sting
   - The database `memori` will be created automatically on first run

4. **Create a `.env` file in the project root and add your API credentials:**
```env
# Nebius AI Configuration
NEBIUS_API_KEY=your_nebius_api_key

# Bright Data Configuration
BRIGHTDATA_API_KEY=your_brightdata_api_key
BRIGHT_DATA_SERP_ZONE=sdk_serp
BRIGHT_DATA_UNLOCKER_ZONE=unlocker
```

> **Note:** This application uses **Nebius Token Factory** for powering the AI agents. Get your API key from [Nebius Token Factory](https://studio.nebius.ai/).

## Usage 🚀

1. **Start MongoDB** (if running locally):
```bash
# MongoDB should be running on localhost:27017
mongod
```

2. **Start the Streamlit application:**
```bash
streamlit run chat_app.py
```

3. **Open your web browser** and navigate to the provided local URL (typically `http://localhost:8501`)

4. **Configure your API keys** in the sidebar:
   - Bright Data API Key
   - Nebius API Key
   - Click "Save API Keys"

## How It Works 🔄

### 1. Product Intelligence Team (Multi-Agent System)

The application uses three specialized AI agents that coordinate to provide comprehensive competitive intelligence:

#### **Product Launch Analyst**
- Evaluates competitor positioning and Go-To-Market strategy
- Identifies launch tactics that drove success
- Pinpoints execution weaknesses and gaps
- Provides actionable strategic insights

#### **Market Sentiment Specialist**
- Analyzes social media sentiment (Twitter/X, Reddit, Product Hunt)
- Tracks customer reviews and feedback patterns
- Monitors brand perception across platforms
- Identifies positive and negative sentiment drivers

#### **Launch Metrics Specialist**
- Tracks user adoption and engagement metrics
- Analyzes press coverage and media attention
- Measures market penetration and growth rates
- Benchmarks performance against industry standards

### 2. Conversation Flow

**Step 1: Introduction**
- System asks about your company and product
- Stores your context for personalized analysis

**Step 2: Analysis Selection**
- Choose from three analysis types:
  1. Product Launch Analysis
  2. Market Sentiment Analysis
  3. Launch Metrics Analysis
- Specify the competitor you want to analyze

**Step 3: AI Research**
- Multi-agent system performs real-time web research using Bright Data
- Scrapes competitor websites, news, reviews, and social media
- Analyzes data and generates comprehensive report
- All findings stored in Memori for future reference

**Step 4: Follow-Up & Deep Dive**
- Ask follow-up questions about the analysis
- Request additional competitor analyses
- System searches Memori before answering for consistency
- All conversations tracked for context-aware responses

## Example Workflow 🔄

1. **Launch App**: Open the application and enter your API keys
2. **Introduce Product**: "I'm building a project management tool for remote teams"
3. **Request Analysis**: "I want a Product Launch Analysis for Monday.com"
4. **AI Research**: System scrapes web data and analyzes Monday.com's launch
5. **Review Report**: Receive detailed analysis with positioning, strengths, weaknesses, and insights
6. **Follow-Up**: Ask questions like "What were their main marketing channels?"
7. **Next Analysis**: Request analysis of another competitor or different analysis type

## Architecture 🏗️

### Modular Design
- **UI Layer** (`chat_app.py`): Streamlit interface and conversation flow
- **Agent Layer** (`agent.py`): Multi-agent AI system and coordination
- **Memory Layer**: Memori integration for context persistence
- **Scraping Layer**: Bright Data tools for web research

### Key Components
1. **Conversation Manager**: Handles user interaction and flow states
2. **Multi-Agent Team**: Coordinates specialized AI agents
3. **Web Research Engine**: Bright Data integration for real-time scraping
4. **Memory System**: Memori for context storage and retrieval
5. **Context Search**: Automatic memory search before responding

## Intelligence Features 📱

### Competitor Validation ✅
- Verifies competitor relevance before analysis
- Rejects irrelevant comparisons (e.g., Spotify vs Google)
- Suggests relevant alternatives in the same market
- Ensures high-quality, actionable insights

### Source Verification ✅
- Only includes exact URLs actually crawled
- Never fabricates or adds placeholder sources
- No Twitter/X links unless data actually obtained from Twitter
- Complete transparency in research sources

### Memory-First Approach ✅
- Always searches Memori before answering
- Maintains conversation context across sessions
- Provides consistent insights over time
- Learns from all previous analyses

## Example Use Cases 💡

### Pre-Launch Research
- "Analyze how Notion launched their product"
- "What sentiment does Figma have among designers?"
- "Show me Airtable's launch metrics and growth"

### Competitive Intelligence
- "Compare Slack's launch strategy to our approach"
- "What are users saying about Linear on Product Hunt?"
- "How did Superhuman achieve their early traction?"

### Strategy Refinement
- "What weaknesses did Zoom have at launch that we can avoid?"
- "Which launch tactics worked best for Calendly?"
- "How should we position against Miro based on their reception?"

### Follow-Up Analysis
- "Tell me more about their pricing strategy"
- "What were their main distribution channels?"
- "How did they handle negative feedback?"

## Contributing 🤝

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License 📄

This project is licensed under the MIT License - see the LICENSE file for details.



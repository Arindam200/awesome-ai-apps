# Conference-Agnostic CFP Generation/RAG System

A powerful, conference-agnostic RAG (Retrieval-Augmented Generation) application that automatically crawls any conference website, builds a searchable corpus, and generates unique talk proposals using real-time research and historical context.

## ✨ Key Features

- **🌐 Universal Conference Support**: Automatically crawls Sched.com, Sessionize.com, and generic conference websites
- **⚡ Parallel Processing**: High-performance async crawling with rate limiting and batch processing
- **🔍 Intelligent Search**: Vector search with automatic fallback to text-based similarity matching
- **🔬 Real-time Research**: Integrates live web research using Exa and Tavily APIs
- **🤖 Smart Proposals**: Generates unique talk proposals using Nebius Token Factory's advanced LLMs
- **📊 Analytics Dashboard**: Conference statistics, category distributions, and corpus insights
- **🎯 Multi-Platform**: Streamlit web interface with comprehensive conference management

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Streamlit     │    │   Conference     │    │   Real-time     │
│   Interface     │───▶│   Crawler        │───▶│   Research      │
│                 │    │                  │    │   (Exa/Tavily)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Couchbase     │    │   Vector Search  │    │   LLM Generation│
│   Corpus        │◀───│   & Analytics    │───▶│   (Nebius Token Factory)   │
│   Management    │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Couchbase Server with Vector Search capabilities
- API keys for Nebius Token Factory, Exa, and Tavily (see Environment Setup)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd conference-talk-abstract-generator
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys and Couchbase credentials
```

4. **Run the application**
```bash
python main.py
```

The Streamlit interface will open at `http://localhost:8501`

## 🔧 Environment Setup

Create a `.env` file with the following configuration:

```env
# Nebius Token Factory Configuration (for chat completions and embeddings)
NEBIUS_API_KEY=your_nebius_api_key_here
NEBIUS_API_BASE=https://api.studio.nebius.com/v1/

# Research APIs (Optional - for web research functionality)
EXA_API_KEY=your_exa_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

# Couchbase Cloud Configuration
CB_CONNECTION_STRING=couchbases://your-cluster.cloud.couchbase.com
CB_USERNAME=your_username
CB_PASSWORD=your_secure_password
CB_BUCKET=conferences
CB_SEARCH_INDEX_PATTERN=vector_search_talks_{conference_id}
# Note: Collections are created dynamically per conference (e.g., talks_kubecon2024)
# Note: Per-conference vector search index; ensure index dimensions match EMBEDDING_MODEL

### Supported LLM Models

The system uses Nebius Token Factory models:
- **openai/gpt-oss-120b** (Primary chat model for generating talk proposals)

### Embedding Models

- **Qwen/Qwen3-Embedding-8B** (4096 dimensions) - Primary embedding model for vector search

## 📱 Using the Application

### 1. Add a Conference

1. Navigate to the **"Add Conference"** tab
2. Enter any conference schedule URL:
   - `https://kccncna2024.sched.com/`
   - `https://sessionize.com/dotnetconf-2024/`
   - Any conference website with a schedule
3. Configure crawling options (batch size, rate limiting)
4. Click **"Crawl Conference"**

The system will:
- Automatically detect the platform (Sched, Sessionize, etc.)
- Extract conference metadata
- Crawl all talk pages in parallel
- Generate embeddings for vector search
- Store everything in Couchbase

### 2. Generate Talk Proposals

1. Go to the **"Generate Proposal"** tab
2. Select a stored conference
3. Describe your talk idea
4. Configure generation options:
   - Number of similar talks to find
   - Enable/disable real-time research
   - Creativity level and response length
5. Click **"Generate Talk Proposal"**

The system will:
- Research current trends (if enabled)
- Find similar historical talks
- Generate a unique, compelling proposal
- Show all context used in generation

### 3. View Analytics

1. Visit the **"Analytics"** tab
2. Select a conference to analyze
3. View:
   - Total talks and metadata
   - Category distribution charts
   - Technical details and embeddings info

## 🛠️ Supported Conference Platforms

### Sched.com
- **Examples**: KubeCon, DockerCon, many tech conferences
- **URL Pattern**: `*.sched.com`
- **Features**: Full schedule parsing, speaker details, categories

### Sessionize.com
- **Examples**: .NET Conf, many Microsoft events
- **URL Pattern**: `sessionize.com/*`
- **Features**: API-based extraction, rich metadata

### Generic Websites
- **Examples**: Custom conference sites, WordPress events
- **Detection**: HTML pattern analysis
- **Features**: Best-effort extraction using BeautifulSoup

## 📊 Couchbase Setup

### 1. Create Bucket and Collections

The system automatically creates collections as needed, but you can pre-create:

```sql
-- Create main bucket
CREATE BUCKET `conferences`;

-- Collections are auto-created as `talks_{conference_id}`
```

### 2. Vector Search Index

Indexes are automatically created with optimal settings:

```json
{
  "name": "vector_search_talks_{conference_id}",
  "type": "fulltext-index",
  "params": {
    "mapping": {
      "types": {
        "_default.talks_{conference_id}": {
          "properties": {
            "embedding": {
              "fields": [{
                "name": "embedding",
                "type": "vector",
                "dims": 4096,
                "similarity": "dot_product"
              }]
            }
          }
        }
      }
    }
  }
}
```

## 🎯 Example Use Cases

### Technology Research
```
Input: "Advanced OpenTelemetry patterns for distributed tracing"
Output: Comprehensive proposal with current best practices and historical context
```

### Implementation Stories
```
Input: "Migrating from Prometheus to Grafana Cloud"
Output: Real-world migration guide with lessons learned
```

### Emerging Trends
```
Input: "WebAssembly in Kubernetes workloads"
Output: Cutting-edge proposal combining latest research with practical applications
```

## 📁 Project Structure

```
conference-talk-abstract-generator/
├── main.py                          # Application entry point
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment template
├── docker-compose.yml              # Optional Docker setup
├── scripts/
│   └── create_search_indexes.py    # Manual index creation utility
├── src/
│   ├── config/
│   │   └── nebius_client.py        # Nebius Token Factory client configuration
│   ├── scrapers/
│   │   ├── conference_detector.py  # Platform detection logic
│   │   ├── platform_adapters.py    # Platform-specific parsers
│   │   └── parallel_crawler.py     # Main crawling engine
│   ├── models/
│   │   └── corpus_manager.py       # Couchbase & vector operations
│   ├── research/
│   │   └── adk_research_agent.py   # Real-time research integration
│   └── ui/
│       ├── conference_talk_app.py  # Main Streamlit interface
│       └── prompts.py              # LLM prompt templates
```

## 🔍 Technical Deep Dive

### Crawling Engine

- **Async Architecture**: Built on `aiohttp` and `asyncio` for maximum performance
- **Rate Limiting**: Configurable delays between batches to respect website policies
- **Error Handling**: Comprehensive retry logic and graceful degradation
- **Platform Detection**: Smart algorithm to identify conference platforms

### Vector Search

- **Fallback Strategy**: Vector search → Text search → Random sampling
- **Multiple Models**: Support for various embedding models and dimensions
- **Similarity Metrics**: Dot product, cosine similarity, and text-based scoring

### LLM Integration

- **Unified AI Platform**: Nebius Token Factory provides both chat completions and embedding generation
- **Structured Prompts**: Carefully crafted prompts for consistent, high-quality outputs
- **Context Management**: Intelligent combination of research and historical data

## 🐛 Troubleshooting

### Vector Search Issues
```bash
# Check if search index exists
python scripts/create_search_indexes.py list

# Manually create index if needed
python scripts/create_search_indexes.py create conference_id
```

### Connection Problems
```bash
# Test Couchbase connection
python -c "from src.models.corpus_manager import ConferenceCorpusManager; cm = ConferenceCorpusManager()"

# Verify API keys
python -c "from src.config.nebius_client import NebiusClient; nc = NebiusClient()"
```

### Crawling Failures
- Check conference URL accessibility
- Verify platform is supported
- Review rate limiting settings
- Check for JavaScript-heavy sites (may need different approach)

## 🚀 Performance Optimization

### Crawling Performance
- **Batch Size**: Start with 10, increase for faster servers
- **Rate Limiting**: 1-2 seconds between batches is usually safe
- **Concurrent Requests**: Limited to prevent overwhelming conference sites

### Search Performance
- **Vector Indexes**: Ensure proper index creation and building
- **Query Optimization**: Use specific keywords and categories
- **Caching**: Results are cached within sessions

### Memory Management
- **Streaming**: Large datasets are processed in chunks
- **Connection Pooling**: Efficient database connection reuse
- **Cleanup**: Automatic resource cleanup on application exit

## 🔮 Future Enhancements

- [ ] **Multi-language Support**: International conference support
- [ ] **Advanced Analytics**: Trend analysis and speaker recommendations
- [ ] **API Interface**: REST API for programmatic access
- [ ] **Real-time Notifications**: Alert for new conferences and talks
- [ ] **Collaborative Features**: Team-based proposal management
- [ ] **Export Features**: PDF, Word, and presentation format exports

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For questions and support:
- Open an issue in the GitHub repository
- Check the troubleshooting section above
- Review the Couchbase and Nebius Token Factory documentation

---

**Built with ❤️ for the Global Conference Community**

Transform any conference's historical talks into your next great presentation idea!

# KubeCon Talk RAG Application

A comprehensive RAG (Retrieval-Augmented Generation) application that helps generate unique and compelling talk proposals for cloud-native conferences by combining historical KubeCon talk data with real-time web research.

## 🏗️ Architecture Overview

This application follows a multi-stage pipeline to create a powerful talk suggestion system:

1. **Data Collection** - Extract and crawl KubeCon talk URLs
2. **Data Processing** - Parse and structure talk information
3. **Vector Storage** - Generate embeddings and store in Couchbase
4. **RAG Application** - Combine historical data with real-time research for intelligent suggestions

## 📋 Prerequisites

- Python 3.8+
- Couchbase Server with Vector Search capabilities
- OpenAI-compatible API access (Nebius AI)
- Environment variables configured (see `.env` setup below)

## 🚀 Complete Pipeline Flow

### Step 1: URL Extraction (`extract_events.py`)

**Purpose**: Extract all KubeCon talk URLs from conference schedule pages.

```bash
# Save the KubeCon schedule HTML to a file, then run:
python extract_events.py < schedule.html
```

**What it does**:
- Parses HTML content from stdin
- Extracts all event URLs with pattern `event/`
- Merges with existing URLs in `event_urls.txt`
- Outputs the count of new URLs discovered

**Output**: `event_urls.txt` - Contains all unique talk URLs

### Step 2: Talk Data Crawling (`couchbase_utils.py`)

**Purpose**: Crawl individual talk pages and extract structured information.

```bash
python couchbase_utils.py
```

**What it does**:
- Reads URLs from `event_urls.txt`
- Uses AsyncWebCrawler to fetch talk pages in batches
- Extracts structured data:
  - Title
  - Description
  - Speaker(s)
  - Category
  - Date
  - Location
- Stores directly to Couchbase with document keys like `talk_<event_id>`

**Features**:
- Batch processing (5 URLs at a time)
- Error handling and retry logic
- Progress tracking with success/failure counts
- Automatic document key generation

### Step 3: Alternative JSON Storage (`crawl_talks.py`)

**Purpose**: Alternative approach to store pre-crawled talk data from JSON files.

```bash
python crawl_talks.py
```

**What it does**:
- Reads from `talk_results1.json`
- Processes and stores talks in Couchbase
- Handles document conflicts with upsert operations
- Adds crawling timestamps

**Use Case**: When you have pre-existing JSON data to import

### Step 4: Embedding Generation (`embeddinggeneration.py`)

**Purpose**: Generate vector embeddings for semantic search capabilities.

```bash
python embeddinggeneration.py
```

**What it does**:
- Queries all documents from Couchbase
- Combines title, description, and category into searchable text
- Generates embeddings using `intfloat/e5-mistral-7b-instruct` model
- Updates documents with embedding vectors
- Enables vector search functionality

**Model**: Uses Nebius AI's embedding endpoint for high-quality vectors

### Step 5: RAG Application (`talk_suggestions_app.py`)

**Purpose**: Interactive Streamlit application for generating talk proposals.

```bash
streamlit run kubecon-talk-agent/talk_suggestions_app.py
```

**Core Features**:

#### 🔍 **Dual-Context Architecture**
1. **Historical Context**: Vector search through stored KubeCon talks
2. **Real-time Context**: Web research via ADK (Agent Development Kit)

#### 🧠 **Three-Stage Generation Process**
1. **Research Phase**: ADK agent researches current trends
2. **Retrieval Phase**: Vector search finds similar historical talks
3. **Synthesis Phase**: LLM combines both contexts for unique proposals

#### 💡 **Smart Proposal Generation**
- Avoids duplicating existing talks
- Incorporates latest industry trends
- Focuses on end-user perspectives
- Provides structured output with learning objectives

## 🛠️ Environment Setup

Create a `.env` file with the following variables:

```env
# Couchbase Configuration
CB_CONNECTION_STRING=couchbase://your-cluster-url
CB_USERNAME=your-username
CB_PASSWORD=your-password
CB_BUCKET=kubecon-talks
CB_COLLECTION=talks
CB_SEARCH_INDEX=kubecontalks

# AI APIs
NEBIUS_API_KEY=your-nebius-api-key
NEBIUS_API_BASE=https://api.studio.nebius.com/v1/
OPENAI_API_KEY=your-openai-key  # Optional fallback
```

## 📊 Couchbase Setup

### 1. Create Bucket and Collection
```sql
-- Create bucket
CREATE BUCKET `kubecon-talks`;

-- Create collection (if not using default)
CREATE COLLECTION `kubecon-talks`.`_default`.`talks`;
```

### 2. Create Vector Search Index
```json
{
  "name": "kubecontalks",
  "type": "fulltext-index",
  "params": {
    "mapping": {
      "default_mapping": {
        "enabled": false
      },
      "type_field": "_type",
      "types": {
        "_default": {
          "enabled": true,
          "dynamic": true,
          "properties": {
            "embedding": {
              "enabled": true,
              "dynamic": false,
              "fields": [
                {
                  "name": "embedding",
                  "type": "vector",
                  "dims": 4096,
                  "similarity": "dot_product"
                }
              ]
            }
          }
        }
      }
    }
  },
  "sourceType": "gocbcore",
  "sourceName": "kubecon-talks"
}
```

## 🎯 Usage Examples

### Basic Talk Proposal Generation
```
Query: "OpenTelemetry distributed tracing in microservices"
```

The system will:
1. Research current OpenTelemetry discussions online
2. Find similar historical talks in the database
3. Generate a unique proposal that builds on existing knowledge

### Advanced Use Cases
- **Emerging Technologies**: "WebAssembly in Kubernetes workloads"
- **Implementation Stories**: "Migration from Prometheus to OpenTelemetry"
- **Best Practices**: "Cost optimization strategies for multi-cloud Kubernetes"

## 📁 File Structure

```
kubecontalksagent/
├── extract_events.py          # URL extraction from HTML
├── couchbase_utils.py         # Main crawling and storage logic
├── crawl_talks.py            # JSON-to-Couchbase import
├── embeddinggeneration.py     # Vector embedding generation
├── kubecon-talk-agent/
│   ├── talk_suggestions_app.py # Main Streamlit RAG app
│   └── adk_research_agent.py   # Web research agent
├── event_urls.txt            # Extracted URLs (generated)
├── talk_results1.json        # Optional: pre-crawled data
└── .env                      # Environment configuration
```

## 🔧 Technical Details

### Vector Search Implementation
- **Model**: `intfloat/e5-mistral-7b-instruct` (4096 dimensions)
- **Similarity**: Dot product
- **Search Strategy**: Combines text matching with vector similarity

### Error Handling
- Connection timeouts and retries
- Graceful degradation when services are unavailable
- Comprehensive logging and user feedback

### Performance Optimizations
- Batch processing for crawling
- Connection pooling for Couchbase
- Async operations where possible
- Configurable timeouts

## 🚨 Common Issues & Solutions

### 1. Vector Search Not Working
- Ensure the search index is created and built
- Verify embedding dimensions match (4096)
- Check Couchbase FTS service is running

### 2. Slow Embedding Generation
- Consider using a local embedding model
- Implement caching for repeated queries
- Use batch embedding generation

### 3. Connection Timeouts
- Increase timeout values in environment
- Check network connectivity to Couchbase
- Verify credentials and permissions

## 🔮 Future Enhancements

- [ ] Support for multiple conference data sources
- [ ] Real-time talk trend analysis
- [ ] Speaker recommendation system
- [ ] Integration with CFP (Call for Papers) platforms
- [ ] Multi-language support for international conferences

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For questions and support, please open an issue in the GitHub repository or contact the maintainers.

---

**Built with ❤️ for the Cloud Native Community** 

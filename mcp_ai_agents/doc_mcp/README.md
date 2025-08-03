# 📚 Doc-MCP: Documentation RAG System

Transform GitHub documentation repositories into intelligent, queryable knowledge bases using RAG and MCP.

## ✨ Features

- **Semantic Search** - Find answers across documentation using natural language
- 🤖 **AI-Powered Q&A** - Get intelligent responses with source citations
- 📚 **Batch Processing** - Ingest entire repositories with progress tracking
- 🔄 **Incremental Updates** - Detect and sync only changed files
- 🗂️ **Repository Management** - Complete CRUD operations for ingested docs

## 🚀 Quick Start

### Prerequisites

- **Python 3.13+**
- **MongoDB Atlas** with Vector Search enabled
- **Nebius API key** for embeddings and LLM
- **GitHub token** (optional, for private repos and higher rate limits)

### Installation

```bash
# Clone and setup
git clone https://github.com/md-abid-hussain/doc-mcp.git
cd doc-mcp
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Setup environment
cp .env.example .env
```

Edit `.env` with your credentials:
```env
NEBIUS_API_KEY=your_nebius_api_key_here
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
GITHUB_API_KEY=your_github_token_here  # Optional
```

### Launch

```bash
# Setup database
python scripts/db_setup.py setup

# Start application
python main.py
```

Visit `http://localhost:7860` to access the web interface.

Access MCP at `http://127.0.0.1:7860/gradio_api/mcp/sse`

## Usage

### 1. Ingest Documentation
- Navigate to "📥 Documentation Ingestion" tab
- Enter GitHub repository URL (e.g., `owner/repo`)
- Select markdown files to process
- Execute two-step pipeline: Load files → Generate embeddings

### 2. Query Documentation  
- Go to "🤖 AI Documentation Assistant" tab
- Select your repository
- Ask natural language questions
- Get AI responses with source citations

### 3. Manage Repositories
- Use "�️ Repository Management" tab  
- View statistics and file counts
- Delete repositories when needed

## 🔧 Configuration

### Environment Variables

```env
# Required
NEBIUS_API_KEY=your_nebius_api_key_here
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/

# Optional
GITHUB_API_KEY=your_github_token_here
CHUNK_SIZE=3072
SIMILARITY_TOP_K=5
GITHUB_CONCURRENT_REQUESTS=10
```

### MongoDB Atlas Setup

1. Create cluster with **Vector Search** enabled
2. Database structure auto-created:
   - `doc_rag` - documents with embeddings  
   - `ingested_repos` - repository metadata

## 🐛 Troubleshooting

**Common Issues:**

- **Rate Limits**: Add GitHub token for 5000 requests/hour (vs 60)
- **Memory Issues**: Reduce `CHUNK_SIZE` in `.env`
- **Connection Errors**: Verify MongoDB Atlas Vector Search is enabled
- **Database Issues**: Run `python scripts/db_setup.py status`

## 📖 Documentation

For detailed guides see:
- Advanced configuration options
- Development and contribution guide  
- API reference and examples

## 💻 Author

**Md Abid Hussain**
- GitHub: [@md-abid-hussain](https://github.com/md-abid-hussain)
- LinkedIn: [md-abid-hussain](https://www.linkedin.com/in/md-abid-hussain-52862b229/)

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Built with ❤️ using Python, LlamaIndex, Nebius, MongoDB Atlas, and Gradio**
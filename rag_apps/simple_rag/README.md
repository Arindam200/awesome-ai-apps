# Simple RAG

> A minimal Retrieval-Augmented Generation notebook using LlamaIndex with Nebius Token Factory LLM and embedding models — a quick-start template for building your own RAG pipeline.

This is the smallest possible RAG example in this repo: point it at a folder of documents, ask a question, and get an answer grounded in that folder's contents. Good starting point before moving on to the more advanced RAG examples in this directory (reranking, hybrid search, OCR, etc.).

## 🚀 Features

- **Document loading**: reads any local directory of documents with LlamaIndex's `SimpleDirectoryReader`
- **In-memory vector index**: builds a `VectorStoreIndex` over the loaded documents
- **Nebius-hosted embeddings + LLM**: uses `NebiusEmbedding` and `NebiusLLM` for retrieval and generation, no local models required
- **Single function interface**: one `run_rag_completion()` call takes a document directory and a query and returns the answer

## 🛠️ Tech Stack

- **Python**: Core programming language
- **[LlamaIndex](https://www.llamaindex.ai/)** (`llama-index-llms-nebius`, `llama-index-embeddings-nebius`): For document indexing and retrieval
- **[Nebius Token Factory](https://tokenfactory.nebius.com/)**: LLM (`deepseek-ai/DeepSeek-V3` by default) and embedding model (`BAAI/bge-en-icl` by default) provider

## Workflow

1. Load all documents from a local directory with `SimpleDirectoryReader`.
2. Embed and index them into an in-memory `VectorStoreIndex` using a Nebius embedding model.
3. Send the query to a Nebius LLM through the index's query engine, which retrieves relevant chunks and generates a grounded answer.

## 📦 Getting Started

### Prerequisites

- Python 3.9+
- A [Nebius Token Factory](https://tokenfactory.nebius.com/) API key

### Environment Variables

Set your API key directly in the notebook, or export it before starting Jupyter:

```env
NEBIUS_API_KEY="your_nebius_api_key"
```

### Installation

```bash
git clone https://github.com/Arindam200/awesome-llm-apps.git
cd awesome-llm-apps/rag_apps/simple_rag
pip install llama-index llama-index-llms-nebius llama-index-embeddings-nebius
```

## ⚙️ Usage

1. **Open the notebook:**

   ```bash
   jupyter notebook nebius_rag.ipynb
   ```

2. **Set `NEBIUS_API_KEY`** in the environment-variable cell (or export it beforehand).

3. **Point `document_dir` at your own folder** of documents (defaults to `./data`) and set `query_text` to your question, then run all cells.

## 📂 Project Structure

```
simple_rag/
├── nebius_rag.ipynb   # RAG walkthrough: load docs, index, query
└── README.md
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See the [CONTRIBUTING.md](https://github.com/Arindam200/awesome-llm-apps/blob/main/CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/Arindam200/awesome-llm-apps/blob/main/LICENSE) file for details.

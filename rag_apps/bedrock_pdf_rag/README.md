# Bedrock PDF RAG

A RAG-powered PDF chatbot using Amazon Bedrock (Claude 3 Haiku) and FAISS for semantic search with page-level citations. Sub-2s response time. Local embeddings via sentence-transformers (no API cost on uploads).

## Features

- PDF upload with multi-turn Q&A and page-level citations on every answer
- Local embeddings via sentence-transformers — no embedding API costs
- Session isolation for multiple users, Docker ready

## Tech Stack

| Component | Technology |
|---|---|
| LLM | Amazon Bedrock (Claude 3 Haiku) |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 (local) |
| Vector Store | FAISS (in-memory) |
| API | FastAPI + uvicorn |
| Frontend | Streamlit |
| PDF Parsing | pypdf |
| Containerization | Docker |

## Getting Started

Prerequisites: Python 3.11+, AWS account with Amazon Bedrock enabled, IAM user with bedrock:InvokeModel permission.

```bash
cd rag_apps/bedrock_pdf_rag
cp .env.example .env
pip install -r requirements.txt
uvicorn api.main:app --reload   # Terminal 1
streamlit run frontend/app.py   # Terminal 2
```

Open http://localhost:8501, upload a PDF, ask questions in plain English.

## Docker

```bash
cd rag_apps/bedrock_pdf_rag
docker build -t bedrock-pdf-rag .
docker run --env-file .env -p 8000:8000 -p 8501:8501 bedrock-pdf-rag
```

## Project Structure

```
rag_apps/bedrock_pdf_rag/
├── api/
│   └── main.py
├── frontend/
│   └── app.py
├── core/
│   ├── embeddings.py
│   └── retriever.py
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Environment Variables

```
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
```

## Related Project

[Constitutional AI Multi-Agent](../advance_ai_agents/constitutional_ai_multi_agent/) — a 6-agent system also using Amazon Bedrock for safe AI deployment.

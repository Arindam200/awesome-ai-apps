# Image-Aware PDF RAG

This project demonstrates a multimodal Retrieval-Augmented Generation (RAG) system capable of answering questions about both the text and the visual elements (charts, tables, diagrams) within a PDF document.

## 🌟 Features

- **Multimodal Indexing**: Extracts both text chunks and visual descriptions of pages using a Vision LLM.
- **Visual Understanding**: Can answer questions about specific charts, tables, or architecture diagrams.
- **Grounded Citations**: Every answer includes page-level citations.
- **Interactive Preview**: A side-by-side UI that allows users to instantly view the cited page of the PDF.
- **Fast Inference**: Powered by Groq for ultra-low latency multimodal and chat responses.

## 🛠️ Technical Architecture

- **UI**: Streamlit
- **Vision Model**: Groq (default: `qwen/qwen3.8-27b`)
- **Chat Model**: Groq (default: `openai/gpt-oss-20b`)
- **Embeddings**: Local `Sentence-Transformers` (`all-MiniLM-L6-v2`)
- **Vector Store**: FAISS
- **PDF Processing**: PyMuPDF / pdf2image

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- A Groq API Key

### Installation

1. Navigate to the project directory:
   ```bash
   cd rag_apps/image_aware_pdf_rag
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   # Or using uv:
   uv pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your `GROQ_API_KEY`.

### Running the Application

```bash
streamlit run app.py
```

## 📖 Usage

1. **Upload**: Upload a PDF containing charts or diagrams (e.g., the provided `technical-doc-teachgrow.pdf`).
2. **Index**: Click **"🚀 Index Document"**. The app will:
   - Chunk the text.
   - Use the Vision model to describe every page containing an image.
   - Store both text and visual descriptions in the FAISS vector store.
3. **Ask**: Use the provided example buttons or type your own question:
   - *Text Question*: "What is the main contribution of this paper?"
   - *Visual Question*: "Explain the architecture diagram on page 3."
4. **Verify**: Click "View page" on the cited sources to see the exact section of the PDF used to generate the answer.

## 📂 Project Structure

- `app.py`: Main Streamlit application.
- `ingestion.py`: PDF loading and page extraction.
- `vision.py`: Integration with the Multimodal LLM for page descriptions.
- `chunking.py`: Logic for splitting PDF text into manageable chunks.
- `retrieval/`: Logic for semantic search over the multimodal index.
- `providers/`: API wrappers for Groq Chat and Vision models.
- `vectorstores/`: FAISS implementation for document storage.
- `sample_data/`: Example PDFs for testing.

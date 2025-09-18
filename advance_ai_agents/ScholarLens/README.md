
# 🧠 ScholarLens – AI-Powered Research Assistant with Agentic RAG

ScholarLens is a **Streamlit-based AI research assistant** that streamlines literature review, research paper summarization, and comparison.
It leverages **Agentic AI workflows** and **Agentic RAG** (via the [Agno](https://agno.com) library) to let you search, analyze, summarize, and compare academic papers in a deeply interactive way.

---

## 🚀 Features

### 1. **🔍 ArXiv Smart Search**

* Search **latest research papers** from [arXiv](https://arxiv.org) by topic.
* Summarizes each paper with:

  * Problem statement
  * Key contributions
  * Summary of findings
* Export results as **JSON**.

### 2. **📚 AI Paper Companion**

* Upload any PDF research paper.
* **Instant Glance Mode**:

  * Extracts title, model, dataset, evaluation metrics, and structured summary.
* **Guru Mode**:

  * Section-wise summarization (Abstract, Methodology, Results, etc.) in **bullet-point JSON** format.

### 3. **💬 Agentic RAG Chatbot**

* Upload a paper and query it conversationally.
* Uses **Agno's Agentic RAG flow**:

  * **Gemini Embeddings** for semantic chunk representation.
  * **Pinecone VectorDB** for fast similarity search.
  * **Gemini LLM** as the reasoning engine.
* Supports persistent **chat + search history** for contextual Q\&A.

### 4. **📊 Compare Research Papers**

* Upload **two or three** research papers (PDF).
* AI-generated **Markdown comparison table**:

  * Problem statement
  * Methodology
  * Datasets used
  * Model performance and accuracy

---

## 🏗️ Tech Stack

* **Frontend**: [Streamlit](https://streamlit.io)
* **Agentic Framework**: [Agno](https://agno.com) for multi-step RAG orchestration
* **LLM Providers**: Google Gemini, Groq
* **Vector Database**: Pinecone
* **Embeddings**: Gemini Embeddings (`models/gemini-embedding-001`)
* **PDF Processing**: PyMuPDF (fitz)
* **Agent Framework (ArXiv & Summarization)**: [CrewAI](https://www.crewai.com)
* **APIs**: arXiv API, Pinecone API
* **Environment Management**: python-dotenv

---

## 📂 Project Structure

```
ScholarLens/
├── main.py                  # Entry point
├── requirements.txt         # Dependencies
├── comparision/             # Paper comparison module
├── rag/                     # Agentic RAG implementation
├── search/                  # Research paper search tools
├── summarization/           # Summarization modules
├── utils/                   # Utilities (memory, DB patches)
└── assets/                  # Images & static assets

```

---

## ⚙️ Installation

1️⃣ **Clone the repository**

```bash
git clone https://github.com/your-username/scholarlens.git
cd scholarlens
```

2️⃣ **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate    # On Mac/Linux
venv\Scripts\activate       # On Windows
```

3️⃣ **Install dependencies**

```bash
pip install -r requirements.txt
```

4️⃣ **Set up environment variables**
Create a `.env` file in the root directory:

```env
GOOGLE_API_KEY=your_google_gemini_api_key
GROQ_API_KEY=your_groq_api_key
PINECONE_API_KEY=your_pinecone_api_key
```

---

## ▶️ Usage

Run the app:

```bash
streamlit run app.py
```

In the sidebar, select:

* **ArXiv Smart Search** → Search papers by topic.
* **AI Paper Companion** → Upload PDF for summarization.
* **Agentic RAG Chatbot** → Chat with a paper using Agno's RAG.
* **Compare Research Papers** → Compare two research PDFs.

---
Check out the demo: https://scholarlens.streamlit.app/

<img width="1919" height="965" alt="image" src="https://github.com/user-attachments/assets/289b61af-6fa4-4d7e-b3eb-059497a803a9" />
<img width="1919" height="943" alt="image" src="https://github.com/user-attachments/assets/86f192d6-2f07-464b-b598-6547455b72fd" />
<img width="1450" height="846" alt="image" src="https://github.com/user-attachments/assets/1fc53e75-b5dd-4c23-9dbe-f18195417811" />

---

## 📜 License

MIT License © 2025 ScholarLens AI

---

## 🙌 Acknowledgements

* [Agno](https://agno.com) for the Agentic RAG framework.
* [arXiv](https://arxiv.org) for open-access research papers.
* [Streamlit](https://streamlit.io) for the interactive web app framework.
* [Google Gemini](https://ai.google) and [Groq](https://groq.com) for LLM APIs.
* [Pinecone](https://pinecone.io) for vector database services.
* [CrewAI](https://www.crewai.com) for agentic workflows in research retrieval & summarization.


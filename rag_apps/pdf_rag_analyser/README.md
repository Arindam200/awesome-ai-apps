# 📚 Chat with Multiple PDFs

Interact with multiple PDF files using powerful AI models like **Gemini 1.5 (Google AI)** to extract insights, analyze financial data, and answer questions based on uploaded documents. This app is especially useful for analyzing **annual reports** and **financial statements** of Indian stock market companies.

![Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-orange?style=flat-square&logo=streamlit)

---

## 🚀 Features

- 📄 Upload multiple PDF files
- 🤖 Ask questions based on the content of the PDFs
- 🧠 Uses LangChain and Google Gemini 1.5 (`gemini-1.5-flash`) for contextual answers
- 🗃️ Embeds content using `GoogleGenerativeAIEmbeddings` and stores in FAISS vector database
- 📊 Specialized for analyzing financial reports, related-party transactions, and remuneration
- 🗨️ Chat-like interface with user/bot avatars
- 📥 Export conversation history as CSV

---

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/rakshithsantosh/pdf-chatbot-gemini.git
cd pdf-chatbot-gemini
```

### 2. Set Up a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install Required Dependencies

```bash
# Using pip
pip install -r requirements.txt

# Or using uv (recommended)
uv sync
```

### 4. Run the App

```bash
streamlit run app.py
```

---

## 🔐 Google AI API Key

To use Gemini models and embeddings:

1. Visit [Google AI Studio](https://ai.google.dev/)
2. Generate your API key
3. Enter the key in the **Streamlit sidebar**

---

## 📦 Tech Stack

| Tech       | Purpose                                  |
| ---------- | ---------------------------------------- |
| Streamlit  | UI framework for interactive web apps    |
| LangChain  | Managing LLM chains and embeddings       |
| Gemini 1.5 | Large Language Model (via Google AI API) |
| PyPDF2     | PDF text extraction                      |
| FAISS      | Vector database for similarity search    |
| Pandas     | Exporting conversation as CSV            |
| HTML/CSS   | Custom chat UI inside Streamlit          |

---

## 📁 File Structure

```
├── app.py               # Main Streamlit app
├── faiss_index/         # Folder where vectorstore is saved
├── requirements.txt     # Required Python packages
└── README.md            # You're here!
```

---

## 🧠 Prompt Template Logic

This tool is **finance-aware**. The prompt guides the LLM to:

- Evaluate financial statements from PDFs
- Detect irregularities or red flags
- Analyze related party transactions
- Identify unusual managerial remuneration

---

## 🧪 Sample Use Cases

- Analyze 5 annual reports to compare **debt-to-equity ratios**
- Identify suspicious **related-party transactions**
- Audit **CFO to Net Profit** conversion trends
- Track increase in **Key Managerial Personnel (KMP)** pay

---

## 👤 Author

- [Rakshith Santosh](https://www.linkedin.com/in/rak-99-s)
- [GitHub](https://github.com/rakshithsantosh)

---

## 📄 License

MIT License – Feel free to use, modify, and share!

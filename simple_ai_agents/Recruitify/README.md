
# 🚀 Recruitify

An intelligent recruitment and interview assistant built with **Streamlit**, **LangChain**, **Google Gemini API**, **Groq API**, and **Deepgram API**.
This app helps recruiters, candidates, and career coaches by:

* 📄 **Analyzing Resumes** against job requirements or custom job descriptions
* ❓ **Q\&A on Resumes** using Retrieval-Augmented Generation (RAG)
* 🎯 **Generating Personalized Interview Questions**
* 🛠️ **Providing Resume Improvement Suggestions** with before/after examples
* 📝 **Creating Optimized Improved Resumes** tailored for a target role
* 🎙️ **Simulating Real-Time Interviews** with voice input, AI-generated feedback, and performance scoring

---

## ✨ Features

### 🔍 Resume Requirement Analyst

* Upload a **resume (PDF)** and analyze it against:

  * Predefined **role-based skill sets** (e.g., Data Scientist, AI/ML Engineer, DevOps Engineer)
  * Or a **custom job description (PDF/TXT)**
* Get:

  * **Overall Score & Shortlisting Status**
  * **Strengths & Weaknesses**
  * **Detailed Skill Gap Analysis**
  * 📊 Downloadable **Resume Analysis Report**

### 🤖 Resume Q\&A

* Ask **any question** about the uploaded resume
* Example: *“What is the candidate’s most recent role?”* or *“Does the candidate have cloud experience?”*

### 📝 Interview Question Generator

* Generate **personalized interview questions** based on resume & skills
* Supports multiple question types: *Basic, Technical, Scenario, Coding, Behavioral*
* Difficulty levels: *Easy, Medium, Hard*
* Download generated questions in **Markdown format**

### 🛠️ Resume Improvement

* AI-powered suggestions for improvement in:

  * **Content**
  * **Skills Highlighting**
  * **Experience & Projects**
  * **Format & Structure**
* Includes **Before vs. After** examples for better clarity

### 📑 Improved Resume Generator

* Automatically rewrite and optimize resumes for:

  * A **specific target role**
  * Or a **given job description**
* Highlights missing & key skills

### 🎙️ AI Interview Assistant

* Upload **interview question files (Markdown/TXT)**
* **Voice-based interview simulation**:

  * Questions are read aloud using **Groq TTS**
  * Candidate answers via **microphone input**
  * Transcribed using **Deepgram STT**
* AI evaluates responses with:

  * ✅ Strengths & Weaknesses
  * 📌 Actionable Improvement Suggestions
  * 📊 Confidence & Accuracy Scoring (1–10)
* 📉 Performance Report with **visual graphs (Plotly)**

---

## 🛠️ Tech Stack

* **Frontend/UI**: [Streamlit](https://streamlit.io/)
* **AI & NLP**: [LangChain](https://www.langchain.com/), [Google Gemini API](https://ai.google.dev/)
* **LLMs**: Groq (LLaMA 3.3-70B), Google Gemini
* **Vector Database**: FAISS
* **Speech-to-Text**: [Deepgram](https://deepgram.com/)
* **Text-to-Speech**: Groq Audio API
* **Charts & Visualization**: Plotly, Matplotlib

---

## 🚀 Installation

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/yourusername/recruitment-agent.git
cd recruitment-agent
```

### 2️⃣ Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Set Environment Variables

Create a `.env` file in the project root:

```ini
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
```

---

## ▶️ Usage

Run the app with:

```bash
streamlit run app.py
```

### Modes:

* **Requirement Analyst** → Resume analysis, Q\&A, improvements, and interview question generation
* **Interview Assistant** → Voice-enabled AI-powered interview simulation

---

## 📂 Project Structure

```
.
├── app.py               # Main Streamlit app entry point
├── agents.py            # Resume analysis agent (LLM, RAG, scoring, improvements)
├── interview.py         # AI-powered voice interview assistant
├── ui.py                # Streamlit UI components and styling
├── requirements.txt     # Dependencies
└── README.md            # Project documentation
```

---

## 📊 Example Screenshots

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/e20bf1df-e06f-418f-8865-8b3eba181de0" />
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/e8946f12-4e9d-4757-b3a0-90a74a305145" />
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/d8097f93-c4c7-407a-9d14-13d8997b9192" />


---

## 🤝 Contributing

Contributions are welcome!

* Fork the repo
* Create a feature branch
* Commit your changes
* Open a Pull Request

---

## 📜 License

This project is licensed under the **MIT License**.

---

Would you like me to also **generate a `requirements.txt`** file for you based on the imports in all four files? That way your repo will be fully ready to run.

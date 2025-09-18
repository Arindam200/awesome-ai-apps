
# 🎯 Career Guidance AI System

An **AI-powered career recommendation and guidance platform** built with **Streamlit**, leveraging **Agentic AI**, **LLMs**, and **web APIs** to provide personalized career suggestions, growth paths, salary insights, and demand analysis based on user-selected career preferences.

---

## 🚀 Features

### 1. **Interactive Career Chatbot**

* Real-time conversational interface to guide users in exploring career paths.
* Suggests relevant skills, courses, and learning resources.
* Provides salary expectations and job market demand data.

### 2. **Career Path Recommendations**

* Select your desired careers.
* AI agents fetch career growth paths, industry insights, and role descriptions.
* Data-driven salary and demand predictions.

### 3. **Industry Insights & Market Trends**

* Integrates with **SerpAPI** for real-time web data.
* Uses **LLM-based analysis** for summarizing industry trends.

---

## 🏗️ Tech Stack

* **Frontend**: [Streamlit](https://streamlit.io) for interactive UI
* **LLM Framework**: [CrewAI](https://www.crewai.com) for agent orchestration
* **LLMs**: Groq & Google Gemini
* **Data Sources**: SerpAPI
* **Backend Logic**: Python
* **Environment Management**: python-dotenv

---

## 📂 Project Structure

```
Career_Guidence-main/
├── app.py                    # Main Streamlit app entry point
├── career_chatbot.py         # Chatbot UI & logic
├── career_guidance_system.py # Career recommendation & insights logic
├── demo.ipynb                # Example notebook for testing
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
└── README.md                 # Documentation
```

---

## ⚙️ Installation

1️⃣ **Clone the repository**

```bash
git clone https://github.com/your-username/Career_Guidence.git
cd Career_Guidence-main
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

4️⃣ **Configure environment variables**
Create a `.env` file with:

```env
SERPAPI_API_KEY=your_serpapi_key
GOOGLE_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
```

---

## ▶️ Usage

Run the app:

```bash
streamlit run app.py
```

In the sidebar:

* Select **Career Chatbot** to start an interactive conversation.
* Choose **Career Guidance** to get recommendations, paths, salaries, and trends.

---
check this: https://careerguidencer.streamlit.app/
## 📸 Screenshots
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/415f5386-6932-470a-b0c1-c1e93fe2a36e" />
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/525c2b40-073e-4b38-979d-05b1a412f5a1" />
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/e8bbc313-6b47-4296-beb1-3eb8df52c6a7" />
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/bd70e2e6-4c58-450e-bd4e-79895c8900fd" />


---

## 📜 License

MIT License © 2025 Career Guidance AI

---

## 🙌 Acknowledgements

* [CrewAI](https://www.crewai.com) for agent orchestration
* [Google Gemini](https://ai.google) and [Groq](https://groq.com) for LLM APIs
* [SerpAPI](https://serpapi.com) for search data

<!-- Optional: Add a banner or GIF at the top -->

![Demo GIF](./assets/demo.gif)

# OmniSage – Intelligent Multi-Agent Teaching and Learning Ecosystem

> An AI-powered multi-agent learning platform that analyzes student learning needs, generates personalized learning resources, creates assessments, and supports adaptive learning.

OmniSage is an AI-powered teaching and learning ecosystem designed to provide personalized academic support to students. Instead of working as a simple chatbot, OmniSage uses specialized AI agents that collaborate to analyze learner needs, generate appropriate learning resources, assess understanding, and provide personalized learning support.

Built with **React, TypeScript, Python, FastAPI, Vite, and Google Gemini**, OmniSage demonstrates how multi-agent AI can be used to create a more adaptive and personalized learning experience.

## 🚀 Features

* **Learning Analyst Agent**: Analyzes the student's question to identify the learning requirement and approximate difficulty level.

* **Resource Agent**: Generates clear, personalized, and beginner-friendly explanations based on the student's learning needs.

* **Assessment Agent**: Generates questions based on the learning content to check the student's understanding.

* **Multi-Agent Collaboration**: Multiple specialized AI agents work together instead of relying on a single chatbot response.

* **Personalized Learning**: The system adapts educational content according to the identified learning requirement and difficulty.

* **Assessment-Based Learning**: Connects generated learning resources with assessments to create a continuous learning process.

* **User-Friendly Interface**: A React and TypeScript-based web interface allows students to ask questions and receive learning resources and assessments.

## 🛠️ Tech Stack

* **Python 3.10+**: Core backend programming language
* **FastAPI**: Backend API framework for handling requests and connecting the frontend with AI services
* **React + TypeScript**: Frontend framework for building the learning interface
* **Vite**: Frontend development and build tool
* **Google GenAI SDK**: Integration with Google's generative AI services
* **Google Gemini**: Large language model used for AI-powered learning content and assessment generation
* **Pydantic**: Request validation and data modelling
* **python-dotenv**: Environment variable and API key management
* **React Markdown**: Rendering AI-generated learning content in the frontend
* **Uvicorn**: ASGI server used to run the FastAPI backend
* **Git & GitHub**: Version control and project collaboration

## 🔄 Workflow

<!-- Optional: Add a workflow diagram or GIF -->

![Workflow Diagram](./assets/workflow.gif)

The OmniSage workflow consists of multiple specialized AI agents working together to support the student's learning process.

```text
Student Question
       │
       ▼
┌─────────────────────┐
│ Learning Assistant  │
│    Web Interface    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Learning Analyst   │
│       Agent         │
└──────────┬──────────┘
           │
           ▼
   Learning Analysis
   ├── Learning Need
   └── Difficulty
           │
           ▼
┌─────────────────────┐
│   Resource Agent    │
└──────────┬──────────┘
           │
           ▼
 Personalized Learning
      Explanation
           │
           ▼
┌─────────────────────┐
│  Assessment Agent   │
└──────────┬──────────┘
           │
           ▼
     Knowledge Check
           │
           ▼
        Student
```

### Main Processing Steps

1. **Student Input**: The student enters a question or learning requirement through the OmniSage interface.

2. **Learning Analysis**: The Learning Analyst Agent identifies the type of learning support required and estimates the difficulty level.

3. **Resource Generation**: The Resource Agent uses the learning analysis to generate a personalized explanation.

4. **Assessment Generation**: The Assessment Agent uses the student's question and generated explanation to create assessment questions.

5. **Learning Feedback**: The student receives the generated learning material and assessment through the web interface.

6. **Adaptive Learning Extension**: Assessment results can be used in future versions to identify knowledge gaps and recommend the student's next learning activity.

## 📦 Getting Started

### Prerequisites

* **Python 3.10+**
* **Node.js 18+**
* **npm**
* **Git**
* **pip**
* Google Gemini API key
* A code editor such as Visual Studio Code

### Environment Variables

Create the environment file required by the backend.

Create:

```text
backend/.env
```

Add:

```env
GEMINI_API_KEY="your_gemini_api_key"
```

Replace the example value with your actual Gemini API key.

**Note:** Never commit API keys, passwords, or other sensitive information to the repository.

Make sure `.env` is included in `.gitignore`.

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Archanaa-Thannirmalai/omnisage-platform.git
   cd omnisage-platform
   ```

2. **Create and activate a virtual environment:**

   **Using `venv`:**

   ```bash
   python -m venv .venv
   ```

   **Windows:**

   ```bash
   .venv\Scripts\activate
   ```

   **Linux/macOS:**

   ```bash
   source .venv/bin/activate
   ```

3. **Install backend dependencies:**

   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Install frontend dependencies:**

   Open another terminal and navigate to the frontend directory:

   ```bash
   cd frontend
   npm install
   ```

## ⚙️ Usage

1. **Start the FastAPI backend:**

   From the `backend` directory:

   ```bash
   python -m uvicorn main:app --reload
   ```

   The backend will run at:

   ```text
   http://127.0.0.1:8000
   ```

2. **Open the FastAPI documentation:**

   ```text
   http://127.0.0.1:8000/docs
   ```

3. **Start the React frontend:**

   From the `frontend` directory:

   ```bash
   npm run dev
   ```

4. Open the frontend URL displayed by Vite, normally:

   ```text
   http://localhost:5173
   ```

5. Enter a question into the OmniSage Learning Assistant.

   Example:

   ```text
   What is inertia?
   ```

6. OmniSage analyzes the question, generates an explanation, and creates an assessment based on the topic.

## 📂 Project Structure

```text
omnisage-platform/
│
├── assets/
│   ├── demo.gif
│   └── workflow.gif
│
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── agents.py
│   │   │   │   ├── analytics.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── content.py
│   │   │   │   ├── learners.py
│   │   │   │   └── websocket.py
│   │   │   │
│   │   │   └── deps.py
│   │   │
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── utils/
│   │
│   ├── tests/
│   ├── .env
│   ├── alembic.ini
│   ├── main.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/
│   │   │   ├── dashboard/
│   │   │   ├── educator/
│   │   │   └── learner/
│   │   │
│   │   ├── hooks/
│   │   ├── pages/
│   │   │   └── LearningAssistant.tsx
│   │   ├── services/
│   │   ├── store/
│   │   ├── styles/
│   │   ├── App.tsx
│   │   └── main.tsx
│   │
│   ├── package.json
│   └── vite.config.ts
│
├── frontend-old/
│
├── .gitignore
├── README.md
└── LICENSE
```

## 🤝 Contributing

Contributions are welcome! Contributors can help improve OmniSage by:

* Adding new educational AI agents
* Improving learner analysis
* Improving personalized resource generation
* Adding new assessment capabilities
* Developing learning analytics
* Improving the frontend interface
* Adding educator-focused features
* Implementing adaptive learning recommendations

Please follow the repository's contribution guidelines before submitting changes.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## 🙏 Acknowledgments

* Thanks to the developers and maintainers of **FastAPI, React, TypeScript, Vite, Pydantic, and Google GenAI**.
* Thanks to the open-source community for providing the libraries and tools used in this project.
* Special thanks to the developers and researchers working on AI-powered personalized education and multi-agent systems.

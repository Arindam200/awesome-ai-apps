# DSA Assistant 🚀

Your AI-powered coding mentor for problem-solving & algorithm optimization

## ✨ Features

- **🎯 Basic Approach**: Generate brute-force solutions with clear explanations
- **⚡ Sub-Optimal Solutions**: Improve efficiency step by step  
- **🏆 Optimal Solutions**: Find the most efficient algorithms
- **🔍 Code Verification**: Test and validate solutions automatically
- **📚 Notes Generation**: Transform code into comprehensive study notes
- **🎨 Interactive UI**: Beautiful Streamlit interface with progress tracking

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/ankush0511/AlgoMentor.git
cd AlgoMentor

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Add your API keys to .env file
```

### Environment Setup

Create a `.env` file with:
```
GROQ_API_KEY=your_groq_api_key
GOOGLE_API_KEY=your_google_api_key
```

### Run the Application

```bash
streamlit run main.py
```

## 📁 Project Structure

```
DSAAssistant/
├── 📁 src/                    # Source code
│   ├── 📁 agents/             # AI agents for different optimization levels
│   ├── 📁 models/             # Pydantic data models
│   ├── 📁 utils/              # Utility functions
│   ├── 📁 ui/                 # User interface components
│   └── 📁 core/               # Core application logic
├── 📁 config/                 # Configuration files
├── 📁 tests/                  # Test files
├── 📁 docs/                   # Documentation
├── 📁 assets/                 # Static assets
├── 📄 main.py                 # Application entry point
├── 📄 requirements.txt        # Python dependencies
├── 📄 .env.example           # Environment variables template
└── 📄 README.md              # Project documentation
```

## 🛠️ Usage

1. **Enter Problem**: Paste your DSA problem or use example problems
2. **Basic Approach**: Get brute-force solution with explanation
3. **Sub-Optimal**: Improve the solution step by step
4. **Optimal**: Achieve the most efficient algorithm
5. **Notes**: Generate comprehensive study notes from your code

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Powered by [Groq](https://groq.com/) and [Google AI](https://ai.google/)
- Uses [Agno](https://github.com/agno-ai/agno) for AI agent orchestration

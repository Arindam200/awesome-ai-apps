# Job Search Agent with Memory

An AI-powered job search agent that uses ExaAI for intelligent web search and Memori for contextual memory. Built with LangChain for agent orchestration and Streamlit for the user interface.

## Features

- 🔍 **Smart Job Search**: Uses ExaAI to search across multiple job sites (LinkedIn, Indeed, Glassdoor, Monster, etc.)
- 🎯 **Flexible Filters**: Search by job title, location, and work style (Remote/Hybrid/Onsite)
- 📊 **Configurable Results**: Choose how many job listings to display (1-20, default: 5)
- 🔗 **Direct Links**: Click through directly to job postings to apply
- 🧠 **Memory**: Ask questions about your previous job searches using Memori-powered contextual memory
- 💼 **Detailed Listings**: View job descriptions, company names, locations, and salary information when available
- 📄 **Resume Upload**: Upload your resume to get personalized job recommendations and resume improvement suggestions
- 🎯 **Resume Matching**: Ask which jobs you're best suited for based on your resume
- ✏️ **Resume Improvement**: Get suggestions on what to add to your resume for specific job positions

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager (fast Python package installer)
- ExaAI API key ([Get one here](https://exa.ai/))
- Nebius API key ([Get one here](https://nebius.ai/))

## Installation

### 1. Install uv

If you don't have `uv` installed, install it with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or using pip:
```bash
pip install uv
```

### 2. Clone and Navigate

```bash
git clone https://github.com/Arindam200/awesome-ai-apps/brand-reputation-monitor.git
cd memory_agents/job_search_agent
```

### 3. Install Dependencies

Using `uv` (recommended - much faster):

```bash
uv sync
```

This will:
- Create a virtual environment automatically
- Install all dependencies from `pyproject.toml`
- Make the project ready to run

### 4. Set Up Environment Variables

Create a `.env` file in this directory:

```bash
EXA_API_KEY=your_exa_api_key_here
NEBIUS_API_KEY=your_nebius_api_key_here
```

## Usage

### Run the Application

Activate the virtual environment and run Streamlit:

```bash
# Activate the virtual environment (created by uv)
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows

# Run the app
streamlit run app.py
```

Or using `uv` directly:

```bash
uv run streamlit run app.py
```

The app will open in your browser. You can:

1. **Enter API Keys**: Add your API keys in the sidebar (or use the `.env` file)
2. **Upload Resume** (optional): Go to the **Resume** tab to upload your resume for personalized matching
3. **Search Jobs**: Go to the **Job Search** tab and:
   - Enter Job Title (required)
   - Enter Location (optional)
   - Select Work Style (Any/Remote/Hybrid/Onsite)
   - Choose Number of Jobs (1-20, default: 5)
   - Click **Search Jobs**
4. **View Results**: Browse job listings with direct links to apply
5. **Ask Questions**: Go to the **Memory** tab to:
   - Ask about previous searches
   - Get job matching recommendations (if resume uploaded)
   - Get resume improvement suggestions for specific jobs

## How It Works

### Job Search Flow

1. **Query Building**: The app builds a search query from your inputs (job title, location, work style)
2. **ExaAI Search**: Uses ExaAI to search across job board domains with intelligent semantic search
3. **Result Processing**: Extracts job details (title, company, location, description, salary) using LLM
4. **Display**: Shows results in an organized format with clickable links
5. **Memory Storage**: Stores search results and job descriptions in Memori for future reference

### Memory System

- Uses Memori to store:
  - Search history and conversations
  - Resume information (if uploaded)
  - Individual job descriptions for matching
- Ask questions like:
  - "What jobs did I search for?"
  - "Which job am I best suited for with my resume?"
  - "What can I add to my resume to make it fit for Software Engineer at Google?"
  - "What companies did I find for software engineer positions?"
- The memory system uses contextual embeddings to find relevant past searches and resume data

### Resume Matching

When you upload your resume:
- Resume details are extracted and stored in Memori
- Job descriptions are stored individually for matching
- You can ask personalized questions about:
  - Job fit based on your skills
  - Resume improvements for specific positions
  - Skills gaps for target roles

## Project Structure

```
job_search_agent/
├── app.py              # Streamlit interface
├── workflow.py         # LangChain and ExaAI integration
├── resume_parser.py    # Resume parsing and extraction
├── pyproject.toml      # Project dependencies (uv format)
├── README.md           # This file
├── .streamlit/         # Streamlit configuration
│   └── config.toml     # Theme settings
├── assets/             # Logo images
│   ├── Memori_Logo.png
│   └── exa_logo.png
└── memori.db           # Memori database (created automatically)
```

## License

See the main repository LICENSE file.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

Made with ❤️ by [Studio1](https://www.Studio1hq.com) Team

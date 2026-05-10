# Resume Optimizer with Llamaindex

![GIf](./demo.gif)

A powerful AI-powered resume optimization tool that helps job seekers enhance their resumes based on specific job requirements. Built with Streamlit and powered by Nebius AI, this application provides targeted suggestions to improve your resume's effectiveness.

## Features

- **PDF Resume Processing**: Upload and analyze your resume in PDF format
- **Job-Specific Optimization**: Get tailored suggestions based on job title and description
- **Multiple Optimization Types**:
  - ATS Keyword Optimizer
  - Experience Section Enhancer
  - Skills Hierarchy Creator
  - Professional Summary Crafter
  - Education Optimizer
  - Technical Skills Showcase
  - Career Gap Framing
- **Real-time Preview**: View your resume while making changes
- **AI-Powered Analysis**: Leverages advanced language models for intelligent suggestions

## Prerequisites

- Python 3.10 or higher
- PDF resume file
- Create an account at [Nebius Token Factory](https://tokenfactory.nebius.com/)
- Get Nebius [API Keys](https://tokenfactory.nebius.com/)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd rag_apps/resume_optimizer
```

2. Install the required dependencies:

```bash
# Using pip
pip install -r requirements.txt

# Or using uv (recommended)
uv sync
```

3. Create a `.env` file in the project root and add your Nebius API key:

```
NEBIUS_API_KEY=your_api_key_here
```

## Usage

1. Start the application:

```bash
streamlit run main.py
```

2. Open your web browser and navigate to the provided local URL (typically http://localhost:8501)

3. In the application:
   - Upload your resume (PDF format)
   - Enter the job title
   - Provide the job description
   - Select the type of optimization you want
   - Click "Optimize Resume" to get AI-powered suggestions

## How It Works

1. **Resume Upload**: The application processes your PDF resume and extracts its content
2. **Job Analysis**: Analyzes the provided job title and description
3. **AI Processing**: Uses Nebius AI models to:
   - Analyze your resume content
   - Compare it with job requirements
   - Generate targeted improvement suggestions
4. **Optimization**: Provides specific, actionable recommendations based on your selected optimization type

## Optimization Types

- **ATS Keyword Optimizer**: Enhances your resume with relevant keywords for Applicant Tracking Systems
- **Experience Section Enhancer**: Improves the presentation of your work experience
- **Skills Hierarchy Creator**: Organizes your skills based on job requirements
- **Professional Summary Crafter**: Creates a compelling professional summary
- **Education Optimizer**: Optimizes your education section
- **Technical Skills Showcase**: Highlights your technical competencies
- **Career Gap Framing**: Helps address career gaps professionally

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

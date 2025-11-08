# GitHub MCP Agent with Agno

![Demo](./assets/demo.gif)

A powerful GitHub repository exploration tool powered by the Model Context Protocol (MCP) and Nebius Token Factory. This Streamlit application allows you to interact with GitHub repositories using natural language queries.

## Features

- 🔍 Natural language queries for GitHub repositories
- 📊 Multiple query types:
  - Info: Get detailed repository information from README.md
  - Issues: Explore recent issues
  - Pull Requests: View recent merged PRs
  - Repository Activity: Analyze code quality trends
  - Custom: Ask any specific questions about the repository
- 🎯 Interactive UI with Streamlit
- 🔐 Secure API key management
- 📈 Data presented in organized tables with markdown formatting
- 🔗 Direct links to GitHub resources

## Prerequisites

- Python 3.10 or higher
- Docker installed and running
- GitHub Personal Access Token
- Nebius API Key

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd mcp_ai_agents/github_mcp_agent
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Set up your environment variables:
   - Create a `.env` file in the project root
   - Add your API keys:
     ```
     NEBIUS_API_KEY=your_nebius_api_key
     GITHUB_PERSONAL_ACCESS_TOKEN=your_github_token
     ```

## Usage

1. Start the application:

```bash
streamlit run main.py
```

2. Open your browser and navigate to `http://localhost:8501`

3. In the sidebar:

   - Enter your Nebius API key
   - Enter your GitHub Personal Access Token
   - Click "Save Configuration"

4. In the main interface:
   - Enter the repository name (format: owner/repo)
   - Select the query type
   - Enter your query or use the predefined templates
   - Click "Run Query"

> Note: if you get errors on pull, you may have an expired token and need to `docker logout ghcr.io`

## Query Types

- **Info**: Get comprehensive information about the repository from its README.md
- **Issues**: Find and analyze recent issues
- **Pull Requests**: View and analyze recent merged pull requests
- **Repository Activity**: Analyze code quality trends and repository activity
- **Custom**: Ask any specific questions about the repository

## Security

- API keys are stored securely in the session state
- GitHub token is passed securely to the Docker container
- No sensitive data is stored permanently

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

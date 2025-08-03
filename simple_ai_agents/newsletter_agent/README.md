![demo](./demo.gif)

# Newsletter Agent with Agno & FireCrawl 🔥

A powerful AI-powered newsletter generator that creates professional newsletters on any topic using Nebius AI, Agno, and Firecrawl. This application leverages advanced AI models to research, analyze, and generate well-structured newsletters with the latest information from the web.

## Features ✨

- 🔍 Real-time web research using Firecrawl
- 🤖 AI-powered content generation using Nebius AI
- 📝 Professional newsletter formatting with markdown
- ⚡ Customizable search parameters
- 📊 Time-range filtering for content
- 💾 Download newsletters in markdown format
- 🔑 Secure API key management
- 🎯 Example topics for quick starts

## Prerequisites 🛠️

- Python 3.10+
- [Nebius AI API key](https://studio.nebius.com/?modals=create-api-key)
- [Firecrawl API key](https://www.firecrawl.dev/app/api-keys)

## Installation 📥

1. Clone the repository:

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd simple_ai_agent/newsletter_agent
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root and add your API keys:

```env
FIRECRAWL_API_KEY=your_firecrawl_api_key
NEBIUS_API_KEY=your_nebius_api_key
```

## Usage 🚀

1. Start the Streamlit application:

```bash
streamlit run app.py
```

2. Open your web browser and navigate to the provided local URL (typically http://localhost:8501)

3. Enter your API keys in the sidebar (or set them in the .env file)

4. Enter a topic or select from example topics

5. Configure search parameters:

   - Number of articles to include
   - Time range for content

6. Click "Generate Newsletter" to create your newsletter

7. Download the generated newsletter in markdown format

## Newsletter Structure 📑

The generated newsletters follow this structure:

- Compelling Subject Line
- Welcome section with context
- Main Story with key insights
- Featured Content
- Quick Updates
- This Week's Highlights
- Sources & Further Reading

## API Keys 🔑

- **Firecrawl API Key**: Get your API key from [https://firecrawl.dev](https://www.firecrawl.dev/app/api-keys)
- **Nebius API Key**: Your Nebius AI API key from [https://studio.nebius.com/?modals=create-api-key](https://studio.nebius.com/?modals=create-api-key)

## Contributing 🤝

Contributions are welcome! Please feel free to submit a Pull Request.

## License 📄

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments 🙏

- Built with Streamlit
- Powered by Nebius AI
- Web research powered by Firecrawl
- Agent framework by Agno

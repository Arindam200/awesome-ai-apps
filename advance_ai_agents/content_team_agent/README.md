![Demo](./assets/demo.png)

# SEO Content Agent Team with Agno & SerpAPI

AI-powered content optimization workflow for Google AI Search ranking. This advanced multi-agent system helps content teams either optimize existing articles or generate SEO-optimized content briefs before writing.

## Features

- **Two Operation Modes**:

  - **Existing Article Optimization**: Analyze and improve existing content (from URL or pasted text)
  - **Pre-Writing Content Brief**: Generate SEO-optimized guidelines before writing

- **Comprehensive SEO Research**:

  - Google AI Mode & AI Overview analysis
  - Keyword extraction and clustering
  - Related questions and search intent analysis
  - Competitor content analysis

- **Actionable Outputs**:

  - Search insights and keyword research reports
  - Content audit with prioritized recommendations
  - Section-level rewrites with keyword optimization
  - Pre-writing content briefs with structure and guidelines

- **Interactive Streamlit UI**:
  - Clean, modern interface with real-time progress tracking
  - Easy input methods (topic, URL, or title+content)
  - All reports displayed in a flowing document format
  - Dark mode compatible

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or pip
- Nebius API key (get it from [Nebius Token Factory](https://dub.sh/nebius))
- SerpAPI key (for Google AI Mode and AI Overview searches - get it from [SerpAPI](https://serpapi.com/))

## Installation

1. Navigate to the project directory:

```bash
cd advance_ai_agents/content_team_agent
```

2. Install dependencies:

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

3. Set up environment variables:

Create a `.env` file in the project root:

```bash
NEBIUS_API_KEY=your_nebius_api_key_here
SERPAPI_API_KEY=your_serpapi_key_here
```

## Usage

### Streamlit UI (Recommended)

Launch the interactive web interface:

```bash
uv run streamlit run app.py
# or with pip
streamlit run app.py
```

The UI provides:

- **Sidebar Configuration**: Enter your API keys and choose input method
- **Main Area**: Enter your topic, URL, or article content
- **Real-time Progress**: See which step is currently processing
- **Results Display**: All reports displayed in a clean, flowing document format

### Input Methods

1. **Topic Only (Pre-Writing Brief)**

   - Enter a topic you want to write about
   - Get comprehensive SEO content brief with keywords, structure, and guidelines

2. **URL to Existing Article**

   - Provide a URL to an existing article
   - Article is automatically extracted and optimized
   - Full article content is saved for reference

3. **Title + Content**
   - Paste your article title and content directly
   - Get immediate SEO optimization recommendations

### Command Line Interface

You can also run the workflow directly:

```bash
uv run python main.py
# or
python main.py
```

The CLI will prompt you to choose your input method and provide the necessary information.

![results](./assets/results.png)

## Output Reports

All reports and articles are automatically generated and saved to `.tmp/` folder (ignored by git):

### Reports Generated

- **Search Insights & Keyword Research** (`search_insights.md`)

  - Primary and related keywords
  - Related questions and search intent
  - Competitor analysis
  - AI Overview patterns

- **Content Brief** (`content_brief.md`) - Pre-Writing Mode

  - Complete content outline
  - Recommended headings structure
  - FAQ suggestions
  - Keyword placement guidance
  - Writing guidelines

- **Article Audit** (`article_audit.md`) - Optimization Mode

  - Content gaps analysis
  - Keyword opportunities
  - E-E-A-T assessment
  - Structure improvements
  - Prioritized recommendations

- **Section Edits** (`section_edits.md`) - Optimization Mode

  - Optimized section rewrites
  - Natural keyword integration
  - Improved readability
  - SEO enhancements

- **Extracted Articles** (`.tmp/articles/`)
  - Saved articles from URLs
  - Full content for reference
  - Includes source URL and extraction timestamp

## Workflow Architecture

The workflow uses specialized AI agents working together:

1. **Topic Extraction Agent**: Analyzes article content to extract the main topic and title (when URL/content provided)

2. **Search Insights Agent**: Conducts SERP research using Google AI Mode and AI Overview tools

3. **SERP Analysis Agent**: Analyzes raw search results and provides structured keyword insights

4. **Content Strategist Agent**:

   - Generates content briefs (pre-writing mode)
   - Audits existing articles (optimization mode)

5. **SEO Editor Agent**: Rewrites sections with keyword optimization (optimization mode only)

## Technical Details

- **Framework**: [Agno](https://github.com/phidatahq/agno) (multi-agent workflow orchestration)
- **LLM Provider**: [Nebius Token Factory](https://dub.sh/nebius)
  - Tool calling: `moonshotai/Kimi-K2-Instruct`
  - Content writing: `nvidia/Llama-3_1-Nemotron-Ultra-253B-v1`
- **Search APIs**: [SerpAPI](https://serpapi.com/) (Google AI Mode, Google AI Overview)
- **URL Extraction**: Trafilatura (article text extraction)
- **UI Framework**: Streamlit

## Example Use Cases

- **Blog Post Optimization**: Improve existing blog posts for better Google AI Search visibility
- **Content Planning**: Generate SEO-optimized content briefs before writing
- **Keyword Research**: Discover related keywords and questions for content strategy
- **Competitor Analysis**: Understand what top-ranking content includes
- **E-E-A-T Optimization**: Improve Experience, Expertise, Authoritativeness, and Trustworthiness signals
- **Content Refresh**: Update older articles with current SEO best practices

## How It Works

### Pre-Writing Mode Flow

```
Topic Input → Keyword Research → Content Brief Generation → Writing Guidelines
```

1. Enter a topic
2. System researches keywords and SERP patterns
3. Generates comprehensive content brief
4. Provides structure, headings, FAQs, and keyword guidance

### Optimization Mode Flow

```
Article (URL/Content) → Topic Extraction → Keyword Research →
Content Audit → Section Optimization → Improved Article
```

1. Provide article URL or paste content
2. System extracts topic and researches keywords
3. Audits article for SEO improvements
4. Generates optimized section rewrites
5. Provides prioritized recommendations

## Notes

- The workflow preserves the original meaning and value of existing content when optimizing
- Section rewrites focus on high-impact improvements while maintaining readability
- All recommendations are prioritized by impact and ease of implementation
- Reports are generated in Markdown format for easy review and implementation
- Extracted articles are saved for reference and can be accessed later
- All temporary files are stored in `.tmp/` folder (gitignored)

## Troubleshooting

### API Key Issues

- Make sure both Nebius and SerpAPI keys are set in `.env` file or entered in the UI sidebar
- Verify keys are valid and have sufficient credits

### URL Extraction Fails

- Some websites may block automated extraction
- Try using "Title + Content" mode instead
- Check if the URL is accessible and contains readable content

### Reports Not Generated

- Check `.tmp/reports/content_seo/` folder
- Ensure the workflow completed successfully
- Review error messages in the Streamlit UI

## Contributing

This project is part of the [awesome-llm-apps](https://github.com/arindammajumder/awesome-llm-apps) collection. Contributions are welcome!

## License

Part of the awesome-llm-apps repository. See main repository for license information.

## Credits

Developed with ❤️ by [Arindam Majumder](https://www.youtube.com/c/Arindam_1729)

Powered by:

- [Agno](https://github.com/phidatahq/agno) - Multi-agent framework
- [Nebius Token Factory](https://dub.sh/nebius) - LLM inference
- [SerpAPI](https://serpapi.com/) - Google search results

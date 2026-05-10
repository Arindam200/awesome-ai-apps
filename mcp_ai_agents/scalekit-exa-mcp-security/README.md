# Securing MCP servers with [Scalekit](https://www.scalekit.com/)

A Model Context Protocol (MCP) server built on [FastAPI](https://fastapi.tiangolo.com/) that provides access to search [Exa AI Search](https://exa.ai/). The server runs as a remote MCP server on top of a FastAPI app, supporting HTTP transport and modern authentication middleware. This enables AI applications to search for news, get trending headlines, and perform intelligent web searches through a standardized interface with robust security.

> Watch Full Tutorial on [YouTube](https://www.youtube.com/watch?v=uzeDndX1PWU)

## Features

### Exa AI Search Tools
- **`exa_search`** - Intelligent web search using neural and keyword search capabilities
- **`exa_get_contents`** - Retrieve full content for specific search results
- **`exa_find_similar`** - Find web pages similar to a given URL


## Installation & Setup

1. **Install dependencies**
  ```bash
  uv sync
  ```

2. **Get API keys**
  - **Exa API**: Visit [exa.ai](https://exa.ai/), sign up for an account, and get your API key

3. **Set up environment variables**
  ```bash
  export EXA_API_KEY="your_exa_api_key_here"
  ```

4. **Configure authentication**
  - The server uses OAuth2 Bearer token authentication via [ScaleKit](https://www.scalekit.com/). See `auth.py` for details.
  - Set required ScaleKit environment variables in your config (see `config.py`).

## Usage

### Running the Server

The server now runs as a FastAPI application with MCP protocol support and authentication middleware.

**Using uv:**
```bash
uv run main.py
```

The server exposes MCP endpoints over HTTP at:
- **Exa AI service**: `/exa`
- **Service information**: `/` (root endpoint)
- **OAuth metadata**: `/.well-known/oauth-protected-resource/mcp`

### Integration with Other MCP Clients

The server supports the standard MCP protocol and can be used with any MCP-compatible client. Use the stdio transport for local connections.


## Authentication

The server uses OAuth2 Bearer token authentication via ScaleKit. All requests (except for well-known endpoints) require a valid token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Token validation and required scopes are handled by the `AuthMiddleware` (see `auth.py`). Unauthorized requests will receive a structured error response.

## API Reference

### Tools

#### `exa_search`

Search the web using Exa AI's intelligent search capabilities.

**Parameters:**
- `query` (required): The search query string
- `search_type` (optional): "neural", "keyword", "auto", or "fast" (default: "auto")
- `category` (optional): Focus on specific data category (e.g., "research paper", "news", "github")
- `num_results` (optional): Number of results (1-100, default: 10)
- `include_domains` (optional): List of domains to include (e.g., ["arxiv.org", "github.com"])
- `exclude_domains` (optional): List of domains to exclude
- `start_published_date` (optional): Include results published after this date (ISO 8601)
- `end_published_date` (optional): Include results published before this date (ISO 8601)
- `include_content` (optional): Include webpage text content (default: true)
- `include_highlights` (optional): Include highlights of relevant passages (default: true)
- `include_summary` (optional): Include AI-generated summaries (default: true)

**Returns:**
```json
{
  "success": true,
  "query": "search terms",
  "search_type": "auto",
  "resolved_search_type": "neural",
  "request_id": "unique_request_id",
  "num_results": 10,
  "results": [
    {
      "title": "Page Title",
      "url": "https://example.com",
      "id": "unique_result_id",
      "publishedDate": "2024-01-01T12:00:00Z",
      "author": "Author Name",
      "text": "Full page content...",
      "highlights": ["relevant", "passages"],
      "summary": "AI-generated summary..."
    }
  ],
  "cost_dollars": {...}
}
```

#### `exa_get_contents`

Retrieve full content for specific Exa search results.

**Parameters:**
- `ids` (required): List of Exa result IDs
- `include_text` (optional): Include webpage text content (default: true)
- `include_highlights` (optional): Include highlights (default: true)
- `include_summary` (optional): Include AI summaries (default: true)
- `livecrawl` (optional): Use live crawling for up-to-date content (default: false)

#### `exa_find_similar`

Find web pages similar to a given URL.

**Parameters:**
- `url` (required): Reference URL to find similar content
- `num_results` (optional): Number of results (1-100, default: 10)
- `include_domains` (optional): List of domains to include
- `exclude_domains` (optional): List of domains to exclude
- Content options: same as `exa_search`


## Example Usage in Windsurf

### MCP Server Configuration: 

```
{
    "mcpServers": {
      "demo-ngrok": {
        "command": "bash",
        "args": [
          "-c", 
          "source $HOME/.nvm/nvm.sh && nvm use 20 && npx -y mcp-remote https://95929ff2edec.ngrok-free.app/mcp"
        ]
      }
    }
  }

```

After setting up the server, you can use it in Windsurf or any MCP client:

### Web Search Examples (Exa AI)
```
"Search for recent research papers about large language models"
"Find GitHub repositories related to machine learning frameworks"
"Search for company information about AI startups founded in 2023"
"Find similar content to this research paper: https://arxiv.org/abs/2307.06435"
"Get comprehensive content about quantum computing breakthroughs"
```

The server will automatically use the appropriate tools and provide structured, comprehensive results from both news and web sources, with authentication and security enforced.

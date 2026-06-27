# Constitutional AI Multi-Agent System

A production-grade 6-agent Constitutional AI pipeline built with LangGraph and Amazon Bedrock (Claude 3 Sonnet). Enforces harmlessness, helpfulness, and honesty at every stage of response generation.

## Features

- 6 specialized agents in a directed LangGraph pipeline
- Constitutional AI principles enforced at every step
- Real-time streaming with agent status updates
- Full observability via LangGraph Studio integration
- Session isolation — supports multiple concurrent users
- Docker-ready with FastAPI backend and Streamlit UI

## Tech Stack

| Component | Technology |
|-----------|------------|
| LLM | Amazon Bedrock (Claude 3 Sonnet) |
| Orchestration | LangGraph (StateGraph) |
| Backend | FastAPI + Python 3.11 |
| Frontend | Streamlit |
| Containerization | Docker + Docker Compose |

## Agent Pipeline

```
InputValidator → ContentAnalyzer → ConstitutionalChecker → ResponseGenerator → QualityAssurer → OutputFormatter
```

1. **InputValidatorAgent** — Sanitizes and validates user input
2. **ContentAnalyzerAgent** — Identifies topics, intent, and risk level
3. **ConstitutionalCheckerAgent** — Evaluates against 5 constitutional principles
4. **ResponseGeneratorAgent** — Generates response using Amazon Bedrock
5. **QualityAssurerAgent** — Scores response quality and safety (0–100)
6. **OutputFormatterAgent** — Formats final output with metadata

## Setup

```bash
git clone https://github.com/Rajeshdevandla/agent-flow
cd agent-flow
cp .env.example .env
# Add your AWS credentials to .env
docker-compose up --build
```

## Environment Variables

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
```

## Live Demo

[View on GitHub](https://github.com/Rajeshdevandla/agent-flow)

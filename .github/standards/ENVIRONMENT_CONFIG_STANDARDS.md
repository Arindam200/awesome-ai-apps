# Environment Configuration Standards

This guide establishes consistent standards for environment variable configuration across all projects.

## 🎯 Objectives

- **Clear documentation** of all required and optional environment variables
- **Secure defaults** that don't expose sensitive information
- **Easy setup** with links to obtain API keys
- **Comprehensive comments** explaining each variable's purpose
- **Consistent naming** following industry standards

## 📋 .env.example Template

### Basic Template Structure
```bash
# =============================================================================
# {PROJECT_NAME} Environment Configuration
# =============================================================================
# Copy this file to .env and fill in your actual values
# IMPORTANT: Never commit .env files to version control
#
# Quick setup: cp .env.example .env
# Then edit .env with your actual API keys and configuration

# =============================================================================
# Required Configuration
# =============================================================================

# Nebius AI API Key (Required for all AI operations)
# Description: Primary LLM provider for the application
# Get your key: https://studio.nebius.ai/api-keys
# Documentation: https://docs.nebius.ai/
NEBIUS_API_KEY="your_nebius_api_key_here"

# =============================================================================
# Optional Configuration
# =============================================================================

# OpenAI API Key (Optional - Alternative LLM provider)
# Description: Fallback or alternative LLM provider
# Get your key: https://platform.openai.com/account/api-keys
# Usage: Only needed if using OpenAI models instead of Nebius
# OPENAI_API_KEY="your_openai_api_key_here"

# =============================================================================
# Application Settings
# =============================================================================

# Application Environment (Optional)
# Description: Runtime environment for the application
# Values: development, staging, production
# Default: development
# APP_ENV="development"

# Log Level (Optional)
# Description: Controls logging verbosity
# Values: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Default: INFO
# LOG_LEVEL="INFO"

# =============================================================================
# Service-Specific Configuration
# =============================================================================
# Add service-specific variables here based on project needs
```

### Enhanced Template for Web Applications
```bash
# =============================================================================
# {PROJECT_NAME} Environment Configuration
# =============================================================================

# =============================================================================
# Required Configuration
# =============================================================================

# Primary AI Provider
NEBIUS_API_KEY="your_nebius_api_key_here"
# Get from: https://studio.nebius.ai/api-keys

# =============================================================================
# Web Application Settings
# =============================================================================

# Server Configuration (Optional)
# Description: Web server host and port settings
# Default: localhost:8501 for Streamlit, localhost:8000 for FastAPI
# HOST="localhost"
# PORT="8501"

# Application Title (Optional)
# Description: Display name for the web application
# Default: Project name from pyproject.toml
# APP_TITLE="Your App Name"

# =============================================================================
# External Services (Optional)
# =============================================================================

# Web Search API (Optional - for research capabilities)
# Description: Enables web search functionality
# Providers: Choose one of the following

# Tavily API (Recommended for research)
# Get from: https://tavily.com/
# TAVILY_API_KEY="your_tavily_api_key_here"

# Exa API (Alternative for web search)
# Get from: https://exa.ai/
# EXA_API_KEY="your_exa_api_key_here"

# =============================================================================
# Data Storage (Optional)
# =============================================================================

# Vector Database Configuration (Optional - for RAG applications)
# Choose based on your vector database provider

# Pinecone (Managed vector database)
# Get from: https://pinecone.io/
# PINECONE_API_KEY="your_pinecone_api_key"
# PINECONE_ENVIRONMENT="your_pinecone_environment"
# PINECONE_INDEX="your_index_name"

# Qdrant (Self-hosted or cloud)
# Get from: https://qdrant.tech/
# QDRANT_URL="your_qdrant_url"
# QDRANT_API_KEY="your_qdrant_api_key"

# =============================================================================
# Monitoring and Analytics (Optional)
# =============================================================================

# LangSmith (Optional - for LLM observability)
# Get from: https://langchain.com/langsmith
# LANGCHAIN_TRACING_V2="true"
# LANGCHAIN_PROJECT="your_project_name"
# LANGCHAIN_API_KEY="your_langsmith_api_key"

# AgentOps (Optional - for agent monitoring)
# Get from: https://agentops.ai/
# AGENTOPS_API_KEY="your_agentops_api_key"

# =============================================================================
# Development Settings (Optional)
# =============================================================================

# Debug Mode (Development only)
# Description: Enables detailed error messages and debugging
# Values: true, false
# Default: false
# DEBUG="false"

# Async Settings (For async applications)
# Description: Maximum concurrent operations
# Default: 10
# MAX_CONCURRENT_REQUESTS="10"

# =============================================================================
# Security Settings (Optional)
# =============================================================================

# Secret Key (For session management)
# Description: Used for encrypting sessions and cookies
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
# SECRET_KEY="your_generated_secret_key_here"

# CORS Origins (For FastAPI applications)
# Description: Allowed origins for cross-origin requests
# Example: http://localhost:3000,https://yourdomain.com
# CORS_ORIGINS="http://localhost:3000"

# =============================================================================
# Additional Notes
# =============================================================================
#
# API Rate Limits:
# - Nebius AI: 100 requests/minute on free tier
# - OpenAI: Varies by subscription plan
# - Tavily: 1000 searches/month on free tier
#
# Cost Considerations:
# - Monitor your API usage to avoid unexpected charges
# - Consider setting up billing alerts
# - Start with free tiers and upgrade as needed
#
# Security Best Practices:
# - Never share your .env file
# - Use different API keys for development and production
# - Regularly rotate your API keys
# - Monitor API key usage for unauthorized access
#
# Troubleshooting:
# - If environment variables aren't loading, check file name (.env not .env.txt)
# - Ensure no spaces around the = sign
# - Quote values with special characters
# - Restart your application after changing variables
```

## 🔧 Category-Specific Templates

### Starter Agents (.env.example)
```bash
# =============================================================================
# {Framework} Starter Agent - Environment Configuration
# =============================================================================
# This is a learning project demonstrating {framework} capabilities
# Required: Only basic AI provider API key

# Primary AI Provider (Required)
NEBIUS_API_KEY="your_nebius_api_key_here"
# Get from: https://studio.nebius.ai/api-keys
# Free tier: 100 requests/minute

# Learning Features (Optional)
# Uncomment to enable additional features as you learn

# Alternative AI Provider (Optional)
# OPENAI_API_KEY="your_openai_api_key_here"
# Get from: https://platform.openai.com/account/api-keys

# Debug Mode (Recommended for learning)
# DEBUG="true"
```

### RAG Applications (.env.example)
```bash
# =============================================================================
# RAG Application - Environment Configuration
# =============================================================================

# =============================================================================
# Required Configuration
# =============================================================================

# AI Provider for LLM and Embeddings
NEBIUS_API_KEY="your_nebius_api_key_here"
# Get from: https://studio.nebius.ai/api-keys

# Vector Database (Choose one)
# Option 1: Pinecone (Recommended for beginners)
PINECONE_API_KEY="your_pinecone_api_key"
PINECONE_ENVIRONMENT="your_environment"  # e.g., us-west1-gcp
PINECONE_INDEX="your_index_name"         # e.g., documents-index
# Get from: https://pinecone.io/

# Option 2: Qdrant (Self-hosted or cloud)
# QDRANT_URL="your_qdrant_url"           # e.g., http://localhost:6333
# QDRANT_API_KEY="your_qdrant_api_key"   # For Qdrant Cloud only

# =============================================================================
# Document Processing Settings
# =============================================================================

# Embedding Model Configuration
EMBEDDING_MODEL="BAAI/bge-large-en-v1.5"  # Default embedding model
EMBEDDING_DIMENSION="1024"                # Dimension for the chosen model

# Chunking Strategy
CHUNK_SIZE="1000"           # Characters per chunk
CHUNK_OVERLAP="200"         # Overlap between chunks

# =============================================================================
# Optional Features
# =============================================================================

# Web Search (For hybrid RAG)
# TAVILY_API_KEY="your_tavily_api_key"
# Get from: https://tavily.com/

# Document Monitoring
# AGENTOPS_API_KEY="your_agentops_api_key"
# Get from: https://agentops.ai/
```

### MCP Agents (.env.example)
```bash
# =============================================================================
# MCP Agent - Environment Configuration
# =============================================================================

# =============================================================================
# Required Configuration
# =============================================================================

# AI Provider
NEBIUS_API_KEY="your_nebius_api_key_here"
# Get from: https://studio.nebius.ai/api-keys

# =============================================================================
# MCP Server Configuration
# =============================================================================

# MCP Server Settings
MCP_SERVER_NAME="your_server_name"      # e.g., "document-tools"
MCP_SERVER_VERSION="1.0.0"              # Server version
MCP_SERVER_HOST="localhost"             # Server host
MCP_SERVER_PORT="3000"                  # Server port

# MCP Transport (Optional)
# Values: stdio, sse, websocket
# Default: stdio
# MCP_TRANSPORT="stdio"

# =============================================================================
# Tool-Specific Configuration
# =============================================================================

# Database Tools (if applicable)
# DATABASE_URL="your_database_connection_string"

# File System Tools (if applicable)
# ALLOWED_DIRECTORIES="/path/to/safe/directory"

# Web Tools (if applicable)
# ALLOWED_DOMAINS="example.com,api.service.com"

# =============================================================================
# Security Settings
# =============================================================================

# Tool Permissions (Recommended)
ENABLE_FILE_OPERATIONS="false"          # Allow file read/write
ENABLE_NETWORK_ACCESS="false"           # Allow network requests
ENABLE_DATABASE_ACCESS="false"          # Allow database operations

# Sandbox Mode (Development)
SANDBOX_MODE="true"                      # Restrict dangerous operations
```

### Advanced AI Agents (.env.example)
```bash
# =============================================================================
# Advanced AI Agent - Environment Configuration
# =============================================================================

# =============================================================================
# Required Configuration
# =============================================================================

# Primary AI Provider
NEBIUS_API_KEY="your_nebius_api_key_here"
# Get from: https://studio.nebius.ai/api-keys

# =============================================================================
# Multi-Agent Configuration
# =============================================================================

# Agent Coordination
MAX_CONCURRENT_AGENTS="5"               # Maximum agents running simultaneously
AGENT_TIMEOUT="300"                     # Timeout in seconds for agent tasks
AGENT_RETRY_ATTEMPTS="3"                # Retry failed tasks

# Agent Communication
SHARED_MEMORY_SIZE="1024"               # MB for shared agent memory
ENABLE_AGENT_LOGGING="true"             # Log inter-agent communication

# =============================================================================
# External Services
# =============================================================================

# Web Search and Research
TAVILY_API_KEY="your_tavily_api_key"
EXA_API_KEY="your_exa_api_key"

# Data Sources
FIRECRAWL_API_KEY="your_firecrawl_api_key"  # For web scraping
NEWS_API_KEY="your_news_api_key"            # For news data

# Financial Data (if applicable)
ALPHA_VANTAGE_API_KEY="your_av_api_key"     # Stock data
POLYGON_API_KEY="your_polygon_api_key"      # Market data

# =============================================================================
# Performance and Monitoring
# =============================================================================

# Observability
LANGCHAIN_TRACING_V2="true"
LANGCHAIN_PROJECT="advanced_agent"
LANGCHAIN_API_KEY="your_langsmith_api_key"

AGENTOPS_API_KEY="your_agentops_api_key"

# Performance Tuning
REQUEST_TIMEOUT="60"                     # API request timeout
BATCH_SIZE="10"                         # Batch processing size
CACHE_TTL="3600"                        # Cache time-to-live (seconds)

# =============================================================================
# Production Settings
# =============================================================================

# Environment
APP_ENV="development"                    # development, staging, production
LOG_LEVEL="INFO"                        # DEBUG, INFO, WARNING, ERROR

# Security
SECRET_KEY="your_generated_secret_key"
CORS_ORIGINS="http://localhost:3000"

# Database (if applicable)
DATABASE_URL="your_database_url"
REDIS_URL="your_redis_url"              # For caching
```

## 📝 Environment Variable Naming Conventions

### Standard Patterns
- **API Keys**: `{SERVICE}_API_KEY` (e.g., `NEBIUS_API_KEY`)
- **URLs**: `{SERVICE}_URL` (e.g., `DATABASE_URL`, `REDIS_URL`)
- **Configuration**: `{COMPONENT}_{SETTING}` (e.g., `AGENT_TIMEOUT`)
- **Feature Flags**: `ENABLE_{FEATURE}` (e.g., `ENABLE_DEBUG`)
- **Limits**: `MAX_{RESOURCE}` (e.g., `MAX_CONCURRENT_AGENTS`)

### Reserved Names (Avoid)
- `PATH`, `HOME`, `USER` - System variables
- `DEBUG` - Use `APP_DEBUG` instead for clarity
- `PORT` - Use `APP_PORT` or `SERVER_PORT`
- `HOST` - Use `APP_HOST` or `SERVER_HOST`

## 🔒 Security Best Practices

### File Security
```bash
# Add to .gitignore
.env
.env.local
.env.*.local
*.env
api.env

# Set proper file permissions (Unix/Linux)
chmod 600 .env
```

### Key Management
- **Development**: Use separate API keys with limited permissions
- **Production**: Implement key rotation policies
- **CI/CD**: Use encrypted secrets, never plain text
- **Monitoring**: Set up alerts for unusual API usage

### Documentation Security
```bash
# Example secure documentation in .env.example
# IMPORTANT: This is an example file only
# Real values should be in .env (which is gitignored)
# Never commit actual API keys to version control

# Generate secure secret keys:
# python -c "import secrets; print(secrets.token_hex(32))"
```

## ✅ Validation Checklist

### For Each .env.example File
- [ ] **Complete documentation** for every variable
- [ ] **Links provided** to obtain all API keys
- [ ] **No real values** included (only placeholders)
- [ ] **Grouped logically** with clear section headers
- [ ] **Comments explain** purpose and usage
- [ ] **Defaults specified** where applicable
- [ ] **Security notes** included
- [ ] **Troubleshooting tips** provided

### Testing
- [ ] Copy to .env and verify application starts
- [ ] Test with minimal required variables only
- [ ] Verify all optional features work when enabled
- [ ] Check error messages for missing variables are clear

### Maintenance
- [ ] Update when new features require environment variables
- [ ] Remove variables that are no longer used
- [ ] Keep API key links current
- [ ] Update default values when dependencies change

## 🚀 Advanced Features

### Environment Validation Script
```python
# validate_env.py - Include in development utilities
import os
import sys
from typing import Dict, List, Optional

def validate_environment() -> bool:
    """Validate required environment variables."""
    required_vars = [
        "NEBIUS_API_KEY",
        # Add other required variables
    ]
    
    optional_vars = [
        "OPENAI_API_KEY",
        "DEBUG",
        # Add other optional variables
    ]
    
    missing_required = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)
    
    if missing_required:
        print("❌ Missing required environment variables:")
        for var in missing_required:
            print(f"   - {var}")
        print("\n📝 Please check your .env file against .env.example")
        return False
    
    print("✅ All required environment variables are set")
    
    # Check optional variables
    missing_optional = [var for var in optional_vars if not os.getenv(var)]
    if missing_optional:
        print("ℹ️  Optional environment variables not set:")
        for var in missing_optional:
            print(f"   - {var}")
    
    return True

if __name__ == "__main__":
    if not validate_environment():
        sys.exit(1)
```

### Dynamic .env.example Generation
```python
# generate_env_example.py - Development utility
def generate_env_example(project_config: dict) -> str:
    """Generate .env.example based on project configuration."""
    template = f"""# =============================================================================
# {project_config['name']} Environment Configuration
# =============================================================================

# Required Configuration
NEBIUS_API_KEY="your_nebius_api_key_here"
# Get from: https://studio.nebius.ai/api-keys
"""
    
    # Add service-specific variables based on project type
    if project_config.get('type') == 'rag':
        template += """
# Vector Database
PINECONE_API_KEY="your_pinecone_api_key"
PINECONE_ENVIRONMENT="your_environment"
PINECONE_INDEX="your_index_name"
"""
    
    return template
```

This comprehensive environment configuration standard ensures secure, well-documented, and consistent setup across all projects in the repository.
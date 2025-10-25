# Code Quality Tools

This directory contains automated tools for maintaining code quality across the repository.

## comprehensive_code_quality_fixer.py

A comprehensive automated tool that addresses repository-wide code quality improvements.

### Features

- **Trailing Whitespace Fixes**: Removes trailing whitespace (W291) and ensures newlines at end of files (W292)
- **Import Sorting**: Organizes imports following standard conventions - standard library → third-party → local imports (I001)
- **Documentation Enhancement**: Upgrades `.env.example` files from basic templates to comprehensive configuration guides
- **Security & Indentation**: Fixes mixed tabs/spaces and indentation-related security issues

### Usage

```bash
# Run in dry-run mode (preview changes without applying them)
python .github/tools/comprehensive_code_quality_fixer.py . --dry-run

# Run with verbose logging
python .github/tools/comprehensive_code_quality_fixer.py . --verbose

# Apply fixes to the repository
python .github/tools/comprehensive_code_quality_fixer.py .
```

### Output Example

```
Trailing whitespace fixes: 145
Import sorting fixes: 129
Environment documentation fixes: 20
Security/indentation fixes: 4
Total fixes applied: 298
```

### What Gets Fixed

#### 1. Trailing Whitespace & Newlines
- Removes spaces at the end of lines
- Ensures files end with a single newline character
- Resolves Ruff violations: W291, W292

#### 2. Import Organization
- Separates imports into groups: standard library, third-party, local
- Sorts imports alphabetically within each group
- Resolves Ruff violations: I001

**Before:**
```python
from openai import OpenAI
import os
from crewai_tools import QdrantVectorSearchTool
import uuid
```

**After:**
```python
import os
import uuid

from crewai_tools import QdrantVectorSearchTool
from openai import OpenAI
```

#### 3. .env.example Enhancement
Transforms basic API key templates into comprehensive configuration guides with:
- Header sections with clear instructions
- Detailed comments for each variable
- Links to get API keys
- Usage limits and free tier information
- Troubleshooting sections
- Security best practices

**Before:**
```bash
NEBIUS_API_KEY="Your Nebius API Key"
```

**After:**
```bash
# =============================================================================
# project_name - Environment Configuration
# =============================================================================
# Copy this file to .env and fill in your actual values
# IMPORTANT: Never commit .env files to version control
#
# Quick setup: cp .env.example .env

# =============================================================================
# Required Configuration
# =============================================================================

# Nebius AI API Key (Required)
# Description: Primary LLM provider for project_name
# Get your key: https://studio.nebius.ai/api-keys
# Free tier: 100 requests/minute, perfect for learning
# Documentation: https://docs.nebius.ai/
NEBIUS_API_KEY="Your Nebius API Key"

# [... additional sections with troubleshooting, security notes, etc.]
```

#### 4. Security & Indentation
- Converts tabs to consistent 4-space indentation
- Fixes mixed indentation that could cause security issues
- Ensures consistent code formatting

### Integration with CI/CD

This tool is designed to work with the repository's quality assurance workflow and can be integrated into pre-commit hooks or CI/CD pipelines.

### Related

- Issue #77: Repository-wide Documentation & Code Quality Standardization Initiative
- Part of the comprehensive code quality improvement effort

### Notes

- Always review changes before committing, especially when running without `--dry-run`
- The tool is idempotent - running it multiple times produces the same result
- Excludes test files and `__init__.py` files by default for import sorting

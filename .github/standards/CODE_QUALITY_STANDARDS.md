# 🔧 Code Quality Standards

## 📋 Overview

This guide establishes comprehensive code quality standards for all Python projects in the awesome-ai-apps repository. These standards ensure consistency, maintainability, and professional-grade code across all AI applications.

## 🎯 Core Quality Principles

### 1. Type Hints (Python 3.10+)
- **Required**: All function parameters and return types
- **Optional**: Variable annotations for complex types
- **Import**: Use `from typing import` for compatibility

```python
from typing import List, Dict, Optional, Union, Any
from pathlib import Path
import logging

def process_documents(
    file_paths: List[Path], 
    config: Dict[str, Any],
    output_dir: Optional[Path] = None
) -> Dict[str, Union[str, int]]:
    """Process multiple documents and return summary statistics."""
    pass
```

### 2. Logging Standards
- **Replace**: All `print()` statements with proper logging
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Format**: Consistent timestamp and level formatting
- **Configuration**: Centralized logging setup

```python
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def example_function():
    logger.info("Starting process...")
    logger.debug("Debug information here")
    logger.warning("Warning message")
    logger.error("Error occurred")
```

### 3. Error Handling
- **Specific Exceptions**: Catch specific exception types
- **Logging**: Log all exceptions with context
- **Recovery**: Implement graceful fallbacks where possible
- **User-Friendly**: Provide meaningful error messages

```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def safe_file_operation(file_path: Path) -> Optional[str]:
    """Safely read file with comprehensive error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            logger.info(f"Successfully read file: {file_path}")
            return content
    
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return None
    
    except PermissionError:
        logger.error(f"Permission denied accessing: {file_path}")
        return None
    
    except UnicodeDecodeError as e:
        logger.error(f"Encoding error reading {file_path}: {e}")
        return None
    
    except Exception as e:
        logger.error(f"Unexpected error reading {file_path}: {e}")
        return None
```

### 4. Docstring Standards (Google Style)
- **Module**: Brief description at top
- **Classes**: Purpose and key attributes
- **Functions**: Args, Returns, Raises, Examples

```python
def calculate_similarity(
    text1: str, 
    text2: str, 
    method: str = "cosine"
) -> float:
    """Calculate similarity between two text strings.
    
    Args:
        text1: First text string for comparison
        text2: Second text string for comparison  
        method: Similarity calculation method ("cosine", "jaccard", "levenshtein")
        
    Returns:
        Similarity score between 0.0 and 1.0
        
    Raises:
        ValueError: If method is not supported
        
    Examples:
        >>> calculate_similarity("hello world", "hello earth")
        0.707
        >>> calculate_similarity("python", "python", method="cosine")
        1.0
    """
    pass
```

## 📁 Project Structure Standards

### File Organization
```
project_name/
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration management
│   ├── utils.py             # Utility functions
│   └── modules/
│       ├── __init__.py
│       └── feature.py
├── tests/
│   ├── __init__.py
│   ├── test_main.py
│   └── test_utils.py
├── logs/
├── pyproject.toml
├── README.md
└── .env.example
```

### Import Standards
```python
# Standard library imports
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Third-party imports
import pandas as pd
import numpy as np
from pydantic import BaseModel

# Local application imports
from .config import settings
from .utils import helper_function
```

## 🛠️ Implementation Checklist

### For Each Python File:

#### ✅ Type Hints
- [ ] All function parameters have type hints
- [ ] All function return types specified
- [ ] Complex variables annotated
- [ ] Import necessary typing modules

#### ✅ Logging
- [ ] Replace all `print()` with `logger.*`
- [ ] Configure logging at module level
- [ ] Use appropriate log levels
- [ ] Include context in log messages

#### ✅ Error Handling
- [ ] Specific exception catching
- [ ] Log all exceptions
- [ ] Graceful error recovery
- [ ] User-friendly error messages

#### ✅ Documentation
- [ ] Module docstring
- [ ] Class docstrings
- [ ] Function docstrings (Args, Returns, Raises)
- [ ] Complex logic comments

#### ✅ Code Structure
- [ ] Consistent import organization
- [ ] Logical function grouping
- [ ] Appropriate file naming
- [ ] Clean code principles

## 🔄 Automation Tools

### Quality Check Script
```python
# quality_check.py
"""Automated code quality validation."""

import ast
import logging
from pathlib import Path
from typing import List, Dict, Any

def check_type_hints(file_path: Path) -> Dict[str, Any]:
    """Check if file has proper type hints."""
    # Implementation details
    pass

def check_logging_usage(file_path: Path) -> Dict[str, Any]:
    """Verify logging instead of print statements."""
    # Implementation details
    pass

def check_docstrings(file_path: Path) -> Dict[str, Any]:
    """Validate docstring presence and format."""
    # Implementation details
    pass
```

## 📊 Quality Metrics

### Code Quality Scoring
- **Type Hints**: 25 points
- **Logging**: 25 points  
- **Error Handling**: 25 points
- **Documentation**: 25 points
- **Total**: 100 points

### Minimum Standards
- **Type Hints**: 80% coverage
- **Logging**: No print statements in production code
- **Error Handling**: All file operations and API calls protected
- **Documentation**: All public functions documented

## 🚀 Implementation Strategy

### Phase 3A: Core Projects
1. **starter_ai_agents**: Templates and examples
2. **simple_ai_agents**: Basic implementations
3. **rag_apps**: RAG applications

### Phase 3B: Advanced Projects  
1. **advance_ai_agents**: Complex multi-agent systems
2. **mcp_ai_agents**: MCP protocol implementations
3. **memory_agents**: Memory-enhanced applications

### Phase 3C: Automation
1. **Quality check scripts**
2. **Pre-commit hooks**
3. **CI/CD integration**

## 🔍 Code Review Standards

### Pre-Merge Requirements
- [ ] All functions have type hints
- [ ] No print statements (except debugging)
- [ ] Proper error handling
- [ ] Complete docstrings
- [ ] Logging configured
- [ ] Quality score > 80%

### Tools Integration
- **mypy**: Type checking
- **black**: Code formatting  
- **flake8**: Linting
- **pytest**: Testing
- **pre-commit**: Automated checks

---

*This guide ensures all Python code in awesome-ai-apps meets professional development standards and maintains consistency across the entire repository.*
# UV Migration and Dependency Management Standards

This guide standardizes the migration from pip to uv and establishes consistent dependency management across all projects.

## 🎯 Migration Goals

- **Standardize on uv** for faster, more reliable dependency management
- **Version pinning** for reproducible builds
- **pyproject.toml** as the single source of truth for project metadata
- **Consistent Python version requirements** (3.10+ recommended)
- **Development dependencies** properly separated

## 📋 Migration Checklist

### For Each Project:

- [ ] Create `pyproject.toml` with project metadata
- [ ] Convert `requirements.txt` to `pyproject.toml` dependencies
- [ ] Add version constraints for all dependencies
- [ ] Include development dependencies section
- [ ] Update README installation instructions
- [ ] Test installation with `uv sync`
- [ ] Remove old `requirements.txt` (optional, for transition period)

## 🔧 Standard pyproject.toml Template

```toml
[project]
name = "{project-name}"
version = "0.1.0"
description = "{Brief description of the project}"
authors = [
    {name = "Arindam Majumder", email = "arindammajumder2020@gmail.com"}
]
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
keywords = ["ai", "agent", "{framework}", "{domain}"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

dependencies = [
    # Core AI frameworks - always pin major versions
    "agno>=1.5.1,<2.0.0",
    "openai>=1.78.1,<2.0.0",
    
    # Utilities - pin to compatible ranges
    "python-dotenv>=1.1.0,<2.0.0",
    "requests>=2.31.0,<3.0.0",
    "pydantic>=2.5.0,<3.0.0",
    
    # Web frameworks (if applicable)
    "streamlit>=1.28.0,<2.0.0",
    "fastapi>=0.104.0,<1.0.0",
    "uvicorn>=0.24.0,<1.0.0",
    
    # Data processing (if applicable)
    "pandas>=2.1.0,<3.0.0",
    "numpy>=1.24.0,<2.0.0",
]

[project.optional-dependencies]
dev = [
    # Code formatting and linting
    "black>=23.9.1",
    "ruff>=0.1.0",
    "isort>=5.12.0",
    
    # Type checking
    "mypy>=1.5.1",
    "types-requests>=2.31.0",
    
    # Testing
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
    
    # Documentation
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.4.0",
]

test = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
]

docs = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.4.0",
]

[project.urls]
Homepage = "https://github.com/Arindam200/awesome-ai-apps"
Repository = "https://github.com/Arindam200/awesome-ai-apps"
Issues = "https://github.com/Arindam200/awesome-ai-apps/issues"
Documentation = "https://github.com/Arindam200/awesome-ai-apps/tree/main/{category}/{project-name}"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.black]
line-length = 88
target-version = ['py310']
include = '\\.pyi?$'
extend-exclude = '''
/(
  # directories
  \\.eggs
  | \\.git
  | \\.hg
  | \\.mypy_cache
  | \\.tox
  | \\.venv
  | build
  | dist
)/
'''

[tool.ruff]
target-version = "py310"
line-length = 88
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
    "C4", # flake8-comprehensions
    "UP", # pyupgrade
]
ignore = [
    "E501",  # line too long, handled by black
    "B008",  # do not perform function calls in argument defaults
    "C901",  # too complex
]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]

[tool.mypy]
python_version = "3.10"
check_untyped_defs = true
disallow_any_generics = true
disallow_incomplete_defs = true
disallow_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_unreachable = true
strict_equality = true

[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra -q --strict-markers --strict-config"
testpaths = ["tests"]
filterwarnings = [
    "error",
    "ignore::UserWarning",
    "ignore::DeprecationWarning",
]
```

## 📦 Dependency Version Guidelines

### Version Pinning Strategy

1. **Major Version Constraints**: Use `>=X.Y.Z,<(X+1).0.0` for core dependencies
2. **Minor Version Updates**: Allow minor updates `>=X.Y.Z,<X.(Y+1).0` for stable libraries  
3. **Exact Pinning**: Use `==X.Y.Z` only for known problematic libraries
4. **Development Dependencies**: More relaxed pinning acceptable

### Core Dependencies Standards

```toml
# AI/ML Frameworks - Conservative pinning
"agno>=1.5.1,<2.0.0"           # Major version lock
"openai>=1.78.1,<2.0.0"        # API breaking changes expected
"langchain>=0.1.0,<0.2.0"      # Rapid development
"llamaindex>=0.10.0,<0.11.0"   # Frequent updates

# Web Frameworks - Stable pinning  
"streamlit>=1.28.0,<2.0.0"     # Stable API
"fastapi>=0.104.0,<1.0.0"      # Pre-1.0, conservative
"flask>=3.0.0,<4.0.0"          # Mature, stable

# Utilities - Relaxed pinning
"requests>=2.31.0,<3.0.0"      # Very stable
"python-dotenv>=1.0.0,<2.0.0"  # Simple, stable
"pydantic>=2.5.0,<3.0.0"       # V2 is stable
```

## 🚀 Migration Process

### Step 1: Assessment
```bash
# Navigate to project directory
cd awesome-ai-apps/{category}/{project-name}

# Check current dependencies
cat requirements.txt

# Check for existing pyproject.toml
ls -la | grep pyproject
```

### Step 2: Create pyproject.toml
```bash
# Use template above, customize for project
# Update project name, description, dependencies
```

### Step 3: Install uv (if not present)
```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Verify installation
uv --version
```

### Step 4: Test Migration
```bash
# Create new virtual environment
uv venv

# Install dependencies
uv sync

# Test the application
uv run python main.py
# or
uv run streamlit run app.py
```

### Step 5: Update Documentation
- Update README.md installation instructions
- Add uv commands to usage section
- Update .env.example if needed
- Test all documented steps

## 🔄 Migration Script

Here's a PowerShell script to automate common migration tasks:

```powershell
# migrate-to-uv.ps1
param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectPath,
    
    [Parameter(Mandatory=$true)]
    [string]$ProjectName,
    
    [string]$Description = "AI agent application"
)

$projectToml = @"
[project]
name = "$ProjectName"
version = "0.1.0"
description = "$Description"
authors = [
    {name = "Arindam Majumder", email = "arindammajumder2020@gmail.com"}
]
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}

dependencies = [
"@

# Read existing requirements.txt and convert
if (Test-Path "$ProjectPath/requirements.txt") {
    $requirements = Get-Content "$ProjectPath/requirements.txt" | Where-Object { $_ -and !$_.StartsWith("#") }
    
    foreach ($req in $requirements) {
        $req = $req.Trim()
        if ($req) {
            # Add basic version constraints
            if (!$req.Contains("=") -and !$req.Contains(">") -and !$req.Contains("<")) {
                $projectToml += "`n    `"$req>=0.1.0`","
            } else {
                $projectToml += "`n    `"$req`","
            }
        }
    }
}

$projectToml += @"

]

[project.urls]
Homepage = "https://github.com/Arindam200/awesome-ai-apps"
Repository = "https://github.com/Arindam200/awesome-ai-apps"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"@

# Write pyproject.toml
$projectToml | Out-File -FilePath "$ProjectPath/pyproject.toml" -Encoding utf8

Write-Host "Created pyproject.toml for $ProjectName"
Write-Host "Please review and adjust version constraints manually"
```

## 📊 Quality Checks

### Pre-Migration Checklist
- [ ] Document current working state
- [ ] Back up existing requirements.txt
- [ ] Test current installation process
- [ ] Note any special installation requirements

### Post-Migration Validation
- [ ] `uv sync` completes without errors
- [ ] Application starts correctly with `uv run`
- [ ] All features work as expected
- [ ] README instructions updated and tested
- [ ] No missing dependencies identified

### Common Issues and Solutions

**Issue**: uv sync fails with conflicting dependencies
**Solution**: Review version constraints, use `uv tree` to debug conflicts

**Issue**: Application fails to start after migration  
**Solution**: Check for missing optional dependencies, verify Python version

**Issue**: Performance regression
**Solution**: Ensure uv is using system Python, not building from source

## 🎯 Category-Specific Considerations

### Starter Agents
- Keep dependencies minimal for learning purposes
- Include detailed comments explaining each dependency
- Provide alternative installation methods

### Advanced Agents  
- More complex dependency trees acceptable
- Include performance-critical version pins
- Document any compile-time dependencies

### RAG Applications
- Vector database dependencies often have specific requirements
- Document GPU vs CPU installation differences
- Include optional dependencies for different embedding models

### MCP Agents
- MCP framework dependencies must be compatible
- Server/client version alignment critical
- Include debugging and development tools

## 📝 Documentation Standards

### README Installation Section
```markdown
## ⚙️ Installation

### Using uv (Recommended)

1. **Install uv** (if not already installed):
   ```bash
   # Windows (PowerShell)
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Clone and setup**:
   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/{category}/{project-name}
   uv sync
   ```

3. **Run the application**:
   ```bash
   uv run streamlit run app.py
   ```

### Alternative: Using pip

If you prefer pip:
```bash
pip install -r requirements.txt
```

> **Note**: uv provides faster installations and better dependency resolution
```

## 🚀 Benefits of Migration

### For Developers
- **Faster installs**: 10-100x faster than pip
- **Better resolution**: More reliable dependency solving
- **Reproducible builds**: Lock files ensure consistency
- **Modern tooling**: Better error messages and debugging

### For Project Maintainers  
- **Easier updates**: `uv sync --upgrade` for bulk updates
- **Better CI/CD**: Faster build times
- **Conflict detection**: Earlier identification of incompatible dependencies
- **Standards compliance**: Following Python packaging best practices

### For Users
- **Quicker setup**: Reduced friction getting started
- **More reliable**: Fewer "works on my machine" issues
- **Better documentation**: Clearer installation instructions
- **Future-proof**: Aligned with Python ecosystem direction
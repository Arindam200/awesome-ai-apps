# =============================================================================
# UV Migration and Dependency Standardization Script
# =============================================================================
# This script implements Phase 2 of the repository improvement initiative
# Migrates projects from pip to uv and creates standardized pyproject.toml files

param(
    [string]$Category = "all",
    [switch]$DryRun = $false,
    [switch]$Verbose = $false,
    [switch]$InstallUv = $false
)

$RepoRoot = Get-Location
$LogFile = "uv_migration.log"

# Categories mapping
$Categories = @{
    "starter" = "starter_ai_agents"
    "simple" = "simple_ai_agents"
    "rag" = "rag_apps"
    "advance" = "advance_ai_agents"
    "mcp" = "mcp_ai_agents"
    "memory" = "memory_agents"
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$Timestamp] [$Level] $Message"
    Write-Host $LogEntry
    Add-Content -Path $LogFile -Value $LogEntry
}

# Install uv if requested
function Install-Uv {
    if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
        Write-Log "Installing uv package manager"
        if ($DryRun) {
            Write-Log "[DRY RUN] Would install uv" "INFO"
            return
        }
        
        try {
            Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
            Write-Log "uv installed successfully"
        } catch {
            Write-Log "Failed to install uv: $($_.Exception.Message)" "ERROR"
            exit 1
        }
    } else {
        Write-Log "uv is already installed"
    }
}

# Parse requirements.txt to extract dependencies
function Get-DependenciesFromRequirements {
    param([string]$RequirementsPath)
    
    if (-not (Test-Path $RequirementsPath)) {
        return @()
    }
    
    $Requirements = Get-Content $RequirementsPath | Where-Object { 
        $_ -and -not $_.StartsWith("#") -and $_.Trim() -ne ""
    }
    
    $Dependencies = @()
    foreach ($req in $Requirements) {
        $req = $req.Trim()
        
        # Add version constraints if missing
        if (-not ($req -match "[><=]")) {
            # Common dependency version mapping
            $VersionMap = @{
                "agno" = ">=1.5.1,<2.0.0"
                "openai" = ">=1.78.1,<2.0.0"
                "mcp" = ">=1.8.1,<2.0.0"
                "streamlit" = ">=1.28.0,<2.0.0"
                "fastapi" = ">=0.104.0,<1.0.0"
                "python-dotenv" = ">=1.1.0,<2.0.0"
                "requests" = ">=2.31.0,<3.0.0"
                "pandas" = ">=2.1.0,<3.0.0"
                "numpy" = ">=1.24.0,<2.0.0"
                "pydantic" = ">=2.5.0,<3.0.0"
            }
            
            $BaseName = $req -replace "[\[\]].*", ""  # Remove extras like [extra]
            if ($VersionMap.ContainsKey($BaseName)) {
                $req = "$BaseName$($VersionMap[$BaseName])"
            } else {
                $req = "$req>=0.1.0"  # Generic constraint
            }
        }
        
        $Dependencies += "`"$req`""
    }
    
    return $Dependencies
}

# Determine project type based on dependencies and path
function Get-ProjectType {
    param([string]$ProjectPath, [array]$Dependencies)
    
    $ProjectName = Split-Path $ProjectPath -Leaf
    $CategoryPath = Split-Path (Split-Path $ProjectPath -Parent) -Leaf
    
    # Determine type from category and dependencies
    if ($CategoryPath -match "rag") { return "rag" }
    if ($CategoryPath -match "mcp") { return "mcp" }
    if ($CategoryPath -match "advance") { return "advance" }
    if ($CategoryPath -match "memory") { return "memory" }
    if ($CategoryPath -match "starter") { return "starter" }
    
    # Check dependencies for type hints
    $DepsString = $Dependencies -join " "
    if ($DepsString -match "pinecone|qdrant|vector|embedding") { return "rag" }
    if ($DepsString -match "mcp|server") { return "mcp" }
    if ($DepsString -match "crewai|multi.*agent|workflow") { return "advance" }
    
    return "simple"
}

# Generate pyproject.toml content
function New-PyProjectToml {
    param(
        [string]$ProjectPath,
        [array]$Dependencies,
        [string]$ProjectType
    )
    
    $ProjectName = Split-Path $ProjectPath -Leaf
    $SafeName = $ProjectName -replace "_", "-"
    
    # Project description based on type
    $Descriptions = @{
        "starter" = "A beginner-friendly AI agent demonstrating framework capabilities"
        "simple" = "A focused AI agent implementation for specific use cases"
        "rag" = "A RAG (Retrieval-Augmented Generation) application with vector search capabilities"
        "advance" = "An advanced AI agent system with multi-agent workflows"
        "mcp" = "A Model Context Protocol (MCP) server implementation"
        "memory" = "An AI agent with persistent memory capabilities"
    }
    
    $Description = $Descriptions[$ProjectType]
    
    # Keywords based on type
    $KeywordMap = @{
        "starter" = @("ai", "agent", "starter", "tutorial", "learning")
        "simple" = @("ai", "agent", "automation", "tool")
        "rag" = @("ai", "rag", "vector", "search", "retrieval", "embedding")
        "advance" = @("ai", "agent", "multi-agent", "workflow", "advanced")
        "mcp" = @("ai", "mcp", "server", "protocol", "tools")
        "memory" = @("ai", "agent", "memory", "persistence", "conversation")
    }
    
    $Keywords = ($KeywordMap[$ProjectType] | ForEach-Object { "`"$_`"" }) -join ", "
    $DependenciesList = $Dependencies -join ",`n    "
    
    $PyProjectContent = @"
[project]
name = "$SafeName"
version = "0.1.0"
description = "$Description"
authors = [
    {name = "Arindam Majumder", email = "arindammajumder2020@gmail.com"}
]
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
keywords = [$Keywords]
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
    $DependenciesList
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
]

test = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
]

[project.urls]
Homepage = "https://github.com/Arindam200/awesome-ai-apps"
Repository = "https://github.com/Arindam200/awesome-ai-apps"
Issues = "https://github.com/Arindam200/awesome-ai-apps/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.black]
line-length = 88
target-version = ['py310']

[tool.ruff]
target-version = "py310"
line-length = 88
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501", "B008", "C901"]

[tool.mypy]
python_version = "3.10"
check_untyped_defs = true
disallow_any_generics = true
disallow_incomplete_defs = true
disallow_untyped_defs = true
warn_redundant_casts = true
warn_unused_ignores = true

[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra -q --strict-markers --strict-config"
testpaths = ["tests"]
"@

    return $PyProjectContent
}

# Update project with uv migration
function Update-ProjectWithUv {
    param([string]$ProjectPath)
    
    $ProjectName = Split-Path $ProjectPath -Leaf
    Write-Log "Migrating project: $ProjectName to uv"
    
    $RequirementsPath = Join-Path $ProjectPath "requirements.txt"
    $PyProjectPath = Join-Path $ProjectPath "pyproject.toml"
    $ReadmePath = Join-Path $ProjectPath "README.md"
    
    # Skip if pyproject.toml already exists and is modern
    if (Test-Path $PyProjectPath) {
        $PyProjectContent = Get-Content $PyProjectPath -Raw
        if ($PyProjectContent -match "hatchling" -and $PyProjectContent -match "requires-python.*3\.10") {
            Write-Log "  Project already has modern pyproject.toml, skipping"
            return
        }
    }
    
    # Get dependencies from requirements.txt
    $Dependencies = Get-DependenciesFromRequirements -RequirementsPath $RequirementsPath
    if ($Dependencies.Count -eq 0) {
        Write-Log "  No dependencies found, skipping" "WARNING"
        return
    }
    
    # Determine project type
    $ProjectType = Get-ProjectType -ProjectPath $ProjectPath -Dependencies $Dependencies
    Write-Log "  Project type: $ProjectType"
    
    if ($DryRun) {
        Write-Log "  [DRY RUN] Would create pyproject.toml with $($Dependencies.Count) dependencies"
        return
    }
    
    # Create pyproject.toml
    $PyProjectContent = New-PyProjectToml -ProjectPath $ProjectPath -Dependencies $Dependencies -ProjectType $ProjectType
    Set-Content -Path $PyProjectPath -Value $PyProjectContent -Encoding UTF8
    Write-Log "  Created pyproject.toml"
    
    # Test uv sync
    try {
        Push-Location $ProjectPath
        if (Get-Command "uv" -ErrorAction SilentlyContinue) {
            Write-Log "  Testing uv sync..."
            $SyncResult = uv sync --dry-run 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Log "  uv sync validation successful"
            } else {
                Write-Log "  uv sync validation failed: $SyncResult" "WARNING"
            }
        }
    } catch {
        Write-Log "  uv sync test failed: $($_.Exception.Message)" "WARNING"
    } finally {
        Pop-Location
    }
    
    # Update README with uv instructions if needed
    if (Test-Path $ReadmePath) {
        $ReadmeContent = Get-Content $ReadmePath -Raw
        if (-not ($ReadmeContent -match "uv sync")) {
            Write-Log "  README needs uv installation instructions update" "INFO"
        }
    }
    
    Write-Log "  Project migration completed"
}

# Process all projects in category
function Update-Category {
    param([string]$CategoryPath)
    
    Write-Log "Processing category: $CategoryPath"
    
    if (-not (Test-Path $CategoryPath)) {
        Write-Log "Category path not found: $CategoryPath" "ERROR"
        return
    }
    
    $Projects = Get-ChildItem -Path $CategoryPath -Directory
    Write-Log "Found $($Projects.Count) projects in $CategoryPath"
    
    foreach ($Project in $Projects) {
        try {
            Update-ProjectWithUv -ProjectPath $Project.FullName
        } catch {
            Write-Log "Error processing $($Project.Name): $($_.Exception.Message)" "ERROR"
        }
    }
}

# Main execution
function Main {
    Write-Log "Starting UV migration and dependency standardization"
    Write-Log "Category: $Category, DryRun: $DryRun"
    
    # Install uv if requested
    if ($InstallUv) {
        Install-Uv
    }
    
    # Determine categories to process
    $CategoriesToProcess = @()
    if ($Category -eq "all") {
        $CategoriesToProcess = $Categories.Values
    } elseif ($Categories.ContainsKey($Category)) {
        $CategoriesToProcess = @($Categories[$Category])
    } else {
        Write-Error "Invalid category: $Category"
        exit 1
    }
    
    # Process each category
    foreach ($CategoryPath in $CategoriesToProcess) {
        Update-Category -CategoryPath $CategoryPath
    }
    
    Write-Log "UV migration completed. Check $LogFile for details."
    
    # Summary instructions
    Write-Log ""
    Write-Log "Next steps:"
    Write-Log "1. Review generated pyproject.toml files"
    Write-Log "2. Test installations with: uv sync"
    Write-Log "3. Update README files with uv instructions"
    Write-Log "4. Commit changes and test CI/CD"
}

Main
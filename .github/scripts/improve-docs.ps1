# =============================================================================
# Simple Documentation Improvement Script
# =============================================================================

param(
    [string]$ProjectPath = "",
    [switch]$DryRun = $false
)

function Write-Log {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Message"
}

function Update-SingleProject {
    param([string]$Path)
    
    if (-not (Test-Path $Path)) {
        Write-Log "Path not found: $Path"
        return
    }
    
    $ProjectName = Split-Path $Path -Leaf
    Write-Log "Processing: $ProjectName"
    
    $EnvExamplePath = Join-Path $Path ".env.example"
    $PyProjectPath = Join-Path $Path "pyproject.toml"
    $RequirementsPath = Join-Path $Path "requirements.txt"
    
    # Update .env.example if it's too basic
    if (Test-Path $EnvExamplePath) {
        $EnvContent = Get-Content $EnvExamplePath -Raw
        if ($EnvContent.Length -lt 100) {
            Write-Log "  Updating .env.example (current is too basic)"
            if (-not $DryRun) {
                $NewEnvContent = @"
# =============================================================================
# $ProjectName - Environment Configuration
# =============================================================================
# Copy this file to .env and fill in your actual values
# IMPORTANT: Never commit .env files to version control

# =============================================================================
# Required Configuration
# =============================================================================

# Nebius AI API Key (Required)
# Description: Primary LLM provider for the application
# Get your key: https://studio.nebius.ai/api-keys
# Free tier: 100 requests/minute
NEBIUS_API_KEY="your_nebius_api_key_here"

# =============================================================================
# Optional Configuration
# =============================================================================

# OpenAI API Key (Optional - Alternative LLM provider)
# Get your key: https://platform.openai.com/account/api-keys
# OPENAI_API_KEY="your_openai_api_key_here"

# =============================================================================
# Development Settings
# =============================================================================

# Debug Mode (Optional)
# DEBUG="true"

# Log Level (Optional)  
# LOG_LEVEL="INFO"

# =============================================================================
# Getting Started
# =============================================================================
# 1. Copy this file: cp .env.example .env
# 2. Get a Nebius API key from https://studio.nebius.ai/api-keys
# 3. Replace "your_nebius_api_key_here" with your actual key
# 4. Save the file and run the application
#
# Support: https://github.com/Arindam200/awesome-ai-apps/issues
"@
                Set-Content -Path $EnvExamplePath -Value $NewEnvContent -Encoding UTF8
                Write-Log "  .env.example updated"
            }
        } else {
            Write-Log "  .env.example already comprehensive"
        }
    } else {
        Write-Log "  Creating .env.example"
        if (-not $DryRun) {
            # Create basic .env.example
            $BasicEnv = @"
# $ProjectName Environment Configuration
# Copy to .env and add your actual values

# Nebius AI API Key (Required)
# Get from: https://studio.nebius.ai/api-keys
NEBIUS_API_KEY="your_nebius_api_key_here"
"@
            Set-Content -Path $EnvExamplePath -Value $BasicEnv -Encoding UTF8
            Write-Log "  .env.example created"
        }
    }
    
    # Create pyproject.toml if missing but requirements.txt exists
    if (-not (Test-Path $PyProjectPath) -and (Test-Path $RequirementsPath)) {
        Write-Log "  Creating basic pyproject.toml"
        if (-not $DryRun) {
            $SafeName = $ProjectName -replace "_", "-"
            $PyProject = @"
[project]
name = "$SafeName"
version = "0.1.0"
description = "AI agent application built with modern Python tools"
authors = [
    {name = "Arindam Majumder", email = "arindammajumder2020@gmail.com"}
]
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}

dependencies = [
    "agno>=1.5.1",
    "openai>=1.78.1",
    "python-dotenv>=1.1.0",
    "requests>=2.31.0",
]

[project.urls]
Homepage = "https://github.com/Arindam200/awesome-ai-apps"
Repository = "https://github.com/Arindam200/awesome-ai-apps"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"@
            Set-Content -Path $PyProjectPath -Value $PyProject -Encoding UTF8
            Write-Log "  pyproject.toml created"
        }
    }
    
    Write-Log "  Project $ProjectName completed"
}

# Main execution
if ($ProjectPath -ne "") {
    Update-SingleProject -Path $ProjectPath
} else {
    Write-Log "Starting documentation improvements for key projects"
    
    # Key projects to update first
    $KeyProjects = @(
        "starter_ai_agents\agno_starter",
        "starter_ai_agents\crewai_starter", 
        "starter_ai_agents\langchain_langgraph_starter",
        "simple_ai_agents\newsletter_agent",
        "simple_ai_agents\reasoning_agent",
        "rag_apps\simple_rag",
        "advance_ai_agents\deep_researcher_agent"
    )
    
    foreach ($Project in $KeyProjects) {
        $FullPath = Join-Path (Get-Location) $Project
        if (Test-Path $FullPath) {
            Update-SingleProject -Path $FullPath
        } else {
            Write-Log "Skipping $Project (not found)"
        }
    }
    
    Write-Log "Key project improvements completed"
}

Write-Log "Script completed successfully"
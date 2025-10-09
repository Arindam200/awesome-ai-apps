# =============================================================================
# Repository-Wide Documentation Standardization Script
# =============================================================================
# This script implements Phase 1 of the repository improvement initiative
# Run this from the repository root directory

param(
    [string]$Category = "all",  # Which category to process: starter, simple, rag, advance, mcp, memory, all
    [switch]$DryRun = $false,  # Preview changes without applying them
    [switch]$Verbose = $false  # Show detailed output
)

# Configuration
$RepoRoot = Get-Location
$StandardsDir = ".github\standards"
$LogFile = "documentation_upgrade.log"

# Categories and their directories
$Categories = @{
    "starter" = "starter_ai_agents"
    "simple" = "simple_ai_agents"
    "rag" = "rag_apps"
    "advance" = "advance_ai_agents"
    "mcp" = "mcp_ai_agents"
    "memory" = "memory_agents"
}

# Initialize logging
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$Timestamp] [$Level] $Message"
    Write-Host $LogEntry
    Add-Content -Path $LogFile -Value $LogEntry
}

# Check if we're in the right directory
function Test-RepositoryRoot {
    $RequiredFiles = @("README.md", "CONTRIBUTING.md", "LICENSE")
    foreach ($file in $RequiredFiles) {
        if (-not (Test-Path $file)) {
            Write-Error "Required file $file not found. Please run this script from the repository root."
            exit 1
        }
    }
}

# Get all project directories for a category
function Get-ProjectDirectories {
    param([string]$CategoryPath)
    
    if (-not (Test-Path $CategoryPath)) {
        Write-Log "Category path $CategoryPath not found" "WARNING"
        return @()
    }
    
    Get-ChildItem -Path $CategoryPath -Directory | ForEach-Object { $_.FullName }
}

# Analyze current README quality
function Test-ReadmeQuality {
    param([string]$ReadmePath)
    
    if (-not (Test-Path $ReadmePath)) {
        return @{
            Score = 0
            Issues = @("README.md not found")
            HasBanner = $false
            HasFeatures = $false
            HasTechStack = $false
            HasInstallation = $false
            HasUsage = $false
            HasContributing = $false
        }
    }
    
    $Content = Get-Content $ReadmePath -Raw
    $Issues = @()
    $Score = 0
    
    # Check for required sections
    $HasBanner = $Content -match "!\[.*\]\(.*\.(png|jpg|gif)\)"
    $HasFeatures = $Content -match "## .*Features" -or $Content -match "🚀.*Features"
    $HasTechStack = $Content -match "## .*Tech Stack" -or $Content -match "🛠️.*Tech Stack"
    $HasInstallation = $Content -match "## .*Installation" -or $Content -match "⚙️.*Installation"
    $HasUsage = $Content -match "## .*Usage" -or $Content -match "🚀.*Usage"
    $HasContributing = $Content -match "## .*Contributing" -or $Content -match "🤝.*Contributing"
    $HasTroubleshooting = $Content -match "## .*Troubleshooting" -or $Content -match "🐛.*Troubleshooting"
    $HasProjectStructure = $Content -match "## .*Project Structure" -or $Content -match "📂.*Project Structure"
    
    # Score calculation (out of 100)
    if ($HasBanner) { $Score += 10 } else { $Issues += "Missing banner/demo image" }
    if ($HasFeatures) { $Score += 15 } else { $Issues += "Missing features section" }
    if ($HasTechStack) { $Score += 15 } else { $Issues += "Missing tech stack section" }
    if ($HasInstallation) { $Score += 20 } else { $Issues += "Missing installation section" }
    if ($HasUsage) { $Score += 15 } else { $Issues += "Missing usage section" }
    if ($HasContributing) { $Score += 10 } else { $Issues += "Missing contributing section" }
    if ($HasTroubleshooting) { $Score += 10 } else { $Issues += "Missing troubleshooting section" }
    if ($HasProjectStructure) { $Score += 5 } else { $Issues += "Missing project structure" }
    
    # Check for uv installation instructions
    $HasUvInstructions = $Content -match "uv sync" -or $Content -match "uv run"
    if (-not $HasUvInstructions) { $Issues += "Missing uv installation instructions" }
    
    return @{
        Score = $Score
        Issues = $Issues
        HasBanner = $HasBanner
        HasFeatures = $HasFeatures
        HasTechStack = $HasTechStack
        HasInstallation = $HasInstallation
        HasUsage = $HasUsage
        HasContributing = $HasContributing
        HasTroubleshooting = $HasTroubleshooting
        HasProjectStructure = $HasProjectStructure
        HasUvInstructions = $HasUvInstructions
    }
}

# Analyze .env.example quality
function Test-EnvExampleQuality {
    param([string]$EnvPath)
    
    if (-not (Test-Path $EnvPath)) {
        return @{
            Score = 0
            Issues = @(".env.example not found")
            HasComments = $false
            HasApiKeyLinks = $false
            HasSections = $false
        }
    }
    
    $Content = Get-Content $EnvPath -Raw
    $Issues = @()
    $Score = 0
    
    # Check for quality indicators
    $HasComments = $Content -match "#.*Description:" -or $Content -match "#.*Get.*from:"
    $HasApiKeyLinks = $Content -match "https?://.*api" -or $Content -match "studio\.nebius\.ai"
    $HasSections = $Content -match "# ===.*===" -or $Content -match "# Required" -or $Content -match "# Optional"
    $HasSecurity = $Content -match "security" -or $Content -match "never commit" -or $Content -match "gitignore"
    
    # Score calculation
    if ($HasComments) { $Score += 30 } else { $Issues += "Missing detailed comments" }
    if ($HasApiKeyLinks) { $Score += 30 } else { $Issues += "Missing API key acquisition links" }
    if ($HasSections) { $Score += 25 } else { $Issues += "Missing organized sections" }
    if ($HasSecurity) { $Score += 15 } else { $Issues += "Missing security notes" }
    
    return @{
        Score = $Score
        Issues = $Issues
        HasComments = $HasComments
        HasApiKeyLinks = $HasApiKeyLinks
        HasSections = $HasSections
        HasSecurity = $HasSecurity
    }
}

# Generate enhanced .env.example based on project type
function New-EnhancedEnvExample {
    param([string]$ProjectPath, [string]$ProjectType = "starter")
    
    $ProjectName = Split-Path $ProjectPath -Leaf
    
    $BaseTemplate = @"
# =============================================================================
# $ProjectName - Environment Configuration
# =============================================================================
# Copy this file to .env and fill in your actual values
# IMPORTANT: Never commit .env files to version control
#
# Quick setup: cp .env.example .env

# =============================================================================
# Required Configuration
# =============================================================================

# Nebius AI API Key (Required)
# Description: Primary LLM provider for the application
# Get your key: https://studio.nebius.ai/api-keys
# Free tier: 100 requests/minute
# Documentation: https://docs.nebius.ai/
NEBIUS_API_KEY="your_nebius_api_key_here"

# =============================================================================
# Optional Configuration (Uncomment to enable)
# =============================================================================

# OpenAI API Key (Optional - Alternative LLM provider)
# Description: Use OpenAI models instead of or alongside Nebius
# Get your key: https://platform.openai.com/account/api-keys
# Note: Costs apply based on usage
# OPENAI_API_KEY="your_openai_api_key_here"

"@

    # Add project-type specific sections
    switch ($ProjectType) {
        "rag" {
            $BaseTemplate += @"

# =============================================================================
# Vector Database Configuration
# =============================================================================

# Pinecone (Recommended for beginners)
# Get from: https://pinecone.io/
# PINECONE_API_KEY="your_pinecone_api_key"
# PINECONE_ENVIRONMENT="your_environment"
# PINECONE_INDEX="your_index_name"

# Qdrant (Alternative)
# Get from: https://qdrant.tech/
# QDRANT_URL="your_qdrant_url"
# QDRANT_API_KEY="your_qdrant_api_key"

"@
        }
        "mcp" {
            $BaseTemplate += @"

# =============================================================================
# MCP Server Configuration
# =============================================================================

# MCP Server Settings
MCP_SERVER_NAME="$ProjectName"
MCP_SERVER_VERSION="1.0.0"
MCP_SERVER_HOST="localhost"
MCP_SERVER_PORT="3000"

"@
        }
        "advance" {
            $BaseTemplate += @"

# =============================================================================
# Advanced Agent Configuration
# =============================================================================

# Multi-Agent Settings
MAX_CONCURRENT_AGENTS="5"
AGENT_TIMEOUT="300"
ENABLE_AGENT_LOGGING="true"

# External Services
TAVILY_API_KEY="your_tavily_api_key"
EXA_API_KEY="your_exa_api_key"

"@
        }
    }
    
    # Add common footer
    $BaseTemplate += @"

# =============================================================================
# Development Settings
# =============================================================================

# Debug Mode (Optional)
# DEBUG="true"

# Log Level (Optional)
# LOG_LEVEL="INFO"

# =============================================================================
# Notes and Troubleshooting
# =============================================================================
#
# Getting Started:
# 1. Copy this file: cp .env.example .env
# 2. Get API keys from the links provided above
# 3. Replace placeholder values with your actual keys
# 4. Save the file and run the application
#
# Common Issues:
# - API key error: Check your key and internet connection
# - Module errors: Run 'uv sync' to install dependencies
# - Permission errors: Ensure .env file is in project root
#
# Security:
# - Never share your .env file or commit it to version control
# - Use different API keys for development and production
# - Monitor your API usage to avoid unexpected charges
#
# Support:
# - Issues: https://github.com/Arindam200/awesome-ai-apps/issues
# - Documentation: Check project README.md for specific guidance
"@

    return $BaseTemplate
}

# Process a single project
function Update-Project {
    param([string]$ProjectPath, [string]$CategoryType)
    
    $ProjectName = Split-Path $ProjectPath -Leaf
    Write-Log "Processing project: $ProjectName in category: $CategoryType"
    
    $ReadmePath = Join-Path $ProjectPath "README.md"
    $EnvPath = Join-Path $ProjectPath ".env.example"
    $RequirementsPath = Join-Path $ProjectPath "requirements.txt"
    $PyProjectPath = Join-Path $ProjectPath "pyproject.toml"
    
    # Analyze current state
    $ReadmeQuality = Test-ReadmeQuality -ReadmePath $ReadmePath
    $EnvQuality = Test-EnvExampleQuality -EnvPath $EnvPath
    
    Write-Log "  README quality score: $($ReadmeQuality.Score)/100"
    Write-Log "  .env.example quality score: $($EnvQuality.Score)/100"
    
    if ($Verbose) {
        Write-Log "  README issues: $($ReadmeQuality.Issues -join ', ')"
        Write-Log "  .env.example issues: $($EnvQuality.Issues -join ', ')"
    }
    
    # Skip if already high quality
    if ($ReadmeQuality.Score -gt 85 -and $EnvQuality.Score -gt 85) {
        Write-Log "  Project already meets quality standards, skipping" "INFO"
        return
    }
    
    if ($DryRun) {
        Write-Log "  [DRY RUN] Would update README and .env.example" "INFO"
        return
    }
    
    # Update .env.example if needed
    if ($EnvQuality.Score -lt 70) {
        Write-Log "  Updating .env.example"
        $NewEnvContent = New-EnhancedEnvExample -ProjectPath $ProjectPath -ProjectType $CategoryType
        Set-Content -Path $EnvPath -Value $NewEnvContent -Encoding UTF8
    }
    
    # Create pyproject.toml if missing and requirements.txt exists
    if (-not (Test-Path $PyProjectPath) -and (Test-Path $RequirementsPath)) {
        Write-Log "  Creating pyproject.toml"
        # This would be implemented with a more complex conversion
        # For now, just note that it needs manual attention
        Write-Log "  NOTE: pyproject.toml creation needs manual review" "WARNING"
    }
    
    Write-Log "  Project update completed"
}

# Main execution
function Main {
    Write-Log "Starting repository-wide documentation standardization"
    Write-Log "Category: $Category, DryRun: $DryRun, Verbose: $Verbose"
    
    Test-RepositoryRoot
    
    # Determine which categories to process
    $CategoriesToProcess = @()
    if ($Category -eq "all") {
        $CategoriesToProcess = $Categories.Values
    } elseif ($Categories.ContainsKey($Category)) {
        $CategoriesToProcess = @($Categories[$Category])
    } else {
        Write-Error "Invalid category: $Category. Valid options: $($Categories.Keys -join ', '), all"
        exit 1
    }
    
    # Process each category
    $TotalProjects = 0
    $ProcessedProjects = 0
    
    foreach ($CategoryPath in $CategoriesToProcess) {
        Write-Log "Processing category: $CategoryPath"
        
        $Projects = Get-ProjectDirectories -CategoryPath $CategoryPath
        $TotalProjects += $Projects.Count
        
        foreach ($ProjectPath in $Projects) {
            try {
                Update-Project -ProjectPath $ProjectPath -CategoryType ($CategoryPath -replace "_.*", "")
                $ProcessedProjects++
            } catch {
                Write-Log "Error processing project $ProjectPath`: $($_.Exception.Message)" "ERROR"
            }
        }
    }
    
    Write-Log "Documentation standardization completed"
    Write-Log "Processed $ProcessedProjects out of $TotalProjects projects"
    Write-Log "Log file: $LogFile"
}

# Run the script
Main
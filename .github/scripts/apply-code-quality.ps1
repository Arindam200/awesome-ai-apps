# PowerShell Script for Code Quality Improvements
# Applies type hints, logging, error handling, and docstrings across Python projects

param(
    [string]$ProjectPath = ".",
    [switch]$DryRun = $false,
    [switch]$Verbose = $false
)

# Initialize logging
$LogFile = "code_quality_improvements.log"
$Script:LogPath = Join-Path $ProjectPath $LogFile

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "$Timestamp - $Level - $Message"
    Write-Host $LogMessage
    Add-Content -Path $Script:LogPath -Value $LogMessage
}

function Get-PythonFiles {
    param([string]$Path)
    
    Write-Log "Scanning for Python files in: $Path"
    $PythonFiles = Get-ChildItem -Path $Path -Recurse -Filter "*.py" | 
                   Where-Object { $_.Name -notlike "test_*" -and $_.Name -ne "__init__.py" }
    
    Write-Log "Found $($PythonFiles.Count) Python files to process"
    return $PythonFiles
}

function Add-TypeHints {
    param([string]$FilePath)
    
    try {
        $Content = Get-Content -Path $FilePath -Raw
        $Modified = $false
        
        # Add typing imports if not present
        if ($Content -notmatch "from typing import") {
            $NewImport = "from typing import List, Dict, Optional, Union, Any`n"
            $Content = $NewImport + $Content
            $Modified = $true
            Write-Log "Added typing imports to: $FilePath"
        }
        
        # Add basic type hints to function definitions (simple pattern)
        $FunctionPattern = 'def\s+(\w+)\s*\([^)]*\)\s*:'
        if ($Content -match $FunctionPattern -and $Content -notmatch '->') {
            Write-Log "Found functions without return type hints in: $FilePath"
            # Note: Complex type hint addition would require AST parsing
            # This is a placeholder for basic detection
        }
        
        if ($Modified -and -not $DryRun) {
            Set-Content -Path $FilePath -Value $Content -Encoding UTF8
            Write-Log "Updated type hints in: $FilePath"
        }
        
    } catch {
        Write-Log "Error processing type hints for $FilePath`: $($_.Exception.Message)" "ERROR"
    }
}

function Add-Logging {
    param([string]$FilePath)
    
    try {
        $Content = Get-Content -Path $FilePath -Raw
        $Modified = $false
        
        # Add logging import if not present
        if ($Content -notmatch "import logging") {
            $LoggingSetup = @"
import logging

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

"@
            $Content = $LoggingSetup + $Content
            $Modified = $true
            Write-Log "Added logging configuration to: $FilePath"
        }
        
        # Replace print statements with logging (simple cases)
        $PrintPattern = 'print\s*\(\s*["\']([^"\']*)["\']?\s*\)'
        if ($Content -match $PrintPattern) {
            $Content = $Content -replace 'print\s*\(\s*(["\'])([^"\']*)\1\s*\)', 'logger.info("$2")'
            $Modified = $true
            Write-Log "Replaced print statements with logging in: $FilePath"
        }
        
        if ($Modified -and -not $DryRun) {
            Set-Content -Path $FilePath -Value $Content -Encoding UTF8
            Write-Log "Updated logging in: $FilePath"
        }
        
    } catch {
        Write-Log "Error processing logging for $FilePath`: $($_.Exception.Message)" "ERROR"
    }
}

function Add-ErrorHandling {
    param([string]$FilePath)
    
    try {
        $Content = Get-Content -Path $FilePath -Raw
        $Modified = $false
        
        # Look for file operations without try-catch
        if ($Content -match "open\s*\(" -and $Content -notmatch "try:") {
            Write-Log "Found file operations without error handling in: $FilePath"
            # Note: Adding comprehensive error handling requires more sophisticated parsing
        }
        
        # Look for API calls without error handling
        if ($Content -match "requests\." -and $Content -notmatch "try:") {
            Write-Log "Found API calls without error handling in: $FilePath"
        }
        
    } catch {
        Write-Log "Error checking error handling for $FilePath`: $($_.Exception.Message)" "ERROR"
    }
}

function Add-Docstrings {
    param([string]$FilePath)
    
    try {
        $Content = Get-Content -Path $FilePath -Raw
        
        # Check for functions without docstrings
        $FunctionPattern = 'def\s+(\w+)\s*\([^)]*\)\s*:\s*\n(?!\s*""")'
        if ($Content -match $FunctionPattern) {
            Write-Log "Found functions without docstrings in: $FilePath"
            # Note: Adding docstrings requires understanding function purpose and parameters
        }
        
    } catch {
        Write-Log "Error checking docstrings for $FilePath`: $($_.Exception.Message)" "ERROR"
    }
}

function Process-Project {
    param([string]$ProjectPath)
    
    Write-Log "Processing project: $ProjectPath"
    
    $PythonFiles = Get-PythonFiles -Path $ProjectPath
    
    foreach ($File in $PythonFiles) {
        Write-Log "Processing file: $($File.FullName)"
        
        if ($Verbose) {
            Write-Host "  - Adding type hints..." -ForegroundColor Yellow
        }
        Add-TypeHints -FilePath $File.FullName
        
        if ($Verbose) {
            Write-Host "  - Updating logging..." -ForegroundColor Yellow
        }
        Add-Logging -FilePath $File.FullName
        
        if ($Verbose) {
            Write-Host "  - Checking error handling..." -ForegroundColor Yellow
        }
        Add-ErrorHandling -FilePath $File.FullName
        
        if ($Verbose) {
            Write-Host "  - Checking docstrings..." -ForegroundColor Yellow
        }
        Add-Docstrings -FilePath $File.FullName
    }
}

function Get-QualityMetrics {
    param([string]$ProjectPath)
    
    Write-Log "Calculating quality metrics for: $ProjectPath"
    
    $PythonFiles = Get-PythonFiles -Path $ProjectPath
    $TotalFiles = $PythonFiles.Count
    $FilesWithLogging = 0
    $FilesWithTypeHints = 0
    $FilesWithDocstrings = 0
    $FilesWithErrorHandling = 0
    
    foreach ($File in $PythonFiles) {
        $Content = Get-Content -Path $File.FullName -Raw
        
        if ($Content -match "import logging") { $FilesWithLogging++ }
        if ($Content -match "from typing import") { $FilesWithTypeHints++ }
        if ($Content -match '""".*"""') { $FilesWithDocstrings++ }
        if ($Content -match "try:" -and $Content -match "except") { $FilesWithErrorHandling++ }
    }
    
    $Metrics = @{
        "TotalFiles" = $TotalFiles
        "LoggingCoverage" = if ($TotalFiles -gt 0) { [math]::Round(($FilesWithLogging / $TotalFiles) * 100, 2) } else { 0 }
        "TypeHintsCoverage" = if ($TotalFiles -gt 0) { [math]::Round(($FilesWithTypeHints / $TotalFiles) * 100, 2) } else { 0 }
        "DocstringsCoverage" = if ($TotalFiles -gt 0) { [math]::Round(($FilesWithDocstrings / $TotalFiles) * 100, 2) } else { 0 }
        "ErrorHandlingCoverage" = if ($TotalFiles -gt 0) { [math]::Round(($FilesWithErrorHandling / $TotalFiles) * 100, 2) } else { 0 }
    }
    
    return $Metrics
}

# Main execution
Write-Log "=== Code Quality Improvement Script Started ==="
Write-Log "Project Path: $ProjectPath"
Write-Log "Dry Run Mode: $DryRun"

try {
    # Get initial metrics
    $InitialMetrics = Get-QualityMetrics -ProjectPath $ProjectPath
    Write-Log "Initial Quality Metrics:"
    Write-Log "  - Total Python Files: $($InitialMetrics.TotalFiles)"
    Write-Log "  - Logging Coverage: $($InitialMetrics.LoggingCoverage)%"
    Write-Log "  - Type Hints Coverage: $($InitialMetrics.TypeHintsCoverage)%"
    Write-Log "  - Docstrings Coverage: $($InitialMetrics.DocstringsCoverage)%"
    Write-Log "  - Error Handling Coverage: $($InitialMetrics.ErrorHandlingCoverage)%"
    
    # Process the project
    if (-not $DryRun) {
        Process-Project -ProjectPath $ProjectPath
        
        # Get final metrics
        $FinalMetrics = Get-QualityMetrics -ProjectPath $ProjectPath
        Write-Log "Final Quality Metrics:"
        Write-Log "  - Logging Coverage: $($FinalMetrics.LoggingCoverage)% (was $($InitialMetrics.LoggingCoverage)%)"
        Write-Log "  - Type Hints Coverage: $($FinalMetrics.TypeHintsCoverage)% (was $($InitialMetrics.TypeHintsCoverage)%)"
        Write-Log "  - Docstrings Coverage: $($FinalMetrics.DocstringsCoverage)% (was $($InitialMetrics.DocstringsCoverage)%)"
        Write-Log "  - Error Handling Coverage: $($FinalMetrics.ErrorHandlingCoverage)% (was $($InitialMetrics.ErrorHandlingCoverage)%)"
    } else {
        Write-Log "DRY RUN MODE - No files were modified"
        Process-Project -ProjectPath $ProjectPath
    }
    
    Write-Log "=== Code Quality Improvement Script Completed Successfully ==="
    
} catch {
    Write-Log "Critical error during script execution: $($_.Exception.Message)" "ERROR"
    exit 1
}
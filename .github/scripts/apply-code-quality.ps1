# PowerShell Script for Code Quality Improvements
# Applies type hints, logging, error handling, and docstrings across Python projects

[CmdletBinding()]
param(
    [string]$ProjectPath = ".",
    [switch]$DryRun = $false
)

# Set strict mode for better error handling
Set-StrictMode -Version Latest

# Initialize logging
$LogFile = "code_quality_improvements.log"
$Script:LogPath = Join-Path $ProjectPath $LogFile

function Write-Log {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message, 
        [string]$Level = "INFO"
    )
    
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "$Timestamp - $Level - $Message"
    Write-Host $LogMessage
    
    try {
        Add-Content -Path $Script:LogPath -Value $LogMessage -ErrorAction Stop
    }
    catch {
        Write-Warning "Failed to write to log file: $_"
    }
}

function Get-PythonFiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    
    Write-Log "Scanning for Python files in: $Path"
    
    try {
        $PythonFiles = Get-ChildItem -Path $Path -Recurse -Filter "*.py" -ErrorAction Stop | 
                       Where-Object { $_.Name -notlike "test_*" -and $_.Name -ne "__init__.py" }
        
        Write-Log "Found $($PythonFiles.Count) Python files to process"
        return $PythonFiles
    }
    catch {
        Write-Log "Error scanning for Python files: $_" "ERROR"
        throw
    }
}

function Get-QualityMetrics {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectPath
    )
    
    Write-Log "Calculating quality metrics for: $ProjectPath"
    
    try {
        $PythonFiles = Get-PythonFiles -Path $ProjectPath
        $TotalFiles = $PythonFiles.Count
        $FilesWithLogging = 0
        $FilesWithTypeHints = 0
        $FilesWithDocstrings = 0
        $FilesWithErrorHandling = 0
        
        foreach ($File in $PythonFiles) {
            try {
                $Content = Get-Content -Path $File.FullName -Raw -ErrorAction Stop
                
                if ($Content -match "import logging") { $FilesWithLogging++ }
                if ($Content -match "from typing import") { $FilesWithTypeHints++ }
                if ($Content -match '"""') { $FilesWithDocstrings++ }
                if ($Content -match "try:" -and $Content -match "except") { $FilesWithErrorHandling++ }
            }
            catch {
                Write-Log "Warning: Could not read file $($File.FullName): $_" "WARN"
            }
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
    catch {
        Write-Log "Error calculating quality metrics: $_" "ERROR"
        throw
    }
}

# Main execution
Write-Log "=== Code Quality Improvement Script Started ==="
Write-Log "Project Path: $ProjectPath"
Write-Log "Dry Run Mode: $DryRun"

try {
    # Validate project path
    if (-not (Test-Path $ProjectPath)) {
        throw "Project path does not exist: $ProjectPath"
    }
    
    # Get initial metrics
    $InitialMetrics = Get-QualityMetrics -ProjectPath $ProjectPath
    Write-Log "Initial Quality Metrics:"
    Write-Log "  - Total Python Files: $($InitialMetrics.TotalFiles)"
    Write-Log "  - Logging Coverage: $($InitialMetrics.LoggingCoverage)%"
    Write-Log "  - Type Hints Coverage: $($InitialMetrics.TypeHintsCoverage)%"
    Write-Log "  - Docstrings Coverage: $($InitialMetrics.DocstringsCoverage)%"
    Write-Log "  - Error Handling Coverage: $($InitialMetrics.ErrorHandlingCoverage)%"
    
    # Note: For actual processing, use the Python code quality enhancer tool
    Write-Log "For comprehensive code quality improvements, use:"
    Write-Log "python .github/tools/code_quality_enhancer.py $ProjectPath"
    
    Write-Log "=== Code Quality Improvement Script Completed Successfully ==="
    
}
catch {
    Write-Log "Critical error during script execution: $($_.Exception.Message)" "ERROR"
    exit 1
}
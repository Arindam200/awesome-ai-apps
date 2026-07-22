param(
  [string]$ExePath,
  [int]$ObservationSeconds = 12
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ExePath)) {
  $root = Split-Path -Parent $PSScriptRoot
  $packageJson = Get-Content -LiteralPath (Join-Path $root "package.json") -Raw | ConvertFrom-Json
  $ExePath = Join-Path $root ("release\{0}\win-unpacked\AI小说作家.exe" -f [string]$packageJson.version)
}

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace AiNovelSmoke {
  public static class TopLevelWindowProbe {
    public delegate bool EnumWindowsProc(IntPtr handle, IntPtr state);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr state);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr handle, out uint processId);
  }
}
'@

function Test-ProcessHasTopLevelWindow {
  param([Parameter(Mandatory = $true)][int]$ProcessId)

  $found = $false
  [AiNovelSmoke.TopLevelWindowProbe]::EnumWindows({
    param($handle, $state)
    $windowProcessId = 0
    [void][AiNovelSmoke.TopLevelWindowProbe]::GetWindowThreadProcessId($handle, [ref]$windowProcessId)
    if ($windowProcessId -eq $ProcessId) {
      $script:foundSmokeWindow = $true
      return $false
    }
    return $true
  }, [IntPtr]::Zero) | Out-Null

  $found = $script:foundSmokeWindow -eq $true
  $script:foundSmokeWindow = $false
  return $found
}

$resolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
if ([System.IO.Path]::GetExtension($resolvedExe) -ne ".exe") {
  throw "Smoke target must be an .exe file: $resolvedExe"
}

$smokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ai-novel-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $smokeRoot | Out-Null
$process = $null

try {
  $process = Start-Process `
    -FilePath $resolvedExe `
    -ArgumentList @("--user-data-dir=$smokeRoot") `
    -WindowStyle Hidden `
    -PassThru

  $deadline = [DateTime]::UtcNow.AddSeconds($ObservationSeconds)
  $windowCreated = $false
  while ([DateTime]::UtcNow -lt $deadline) {
    Start-Sleep -Milliseconds 250
    $process.Refresh()
    if ($process.HasExited) {
      throw "Application exited during smoke test with code $($process.ExitCode)"
    }
    if (Test-ProcessHasTopLevelWindow -ProcessId $process.Id) {
      $windowCreated = $true
      break
    }
  }

  if (-not $windowCreated) {
    throw "Application stayed alive but did not create a main window within $ObservationSeconds seconds"
  }

  Write-Host "Windows application smoke test passed: PID $($process.Id), top-level window created"
}
finally {
  if ($process -and -not $process.HasExited) {
    & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0 -and -not $process.HasExited) {
      Stop-Process -Id $process.Id -Force
    }
  }
  if (Test-Path -LiteralPath $smokeRoot) {
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
      try {
        Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction Stop
        break
      }
      catch {
        if ($attempt -eq 19) {
          Write-Warning "Could not remove smoke-test user data: $smokeRoot"
        }
        else {
          Start-Sleep -Milliseconds 250
        }
      }
    }
  }
}

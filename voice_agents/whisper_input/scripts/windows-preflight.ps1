param(
  [ValidateSet("all", "msvc", "gnu", "ime")]
  [string]$Toolchain = "msvc",
  [switch]$IncludeLocalAsrExperiment
)

$ErrorActionPreference = "Stop"

$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:USERPROFILE\scoop\persist\rustup\.cargo\bin;$env:USERPROFILE\scoop\apps\rustup\current\.cargo\bin;$env:USERPROFILE\scoop\apps\mingw\current\bin;$env:PATH"

function Test-Command($Name) {
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if ($cmd) {
    Write-Host "[ok] $Name -> $($cmd.Source)"
    return $true
  }
  Write-Host "[missing] $Name"
  return $false
}

function Find-MSBuild {
  $cmd = Get-Command MSBuild.exe -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }

  $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
  if (Test-Path $vswhere) {
    $found = & $vswhere -latest -products * -requires Microsoft.Component.MSBuild -find "MSBuild\Current\Bin\MSBuild.exe" 2>$null |
      Select-Object -First 1
    if ($found -and (Test-Path $found)) {
      return $found
    }
  }

  $candidates = @(
    "${env:ProgramFiles}\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles}\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
  )
  foreach ($candidate in $candidates) {
    if (Test-Path $candidate) {
      return $candidate
    }
  }

  return $null
}

function Find-LinkExe {
  $cmd = Get-Command link.exe -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }

  $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
  if (Test-Path $vswhere) {
    $found = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find "VC\Tools\MSVC\**\bin\Hostx64\x64\link.exe" 2>$null |
      Select-Object -First 1
    if ($found -and (Test-Path $found)) {
      return $found
    }
  }

  $candidateRoot = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC"
  if (Test-Path $candidateRoot) {
    $found = Get-ChildItem -LiteralPath $candidateRoot -Directory |
      Sort-Object Name -Descending |
      ForEach-Object {
        $candidate = Join-Path $_.FullName "bin\Hostx64\x64\link.exe"
        if (Test-Path $candidate) {
          return $candidate
        }
      } |
      Select-Object -First 1
    if ($found) {
      return $found
    }
  }

  return $null
}

function Find-Kernel32Lib {
  $kitsRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\Lib"
  if (-not (Test-Path $kitsRoot)) {
    return $null
  }
  Get-ChildItem -LiteralPath $kitsRoot -Directory |
    Sort-Object Name -Descending |
    ForEach-Object {
      $candidate = Join-Path $_.FullName "um\x64\kernel32.lib"
      if (Test-Path $candidate) {
        return $candidate
      }
    }
}

function Test-IsAdministrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [Security.Principal.WindowsPrincipal]::new($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-WebView2Runtime {
  $paths = @(
    "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
  )
  foreach ($path in $paths) {
    if (Test-Path $path) {
      Write-Host "[ok] WebView2 Runtime registry key found"
      return $true
    }
  }

  $runtimeRoots = @(
    "${env:ProgramFiles(x86)}\Microsoft\EdgeWebView\Application",
    "${env:ProgramFiles}\Microsoft\EdgeWebView\Application"
  )
  foreach ($root in $runtimeRoots) {
    if (-not (Test-Path $root)) {
      continue
    }
    $runtime = Get-ChildItem -LiteralPath $root -Recurse -Filter "msedgewebview2.exe" -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if ($runtime) {
      Write-Host "[ok] WebView2 Runtime executable -> $($runtime.FullName)"
      return $true
    }
  }

  Write-Host "[warn] WebView2 Runtime registry key not found; install Evergreen runtime if the app window is blank."
  return $false
}

function Test-RequiredFile($Path, $MissingMessage) {
  if (Test-Path $Path) {
    Write-Host "[ok] $(Split-Path -Leaf $Path) -> $Path"
    return $true
  }
  Write-Host "[missing] $Path"
  Write-Host "[error] $MissingMessage"
  return $false
}

$appRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$binariesRoot = Join-Path $appRoot "src-tauri\binaries"
$windowsMsvcTarget = "x86_64-pc-windows-msvc"
$failed = $false

Write-Host "Cloud-first standard preflight:"
Write-Host "  ASR: Qwen realtime by default; Doubao is backup."
Write-Host "  LLM: Qwen Flash by default; Doubao and Gemini are alternatives."
Write-Host "  Local ASR assets: optional hidden experiment only."

Write-Host "== Common prerequisites =="
foreach ($name in @("node", "npm")) {
  if (-not (Test-Command $name)) {
    $failed = $true
  }
}
Test-WebView2Runtime | Out-Null

if ($Toolchain -eq "all" -or $Toolchain -eq "msvc") {
  if ($IncludeLocalAsrExperiment) {
    Write-Host ""
    Write-Host "Checking deprecated non-product local ASR experiment assets."
    if (-not (Test-RequiredFile `
        (Join-Path $binariesRoot "qingyu-asr-sidecar-$windowsMsvcTarget.exe") `
        "Missing qingyu-asr-sidecar-$windowsMsvcTarget.exe. Run scripts\build-qingyu-asr-sidecar.ps1 before packaging with -IncludeLocalAsrExperiment.")) {
      $failed = $true
    }
    if (-not (Test-RequiredFile `
        (Join-Path $binariesRoot "sherpa-onnx-offline.exe") `
        "Missing sherpa-onnx-offline.exe. Run scripts\check-sherpa-assets.ps1 to download and verify the pinned sherpa runtime before packaging with -IncludeLocalAsrExperiment.")) {
      $failed = $true
    }
  } else {
    Write-Host ""
    Write-Host "== Whisper Input cloud ASR assets =="
    Write-Host "[ok] Standard cloud-first package does not require local ASR binaries."
  }

  Write-Host ""
  Write-Host "== MSVC route =="
  foreach ($name in @("rustc", "cargo", "rustup")) {
    if (-not (Test-Command $name)) {
      $failed = $true
    }
  }
  if (Get-Command rustup -ErrorAction SilentlyContinue) {
    $toolchains = & rustup toolchain list 2>$null
    if ($toolchains -match "x86_64-pc-windows-msvc") {
      Write-Host "[ok] Rust MSVC toolchain installed"
    } else {
      Write-Host "[missing] stable-x86_64-pc-windows-msvc"
      Write-Host "[hint] rustup toolchain install stable-x86_64-pc-windows-msvc"
      $failed = $true
    }
  } else {
    Write-Host "[missing] rustup"
    $failed = $true
  }
  $linkExe = Find-LinkExe
  if ($linkExe) {
    Write-Host "[ok] link.exe -> $linkExe"
  } else {
    Write-Host "[missing] link.exe"
    Write-Host "[hint] Run from a Developer PowerShell, call vcvars64.bat first, or install Visual Studio Build Tools workload 'Desktop development with C++'."
    $failed = $true
  }
  $kernel32 = Find-Kernel32Lib
  if ($kernel32) {
    Write-Host "[ok] kernel32.lib -> $kernel32"
  } else {
    Write-Host "[missing] kernel32.lib"
    Write-Host "[hint] Install Visual Studio Build Tools workload 'Desktop development with C++' and a Windows 10/11 SDK."
    $failed = $true
  }
}

if ($Toolchain -eq "all" -or $Toolchain -eq "gnu") {
  Write-Host ""
  Write-Host "== GNU/MinGW route =="
  foreach ($name in @("gcc", "dlltool")) {
    if (-not (Test-Command $name)) {
      $failed = $true
    }
  }
  if (Get-Command rustup -ErrorAction SilentlyContinue) {
    $toolchains = & rustup toolchain list 2>$null
    if ($toolchains -match "x86_64-pc-windows-gnu") {
      Write-Host "[ok] Rust GNU toolchain installed"
    } else {
      Write-Host "[missing] stable-x86_64-pc-windows-gnu"
      Write-Host "[hint] rustup toolchain install stable-x86_64-pc-windows-gnu"
      $failed = $true
    }
  } else {
    Write-Host "[missing] rustup"
    $failed = $true
  }
  if ((Get-Location).Path -match "\s") {
    Write-Host "[warn] Current path contains spaces. Use scripts/windows-build-gnu.ps1 or build from a no-space path."
  }
}

if ($Toolchain -eq "all" -or $Toolchain -eq "ime") {
  Write-Host ""
  Write-Host "== Windows IME route =="
  $msbuild = Find-MSBuild
  if ($msbuild) {
    Write-Host "[ok] MSBuild.exe -> $msbuild"
  } else {
    Write-Host "[missing] MSBuild.exe"
    Write-Host "[hint] Install Visual Studio Build Tools workload 'Desktop development with C++'."
    $failed = $true
  }

  $kernel32 = Find-Kernel32Lib
  if ($kernel32) {
    Write-Host "[ok] kernel32.lib -> $kernel32"
  } else {
    Write-Host "[missing] kernel32.lib"
    Write-Host "[hint] Install a Windows 10/11 SDK with x64 libraries."
    $failed = $true
  }

  if (Test-IsAdministrator) {
    Write-Host "[ok] Administrator shell for TSF registration"
  } else {
    Write-Host "[warn] Registering/unregistering the TSF IME requires an elevated Administrator PowerShell."
  }
}

if ($failed) {
  exit 1
}

Write-Host ""
Write-Host "Preflight passed."

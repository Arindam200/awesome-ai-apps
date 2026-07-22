param(
  [string]$ArtifactsRoot = "",
  [switch]$SkipRustInstall,
  [switch]$SkipNpmCi,
  [switch]$CleanArtifacts,
  [switch]$IncludeLocalAsrExperiment
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "windows-common.ps1")

$appRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$releaseRoot = Join-Path $appRoot "src-tauri\target\x86_64-pc-windows-msvc\release"
if ([string]::IsNullOrWhiteSpace($ArtifactsRoot)) {
  $ArtifactsRoot = Join-Path $appRoot ".artifacts\windows-msvc"
}

function Add-PathEntry($PathEntry) {
  if ([string]::IsNullOrWhiteSpace($PathEntry) -or -not (Test-Path $PathEntry)) {
    return
  }
  $entries = $env:PATH -split ";"
  if ($entries -notcontains $PathEntry) {
    $env:PATH = "$PathEntry;$env:PATH"
  }
}

function Test-Command($Name) {
  return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Install-RustMsvcToolchain {
  $cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
  Add-PathEntry $cargoBin

  $hasRustup = Test-Command "rustup"
  $hasCargo = Test-Command "cargo"
  $hasRustc = Test-Command "rustc"
  $hasToolchain = $false
  if ($hasRustup) {
    $toolchains = & cmd.exe /d /c "rustup toolchain list 2>nul"
    $hasToolchain = $LASTEXITCODE -eq 0 -and $toolchains -match "stable-x86_64-pc-windows-msvc"
  }

  if ($hasRustup -and $hasCargo -and $hasRustc -and $hasToolchain) {
    Write-Host "[ok] Rust MSVC toolchain already installed"
    return
  }

  if ($SkipRustInstall) {
    throw "Rust MSVC toolchain is missing. Re-run without -SkipRustInstall to install it automatically."
  }

  Write-Host "[info] Installing Rust stable-x86_64-pc-windows-msvc"
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  $rustupInit = Join-Path $env:TEMP "rustup-init-x86_64-pc-windows-msvc.exe"
  Invoke-WebRequest -Uri "https://win.rustup.rs/x86_64" -OutFile $rustupInit
  & $rustupInit -y --default-toolchain stable-x86_64-pc-windows-msvc

  Add-PathEntry $cargoBin
  & rustup toolchain install stable-x86_64-pc-windows-msvc
  & rustup default stable-x86_64-pc-windows-msvc

  if (-not (Test-Command "cargo") -or -not (Test-Command "rustc")) {
    throw "Rust installation finished, but cargo/rustc is still not available in PATH."
  }
}

function Find-VsDevCmd {
  $candidates = @()

  $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
  if (Test-Path $vswhere) {
    $installPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
    if (-not [string]::IsNullOrWhiteSpace($installPath)) {
      $candidates += (Join-Path $installPath "Common7\Tools\VsDevCmd.bat")
    }
  }

  $candidates += @(
    (Join-Path $env:ProgramFiles "Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"),
    (Join-Path $env:ProgramFiles "Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat"),
    (Join-Path $env:ProgramFiles "Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat"),
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat")
  )

  foreach ($candidate in $candidates) {
    if (Test-Path $candidate) {
      return (Resolve-Path $candidate).Path
    }
  }

  throw "VsDevCmd.bat not found. Install Visual Studio 2022 Build Tools with the Desktop development with C++ workload."
}

function Find-WixTool($Name) {
  $tauriWixRoot = Join-Path $env:LOCALAPPDATA "tauri"
  if (Test-Path $tauriWixRoot) {
    $tauriWixTools = Get-ChildItem -LiteralPath $tauriWixRoot -Directory -Filter "WixTools*" -ErrorAction SilentlyContinue |
      Sort-Object @{ Expression = { if ($_.Name -match '^WixTools(\d+)$') { [int]$Matches[1] } else { -1 } }; Descending = $true }, @{ Expression = "Name"; Descending = $true }
    foreach ($toolDir in $tauriWixTools) {
      $tauriWixTool = Join-Path $toolDir.FullName $Name
      if (Test-Path $tauriWixTool) {
        return (Resolve-Path $tauriWixTool).Path
      }
    }
  }

  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }

  throw "$Name not found. Run the Tauri MSI build once so a WiX tools directory is installed under $tauriWixRoot."
}

function Get-PackageVersion {
  $packageJson = Get-Content -LiteralPath (Join-Path $appRoot "package.json") -Raw | ConvertFrom-Json
  return $packageJson.version
}

function Get-PackageArtifactStem {
  return "Whisper_Input"
}

function Get-MsiName {
  return "$(Get-PackageArtifactStem)_$(Get-PackageVersion)_x64_en-US.msi"
}

function Get-MsiPath {
  return Join-Path $releaseRoot "bundle\msi\$(Get-MsiName)"
}

function Resolve-MsiPath {
  $canonicalPath = Get-MsiPath
  if (Test-Path $canonicalPath) {
    return $canonicalPath
  }

  $bundleDir = Split-Path -Parent $canonicalPath
  $generatedMsi = Get-ChildItem -LiteralPath $bundleDir -Filter "*.msi" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if ($generatedMsi) {
    return $generatedMsi.FullName
  }

  return $canonicalPath
}

function Get-NsisPath {
  $bundleDir = Join-Path $releaseRoot "bundle\nsis"
  if (-not (Test-Path $bundleDir)) {
    return Join-Path $bundleDir "Whisper_Input_$(Get-PackageVersion)_x64-setup.exe"
  }

  $generated = Get-ChildItem -LiteralPath $bundleDir -Filter "*.exe" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if ($generated) {
    return $generated.FullName
  }

  return Join-Path $bundleDir "Whisper_Input_$(Get-PackageVersion)_x64-setup.exe"
}

function Invoke-MsvcBuild {
  param(
    [string]$VsDevCmd,
    [string]$CargoBin
  )

  $nsisBundleDir = Split-Path -Parent (Get-NsisPath)
  if (Test-Path $nsisBundleDir) {
    Get-ChildItem -LiteralPath $nsisBundleDir -Filter "*.exe" -ErrorAction SilentlyContinue |
      Remove-Item -Force -ErrorAction SilentlyContinue
  }
  $msiBundleDir = Split-Path -Parent (Get-MsiPath)
  if (Test-Path $msiBundleDir) {
    Get-ChildItem -LiteralPath $msiBundleDir -Filter "*.msi" -ErrorAction SilentlyContinue |
      Remove-Item -Force -ErrorAction SilentlyContinue
  }

  $nsisCommand = "call `"$VsDevCmd`" -arch=x64 -host_arch=x64 && set `"PATH=$CargoBin;%PATH%`" && npm.cmd run tauri build -- --target x86_64-pc-windows-msvc --bundles nsis"
  & cmd.exe /d /c $nsisCommand
  if ($LASTEXITCODE -ne 0) {
    throw "Tauri Windows NSIS build failed with exit code $LASTEXITCODE."
  }

  $msiCommand = "call `"$VsDevCmd`" -arch=x64 -host_arch=x64 && set `"PATH=$CargoBin;%PATH%`" && npm.cmd run tauri build -- --target x86_64-pc-windows-msvc --bundles msi"
  & cmd.exe /d /c $msiCommand
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Tauri Windows MSI build returned exit code $LASTEXITCODE. Trying to finish MSI linking from generated WiX objects."
    Repair-TauriMsiBundle
  }
}

function Repair-TauriMsiBundle {
  $wixRoot = Join-Path $releaseRoot "wix\x64"
  $mainObject = Join-Path $wixRoot "main.wixobj"
  $locale = Join-Path $wixRoot "locale.wxl"
  $msiPath = Get-MsiPath

  foreach ($requiredPath in @($mainObject, $locale)) {
    if ([string]::IsNullOrWhiteSpace($requiredPath) -or -not (Test-Path $requiredPath)) {
      throw "Cannot repair Tauri MSI bundle because a required file is missing: $requiredPath"
    }
  }

  $bundleDir = Split-Path -Parent $msiPath
  New-Item -ItemType Directory -Force -Path $bundleDir | Out-Null
  Remove-Item -LiteralPath $msiPath -Force -ErrorAction SilentlyContinue

  $light = Find-WixTool "light.exe"
  & $light -nologo -ext WixUIExtension -ext WixUtilExtension -loc $locale -out $msiPath $mainObject
  if ($LASTEXITCODE -ne 0) {
    throw "WiX light.exe failed with exit code $LASTEXITCODE."
  }
  if (-not (Test-Path $msiPath)) {
    throw "WiX light.exe finished but MSI was not produced: $msiPath"
  }

  Write-Host "[ok] MSI linked from generated WiX objects -> $msiPath"
}

function Invoke-AsrSidecarBuild {
  $buildScript = Join-Path $PSScriptRoot "build-qingyu-asr-sidecar.ps1"
  $assetCheckScript = Join-Path $PSScriptRoot "check-sherpa-assets.ps1"

  if (-not (Test-Path $buildScript)) {
    throw "ASR sidecar build script not found: $buildScript"
  }
  if (-not (Test-Path $assetCheckScript)) {
    throw "sherpa asset check script not found: $assetCheckScript"
  }

  & $assetCheckScript
  if ($LASTEXITCODE -ne 0) {
    throw "sherpa asset check failed with exit code $LASTEXITCODE."
  }

  & $buildScript
  if ($LASTEXITCODE -ne 0) {
    throw "ASR sidecar build failed with exit code $LASTEXITCODE."
  }

  $binariesRoot = Join-Path $appRoot "src-tauri\binaries"
  $target = "x86_64-pc-windows-msvc"
  foreach ($requiredPath in @(
      (Join-Path $binariesRoot "qingyu-asr-sidecar-$target.exe"),
      (Join-Path $binariesRoot "sherpa-onnx-offline-$target.exe")
    )) {
    if (-not (Test-Path $requiredPath)) {
      throw "Required sidecar runtime binary was not produced: $requiredPath"
    }
  }

  Write-Host "[ok] ASR sidecar and sherpa runtime binaries are ready"
}

function Reset-ArtifactsRoot {
  if (-not $CleanArtifacts) {
    New-Item -ItemType Directory -Force -Path $ArtifactsRoot | Out-Null
    return
  }

  $resolvedAppRoot = (Resolve-Path $appRoot).Path
  if (Test-Path $ArtifactsRoot) {
    $resolvedArtifactsRoot = (Resolve-Path $ArtifactsRoot).Path
    $insideAppRoot = $resolvedArtifactsRoot.Equals($resolvedAppRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
      $resolvedArtifactsRoot.StartsWith("$resolvedAppRoot\", [System.StringComparison]::OrdinalIgnoreCase)
    if (-not $insideAppRoot) {
      throw "-CleanArtifacts refuses to delete output outside the app root: $resolvedArtifactsRoot"
    }
    Remove-Item -LiteralPath $resolvedArtifactsRoot -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $ArtifactsRoot | Out-Null
}

function Copy-WindowsArtifacts {
  $version = Get-PackageVersion
  $msiName = Get-MsiName
  $msiPath = Resolve-MsiPath
  $nsisPath = Get-NsisPath
  $exePath = Join-Path $releaseRoot "whisper-input.exe"
  $webView2Loader = Get-ChildItem -Path (Join-Path $releaseRoot "build") -Recurse -Filter "WebView2Loader.dll" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "\\out\\x64\\WebView2Loader\.dll$" } |
    Select-Object -First 1

  if (-not (Test-Path $nsisPath)) {
    throw "NSIS installer not found: $nsisPath"
  }
  if (-not (Test-Path $msiPath)) {
    throw "MSI not found: $msiPath"
  }
  if (-not (Test-Path $exePath)) {
    throw "Release exe not found: $exePath"
  }
  if ($null -eq $webView2Loader) {
    throw "WebView2Loader.dll x64 not found under $releaseRoot\build"
  }

  Reset-ArtifactsRoot
  $setupName = "Whisper_Input_${version}_x64_setup.exe"
  Copy-Item -LiteralPath $nsisPath -Destination (Join-Path $ArtifactsRoot $setupName) -Force
  Copy-Item -LiteralPath $msiPath -Destination (Join-Path $ArtifactsRoot $msiName) -Force

  $portableName = "$(Get-PackageArtifactStem)_${version}_x64_portable"
  $portableRoot = Join-Path $ArtifactsRoot $portableName
  New-Item -ItemType Directory -Force -Path $portableRoot | Out-Null
  Copy-Item -LiteralPath $exePath -Destination (Join-Path $portableRoot "Whisper Input.exe") -Force
  Copy-Item -LiteralPath $webView2Loader.FullName -Destination (Join-Path $portableRoot "WebView2Loader.dll") -Force

  if ($IncludeLocalAsrExperiment) {
    Write-Host "Including deprecated non-product local ASR experiment assets."
    $binariesRoot = Join-Path $appRoot "src-tauri\binaries"
    $target = "x86_64-pc-windows-msvc"
    $asrSidecar = Join-Path $binariesRoot "qingyu-asr-sidecar-$target.exe"
    $sherpaOffline = Join-Path $binariesRoot "sherpa-onnx-offline-$target.exe"

    if (-not (Test-Path $asrSidecar)) {
      throw "ASR sidecar not found for portable package: $asrSidecar"
    }
    if (-not (Test-Path $sherpaOffline)) {
      throw "sherpa offline binary not found for portable package: $sherpaOffline"
    }

    Copy-Item -LiteralPath $asrSidecar -Destination (Join-Path $portableRoot (Split-Path -Leaf $asrSidecar)) -Force
    Copy-Item -LiteralPath $sherpaOffline -Destination (Join-Path $portableRoot (Split-Path -Leaf $sherpaOffline)) -Force
    $sherpaRuntimeName = "sherpa-onnx-offline.exe"
    Copy-Item -LiteralPath $sherpaOffline -Destination (Join-Path $portableRoot $sherpaRuntimeName) -Force
  } else {
    Write-Host "Skipping local ASR experiment assets for standard cloud-first package."
  }

  $zipPath = Join-Path $ArtifactsRoot "$portableName.zip"
  Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
  Compress-Archive -LiteralPath $portableRoot -DestinationPath $zipPath -CompressionLevel Optimal

  Write-Host ""
  Write-Host "Windows artifacts:"
  Get-ChildItem -File -LiteralPath $ArtifactsRoot | Select-Object Name,Length,LastWriteTime | Format-Table -AutoSize

  Write-Host "SHA256:"
  Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $ArtifactsRoot $setupName), (Join-Path $ArtifactsRoot $msiName), $zipPath | Select-Object Path,Hash | Format-List
}

Push-Location $appRoot
try {
  Write-Host "[info] App root: $appRoot"
  Install-RustMsvcToolchain
  Test-WebView2Runtime

  $vsDevCmd = Find-VsDevCmd
  Write-Host "[ok] VsDevCmd.bat -> $vsDevCmd"

  if (-not (Test-Command "node") -or -not (Test-Command "npm.cmd")) {
    throw "Node.js/npm.cmd not found. Install Node.js before packaging."
  }

  if ($SkipNpmCi) {
    if (-not (Test-Path (Join-Path $appRoot "node_modules"))) {
      throw "-SkipNpmCi was set, but node_modules does not exist."
    }
    Write-Host "[info] Skipping npm.cmd ci"
  } else {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) {
      throw "npm.cmd ci failed with exit code $LASTEXITCODE."
    }
  }

  $cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
  if ($IncludeLocalAsrExperiment) {
    Write-Host "Including deprecated non-product local ASR experiment assets."
    Invoke-AsrSidecarBuild
  } else {
    Write-Host "Skipping local ASR experiment assets for standard cloud-first package."
  }
  Invoke-MsvcBuild -VsDevCmd $vsDevCmd -CargoBin $cargoBin
  Copy-WindowsArtifacts
} finally {
  Pop-Location
}

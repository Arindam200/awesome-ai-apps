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

param(
  [string]$OutPath = ""
)

$ErrorActionPreference = "Stop"

$appRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutPath)) {
  $OutPath = Join-Path $appRoot "public\whisper-input-icon-source.png"
}

Add-Type -AssemblyName System.Drawing

function New-RoundedRectPath {
  param(
    [float]$X,
    [float]$Y,
    [float]$Width,
    [float]$Height,
    [float]$Radius
  )
  $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
  $diameter = $Radius * 2
  $path.AddArc($X, $Y, $diameter, $diameter, 180, 90)
  $path.AddArc($X + $Width - $diameter, $Y, $diameter, $diameter, 270, 90)
  $path.AddArc($X + $Width - $diameter, $Y + $Height - $diameter, $diameter, $diameter, 0, 90)
  $path.AddArc($X, $Y + $Height - $diameter, $diameter, $diameter, 90, 90)
  $path.CloseFigure()
  return $path
}

function Fill-RoundedRect {
  param(
    [System.Drawing.Graphics]$Graphics,
    [System.Drawing.Brush]$Brush,
    [float]$X,
    [float]$Y,
    [float]$Width,
    [float]$Height,
    [float]$Radius
  )
  $path = New-RoundedRectPath -X $X -Y $Y -Width $Width -Height $Height -Radius $Radius
  try {
    $Graphics.FillPath($Brush, $path)
  } finally {
    $path.Dispose()
  }
}

function Save-ResizedPng {
  param(
    [System.Drawing.Bitmap]$Source,
    [string]$Path,
    [int]$Size
  )
  $target = [System.Drawing.Bitmap]::new($Size, $Size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($target)
  try {
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.DrawImage($Source, 0, 0, $Size, $Size)
    $target.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
  } finally {
    $g.Dispose()
    $target.Dispose()
  }
}

$size = 1024
$bitmap = [System.Drawing.Bitmap]::new($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)

try {
  $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $graphics.Clear([System.Drawing.Color]::Transparent)

  $bounds = [System.Drawing.RectangleF]::new(72, 72, 880, 880)
  $bgPath = New-RoundedRectPath -X $bounds.X -Y $bounds.Y -Width $bounds.Width -Height $bounds.Height -Radius 210
  $bgBrush = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
    $bounds,
    [System.Drawing.Color]::FromArgb(255, 29, 98, 240),
    [System.Drawing.Color]::FromArgb(255, 101, 83, 246),
    [System.Drawing.Drawing2D.LinearGradientMode]::ForwardDiagonal
  )
  $graphics.FillPath($bgBrush, $bgPath)

  $shineBrush = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
    [System.Drawing.RectangleF]::new(128, 112, 768, 380),
    [System.Drawing.Color]::FromArgb(82, 255, 255, 255),
    [System.Drawing.Color]::FromArgb(0, 255, 255, 255),
    [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
  )
  Fill-RoundedRect -Graphics $graphics -Brush $shineBrush -X 144 -Y 118 -Width 736 -Height 342 -Radius 160

  $shadowBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(44, 25, 38, 120))
  Fill-RoundedRect -Graphics $graphics -Brush $shadowBrush -X 238 -Y 634 -Width 548 -Height 92 -Radius 46

  $white = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(255, 255, 255, 255))
  $softWhite = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(225, 255, 255, 255))

  $centerX = 512
  $centerY = 508
  $barWidth = 58
  $gap = 28
  $heights = @(310, 430, 560, 700, 560, 430, 310)
  for ($i = 0; $i -lt $heights.Count; $i++) {
    $x = $centerX - (($barWidth + $gap) * 3.5) + ($i * ($barWidth + $gap)) + ($gap / 2)
    $h = $heights[$i]
    $y = $centerY - ($h / 2)
    $brush = if ($i -eq 3) { $white } else { $softWhite }
    Fill-RoundedRect -Graphics $graphics -Brush $brush -X $x -Y $y -Width $barWidth -Height $h -Radius 29
  }

  Fill-RoundedRect -Graphics $graphics -Brush $white -X 166 -Y 474 -Width 132 -Height 68 -Radius 34
  Fill-RoundedRect -Graphics $graphics -Brush $white -X 726 -Y 474 -Width 132 -Height 68 -Radius 34

  $rimPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(70, 255, 255, 255), 3)
  $graphics.DrawPath($rimPen, $bgPath)

  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutPath) | Out-Null
  $bitmap.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
  $appIconPath = Join-Path $appRoot "public\AppIcon.png"
  $previewIconPath = Join-Path $appRoot "public\preview-app-icon.png"
  Save-ResizedPng -Source $bitmap -Path $appIconPath -Size 1024
  Save-ResizedPng -Source $bitmap -Path $previewIconPath -Size 30
  Write-Host "[ok] icon source generated -> $OutPath"
  Write-Host "[ok] frontend app icon refreshed -> $appIconPath"
  Write-Host "[ok] frontend title icon refreshed -> $previewIconPath"
} finally {
  if ($rimPen) { $rimPen.Dispose() }
  if ($white) { $white.Dispose() }
  if ($softWhite) { $softWhite.Dispose() }
  if ($shadowBrush) { $shadowBrush.Dispose() }
  if ($shineBrush) { $shineBrush.Dispose() }
  if ($bgBrush) { $bgBrush.Dispose() }
  if ($bgPath) { $bgPath.Dispose() }
  $graphics.Dispose()
  $bitmap.Dispose()
}

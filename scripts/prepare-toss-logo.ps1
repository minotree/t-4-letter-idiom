$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$projectRoot = Split-Path -Parent $PSScriptRoot
$source = [System.Drawing.Image]::FromFile((Join-Path $projectRoot 'assets/app-icon.PNG'))
$bitmap = [System.Drawing.Bitmap]::new(600, 600)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.Clear([System.Drawing.Color]::White)
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $ratio = 600 / [Math]::Max($source.Width, $source.Height)
    $width = [int][Math]::Round($source.Width * $ratio)
    $height = [int][Math]::Round($source.Height * $ratio)
    $graphics.DrawImage($source, [int]((600 - $width) / 2), [int]((600 - $height) / 2), $width, $height)
    $bitmap.Save((Join-Path $projectRoot 'assets/toss-app-logo-600.png'), [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output 'assets/toss-app-logo-600.png: 600x600'
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
    $source.Dispose()
}

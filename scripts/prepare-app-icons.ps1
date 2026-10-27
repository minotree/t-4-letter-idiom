$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$projectRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $projectRoot 'assets/app-icon.PNG'
$outputDirectory = Join-Path $projectRoot 'apps/web/public'
$source = [System.Drawing.Image]::FromFile($sourcePath)
try {
    foreach ($spec in @(
        @{ Name = 'favicon.png'; Size = 32; Scale = 1.0 },
        @{ Name = 'apple-touch-icon.png'; Size = 180; Scale = 1.0 },
        @{ Name = 'icon-192.png'; Size = 192; Scale = 1.0 },
        @{ Name = 'icon-512.png'; Size = 512; Scale = 1.0 },
        @{ Name = 'icon-maskable-512.png'; Size = 512; Scale = 0.8 }
    )) {
        $bitmap = [System.Drawing.Bitmap]::new($spec.Size, $spec.Size)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.Clear([System.Drawing.Color]::White)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $ratio = $spec.Size * $spec.Scale / [Math]::Max($source.Width, $source.Height)
            $width = [int][Math]::Round($source.Width * $ratio)
            $height = [int][Math]::Round($source.Height * $ratio)
            $graphics.DrawImage($source, [int](($spec.Size - $width) / 2), [int](($spec.Size - $height) / 2), $width, $height)
            $bitmap.Save((Join-Path $outputDirectory $spec.Name), [System.Drawing.Imaging.ImageFormat]::Png)
            Write-Output "$($spec.Name): $($spec.Size)x$($spec.Size)"
        } finally {
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    }
} finally {
    $source.Dispose()
}

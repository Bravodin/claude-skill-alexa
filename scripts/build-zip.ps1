# Builds dist/claudinho-lambda.zip for the "Import Code" button in the Alexa Developer Console.
# Import Code requires a "lambda/" folder at the zip root.
# The zip includes lambda/anthropic_key.txt, so never commit or share it (dist/ is gitignored).
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$root = Split-Path -Parent $PSScriptRoot
$lambda = Join-Path $root "lambda"
$dist = Join-Path $root "dist"
$zip = Join-Path $dist "claudinho-lambda.zip"

if (-not (Test-Path (Join-Path $lambda "anthropic_key.txt"))) {
    Write-Error "lambda/anthropic_key.txt not found. Create it with your Claude API key first (see README)."
}

New-Item -ItemType Directory -Force $dist | Out-Null
if (Test-Path $zip) { Remove-Item $zip }

$files = Get-ChildItem $lambda -File | Where-Object { $_.Extension -ne ".pyc" }

# Write entries by hand so paths use "/" on both Windows PowerShell 5.1 and PowerShell 7.
$archive = [System.IO.Compression.ZipFile]::Open($zip, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($file in $files) {
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file.FullName, "lambda/$($file.Name)") | Out-Null
    }
} finally {
    $archive.Dispose()
}

Write-Host "Created $zip with:"
$files | ForEach-Object { Write-Host "  lambda/$($_.Name)" }

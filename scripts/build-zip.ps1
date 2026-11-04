# Builds dist/claudinho-lambda.zip for the "Import Code" button in the Alexa Developer Console.
# The zip includes lambda/anthropic_key.txt, so never commit or share it (dist/ is gitignored).
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$lambda = Join-Path $root "lambda"
$dist = Join-Path $root "dist"
$zip = Join-Path $dist "claudinho-lambda.zip"

if (-not (Test-Path (Join-Path $lambda "anthropic_key.txt"))) {
    Write-Error "lambda/anthropic_key.txt not found. Create it with your Claude API key first (see README)."
}

New-Item -ItemType Directory -Force $dist | Out-Null

$files = Get-ChildItem $lambda -File | Where-Object { $_.Extension -ne ".pyc" }
Compress-Archive -Path $files.FullName -DestinationPath $zip -Force

Write-Host "Created $zip with:"
$files | ForEach-Object { Write-Host "  $($_.Name)" }

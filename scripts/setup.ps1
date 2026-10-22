$ErrorActionPreference = "Stop"
Push-Location (Join-Path $PSScriptRoot "..")
try {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "uv is missing; installing with the official Astral installer."
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        $env:PATH = "$HOME\.local\bin;$env:PATH"
    }
    uv sync
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Write-Warning "ffmpeg is missing from PATH; it is required for manimgl render --GL."
    }
    uv run --frozen manim-cue render examples/orbit.py Orbit
    if ($LASTEXITCODE -ne 0) { throw "Orbit render failed" }
    uv run --frozen manim-cue render examples/demo.py Demo
    if ($LASTEXITCODE -ne 0) { throw "Demo render failed" }
    Write-Host "Ready: uv run manim-cue present Demo"
    Write-Host "Right/Left: slides; Space: pause; R: replay; V: reverse; F: fullscreen; H: mouse; S: state; Q: quit."
    Write-Host "Click live to control it; Esc returns to slides. Info can use a second monitor; add --show-info-window on one monitor."
} finally {
    Pop-Location
}

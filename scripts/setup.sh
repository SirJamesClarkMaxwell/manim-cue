#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if ! command -v uv >/dev/null 2>&1; then
    echo "uv is missing; installing with the official Astral installer."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
uv sync
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Warning: ffmpeg is missing from PATH; it is required for manimgl render --GL." >&2
fi
uv run --frozen manim-cue render examples/orbit.py Orbit
uv run --frozen manim-cue render examples/demo.py Demo
echo "Ready: uv run manim-cue present Demo"
echo "Right/Left: slides; Space: pause; R: replay; V: reverse; F: fullscreen; H: mouse; S: state; Q: quit."
echo "Click live to control it; Esc returns to slides. Info can use a second monitor; add --show-info-window on one monitor."

"""manim-cue: żywa scena Manima wyzwalana z zewnątrz.

Architektura, decyzje transportowe i kryteria akceptacji: SPEC.md w korzeniu projektu.
Faza 0: `manimcue.live_scene.LiveScene` plus klient testowy `manimcue.cue`.
Faza 1: `manimcue.slides` — fork manim-slides 5.7.0, CLI `manim-cue`.
"""

__version__ = "0.1.0"

HOST = "127.0.0.1"
"""Nasłuch tylko na pętli zwrotnej. Model bezpieczeństwa jawnie niezabezpieczony — SPEC.md."""

DEFAULT_PORT = 47821
"""Port domyślny; nadpisywany zmienną środowiskową MANIMCUE_PORT."""

PORT_ENV_VAR = "MANIMCUE_PORT"
"""Launcher manimgl woła argparse.parse_args() bez passthrough, więc własnego
`--port` nie da się podać w jego linii komend — endpoint bierzemy ze środowiska."""

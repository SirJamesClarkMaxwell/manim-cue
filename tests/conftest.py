"""Ustawienia wspólne dla wszystkich testów."""

import os
import sys
from pathlib import Path

# Qt bez ekranu, zanim cokolwiek zaimportuje qtpy. Nie daje kontekstu GL — ten manimgl tworzy
# sam (standalone ModernGL); testy z prawdziwym GL mają znacznik `gpu`.
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# manimgl przy imporcie parsuje sys.argv własnym argparse (manimlib/config.py, parse_cli)
# i kończy proces na każdej nieznanej mu opcji pytesta (-x, -k, --ignore...). Upstream
# manim-slides podmienia argv wokół importu w pojedynczych testach; tutaj raz, dla całej sesji.
# Pytest swoje argumenty ma już w tym momencie sparsowane.
#
# --config_file: testy upstreamu zakładają czarne tło z custom_config.yml, który manimgl
# czyta z katalogu roboczego — w upstreamie leży w korzeniu repo. Tutaj nie kładziemy go
# do korzenia, bo zmieniłby tło LiveScene przy zwykłym uruchomieniu.
sys.argv = [
    sys.argv[0],
    "--config_file",
    str(Path(__file__).parent / "slides" / "data" / "custom_config.yml"),
]

# Konfiguracja manimgl to singleton liczony przy pierwszym imporcie. Inicjalizujemy go tu,
# bo slides/slide/manimlib.py przed własnym importem podmienia argv na [__file__] i zgubiłby
# --config_file, gdyby był pierwszy.
import manimlib.config  # noqa: F401

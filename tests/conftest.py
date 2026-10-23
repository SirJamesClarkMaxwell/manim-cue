"""Ustawienia wspólne dla wszystkich testów."""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def write_manim_config(directory: Path) -> Path:
    """Izolowane cwd także potrzebuje zapisywalnego cache GL, bez zmian w Manimie."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "custom_config.yml"
    cache = (ROOT / ".cache" / "manimgl").as_posix()
    path.write_text(
        f"camera:\n  background_color: '#000000'\ndirectories:\n  cache: {cache}\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture(autouse=True)
def temporary_manim_config(tmp_path):
    write_manim_config(tmp_path)

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
    str(write_manim_config(ROOT / ".tmp" / "pytest-config")),
]

# Konfiguracja manimgl to singleton liczony przy pierwszym imporcie. Inicjalizujemy go tu,
# bo slides/slide/manimlib.py przed własnym importem podmienia argv na [__file__] i zgubiłby
# --config_file, gdyby był pierwszy.
import manimlib.config  # noqa: F401

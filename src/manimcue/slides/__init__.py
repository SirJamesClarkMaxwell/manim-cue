"""Fork manim-slides 5.7.0 (MIT, licencja w ``LICENSE.md`` obok).

Zmiany względem upstreamu (D13 w SPEC.md): importy ``manim_slides`` -> ``manimcue.slides``,
usunięte ``ipython/`` i ``docs/``, sprawdzanie wersji na PyPI domyślnie wyłączone. Zamiast
podmiany modułu w ``sys.modules`` — zwykły ``__getattr__`` modułu (PEP 562), bo jedynym powodem
podmiany było leniwe ładowanie magii IPython, której fork nie ma.
"""

from typing import Any

from .__version__ import __version__

__all__ = ("Slide", "ThreeDSlide", "__version__")


def __getattr__(name: str) -> Any:
    # Leniwie, jak w upstreamie: Slide ciągnie Manima, a present/convert go nie potrzebują.
    if name in ("Slide", "ThreeDSlide"):
        from . import slide

        return getattr(slide, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Panel live do demo decku: presety fazy 0 (rotate, pulse, sweep) jako warstwa slajdu.

Warstwa wskazuje podklasę z tego pliku, nie samo `LiveScene`: worker ładuje plik sceny pod własną
nazwą modułu, więc `live_scene.py` wczytany po ścieżce dałby drugą, obcą klasę `LiveScene`.
"""

from manimcue.live_scene import LiveScene


class Panel(LiveScene):
    """Kwadrat i koło z fazy 0; od F4 sterowane strzałkami po kliknięciu warstwy."""

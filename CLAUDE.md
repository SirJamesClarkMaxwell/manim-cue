# manim-cue — instrukcje dla agenta

## Przeczytaj najpierw

1. **`SPEC.md`** — ustalenia zweryfikowane w kodzie manimgl, architektura, dwie pułapki, na których
   szkic już raz padł, i kryteria akceptacji. Ten plik jest wynikiem pięciu rund adwersaryjnej
   recenzji; **nie wyprowadzaj tych faktów od nowa i nie zmieniaj decyzji bez powodu.**
2. **`PLAN.md`** — fazy. Faza 0 jest jedyną aktywną.

## Zasady

- **Zakres fazy 0 jest zamknięty.** Dziewięć kryteriów akceptacji z `SPEC.md`, nic poza tym.
  Pierwotny szacunek to ~1 h na Windowsie. Przy przekroczeniu ~2 h — zatrzymać się i zgłosić.
- **Nie rozszerzaj o synchronizację wielu wideo.** Jest jawnie poza zakresem i ma podany powód.
- **Nie forkuj Manima.** Projekt jest sterownikiem nad istniejącym API.
- **Identyfikatory po angielsku, docstringi i komentarze po polsku.** Projekt macierzysty ma stan
  mieszany (`self.trojkat.set_color()` obok `self.vacancy_bonds`) i to jest uznane za błąd —
  nie powtarzać go tutaj.
- **Jeden wątek.** Rozwiązaniem czekania jest `select` z timeoutem jednej klatki, nie wątek odbiorczy.

## Środowisko

`uv`, Python ≥3.13. `uv sync` instaluje manimgl, `setuptools<80.10.2` i `audioop-lts`
(powody obu pinów w komentarzach w `pyproject.toml`).

**Dwie miny środowiskowe, oba już rozwiązane — nie usuwać tych zależności:**
- `audioop` wypadł ze stdlib w Pythonie 3.13 (PEP 594), a `manimgl` ciągnie `pydub`, który go
  wymaga. Bez `audioop-lts` `import manimlib` pada na `ModuleNotFoundError: No module named
  'audioop'`. W projekcie seminarium manimgl działa przypadkiem, bo tam jest Manim CE, który sam
  deklaruje `audioop-lts` dla 3.13+.
- `manimgl` importuje `pkg_resources` i sam ostrzega „pin to Setuptools<81". `setuptools<80.10.2`
  to ciaśniejsza granica wzięta z extry `[manimgl]` manim-slides, zweryfikowana w praniu.
Uruchomienie wymaga **okna** — `manimgl` otwiera je domyślnie, `-p` to tryb presentera i nie jest
potrzebny. W renderze offline (`-w`, `-o`) scena ma rzucić czytelny `RuntimeError`.

## Projekt macierzysty

`C:\Users\fzabi\Desktop\STUDIA\scientific-student-seminaries\group-theory` — plan seminarium
(`PLAN.md`, decyzja D18 i R8) oraz pełna historia argumentów (`PLAN-REVIEW-LOG.md`).
Punkt integracji, gdy faza 2 dojdzie: klasy bazowe `SeminarScene` / `SeminarScene3D` w tamtym
`deck/base.py`, **nie** sceny treściowe.

## Sąsiednie projekty w `dev/`, warto znać

- **`groupy`** (PyPI: `groupy-symmetry`) — teoria grup punktowych: tabele charakterów, macierze
  reprezentacji, SALC, funkcje wielociałowe, grupy podwójne. Jeśli `manim-cue` kiedykolwiek będzie
  potrzebował danych grupowych, bierze je stąd, a nie przepisuje.
- **`manim-claude`** — korpus ~900 reguł o konstrukcji animacji i organizacji kodu Manima,
  wydobytych z kodu 3b1b i bibliotek społecznościowych. Źródło idiomów.
- **`manim-plots`**, **`manimations`** — inne projekty manimowe, osobne zakresy.

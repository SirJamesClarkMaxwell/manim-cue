# manim-cue — instrukcje dla agenta

## Przeczytaj najpierw

1. **`SPEC.md`** — ustalenia zweryfikowane w kodzie manimgl, manim-slides i Manim CE, architektura,
   trzy pułapki, na których szkic już padł, kryteria akceptacji fazy 0 i decyzje D1-D19.
   Fazy 0 dotyczyło pięć rund adwersaryjnej recenzji; **nie wyprowadzaj tych faktów od nowa i nie
   zmieniaj decyzji bez powodu.**
2. **`PLAN.md`** — fazy. F5d-f: kryteria 1–4 wykonane, próba człowieka pozostaje; F5g: kontrakt domknięty rundą 20 (D39–D41), stan implementacji, testów i pomiarów w `reports/REPORT-5g.md`; próba człowieka pozostaje. F4–F6a czekają na próbę, 6b na decyzję o zależności. 7.0 (CE 0.22) zamknięta; 7a: kontrakt domknięty rundą 19, adapter Cairo 2D wdrożony, wyniki testów/pomiarów i ograniczenia w `PLAN.md` (sekcja 7a) i `experiments/f7a_cairo/`; próba człowieka przed fazą 8. F10: kontrakt po rundzie 21 (D42–D44), codex wykonuje etapami, Claude przegląda; 10a zatrzymane na bramce 1 (brak imgui-bundle w cache offline i brak prawdziwego okna), szczegóły w `reports/REPORT-10a.md`; `--player imgui` jeszcze niewdrożony.
3. **`REVIEW-LOG.md`** — rundy recenzji codex; runda 7 zawiera kontrakt fazy 2.

## Zasady

- **Zakres fazy jest zamknięty.** Kryteria akceptacji z `PLAN.md`, nic poza tym. Każda faza ma
  szacunek czasu; przy przekroczeniu dwukrotnym — zatrzymać się i zgłosić.
- **Synchronizacja warstw to wspólny start i pauza (D17).** Zegar główny, seek, frame-lock — poza
  zakresem, z podanym powodem.
- **Nie forkuj Manima.** Forkujemy manim-slides (D13) — to nie Manim. CE, GL i GX używamy przez
  ich istniejące API.
- **Identyfikatory po angielsku, docstringi i komentarze po polsku.** Projekt macierzysty ma stan
  mieszany (`self.trojkat.set_color()` obok `self.vacancy_bonds`) i to jest uznane za błąd —
  nie powtarzać go tutaj. **Wyjątek:** kod z forka w `src/manimcue/slides/` zachowuje angielskie
  komentarze upstreamu, żeby diff z kolejnym wydaniem manim-slides dał się nałożyć.
- **Jeden wątek kodu aplikacji na proces.** Player Qt i proces live to osobne procesy (D15).
  Wewnętrzne wątki Qt i sterowników są dozwolone (backend FFmpeg Qt sam je uruchamia). W procesie
  live rozwiązaniem czekania jest `select` z timeoutem jednej klatki, nie wątek odbiorczy.
- **Plan i decyzje przechodzą przez codex.** Po zmianie planu albo decyzji w SPEC — runda
  adwersaryjnej recenzji `codex exec -s read-only`, wynik w `REVIEW-LOG.md`.

## Środowisko

`uv`, Python ≥3.13. `uv sync` instaluje manimgl, `setuptools<80.10.2` i `audioop-lts`
(powody obu pinów w komentarzach w `pyproject.toml`).

**Trzy miny środowiskowe, wszystkie już rozwiązane — nie usuwać tych zależności:**
- `audioop` wypadł ze stdlib w Pythonie 3.13 (PEP 594), a `manimgl` ciągnie `pydub`, który go
  wymaga. Bez `audioop-lts` `import manimlib` pada na `ModuleNotFoundError: No module named
  'audioop'`. W projekcie seminarium manimgl działa przypadkiem, bo tam jest Manim CE, który sam
  deklaruje `audioop-lts` dla 3.13+.
- `manimgl` importuje `pkg_resources` i sam ostrzega „pin to Setuptools<81". `setuptools<80.10.2`
  to ciaśniejsza granica wzięta z extry `[manimgl]` manim-slides, zweryfikowana w praniu.
- `pillow<13`: Manim CE 0.21 woła `Image.fromarray(..., mode="RGBA")` przy każdym `ImageMobject`
  w Cairo, a Pillow 13 usunął parametr `mode` → `Invalid mode for data type`.
`LiveScene` w trybie zwykłym wymaga **okna** — `manimgl` otwiera je domyślnie, `-p` to tryb
presentera i nie jest potrzebny. W renderze offline (`-w`, `-o`) scena ma rzucić czytelny
`RuntimeError`.

## Projekt macierzysty

`C:\Users\fzabi\Desktop\STUDIA\scientific-student-seminaries\group-theory` (ścieżka z innej maszyny;
na tej jej nie ma) — plan seminarium (`PLAN.md`, decyzja D18 i R8) oraz pełna historia argumentów
(`PLAN-REVIEW-LOG.md`). Punkt integracji (faza 7): klasy bazowe `SeminarScene` / `SeminarScene3D`
w tamtym `deck/base.py`, **nie** sceny treściowe.

## Sąsiednie projekty w `dev/`, warto znać

- **`groupy`** (PyPI: `groupy-symmetry`) — teoria grup punktowych: tabele charakterów, macierze
  reprezentacji, SALC, funkcje wielociałowe, grupy podwójne. Jeśli `manim-cue` kiedykolwiek będzie
  potrzebował danych grupowych, bierze je stąd, a nie przepisuje.
- **`manim-claude`** — korpus ~900 reguł o konstrukcji animacji i organizacji kodu Manima,
  wydobytych z kodu 3b1b i bibliotek społecznościowych. Źródło idiomów.
- **`manim-plots`**, **`manimations`** — inne projekty manimowe, osobne zakresy.

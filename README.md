# manim-cue

Żywa scena Manima wyzwalana z zewnątrz. Jedno miejsce, które steruje animacją i ją wyzwala —
żeby dało się potem synchronizować więcej źródeł.

Od fazy 1 projekt jest też **forkiem [manim-slides](https://github.com/jeertmans/manim-slides)
5.7.0** (MIT, © Jérome Eertmans; licencja w `src/manimcue/slides/LICENSE.md`): prezentacja
prerenderowanych slajdów z notatkami i podglądem, docelowo z warstwami i wstrzykiwanym live
(`PLAN.md`, decyzje D13-D19 w `SPEC.md`).

```bash
uv run manim-cue render examples/demo.py Demo        # Manim CE (<0.22, powód w pyproject.toml)
uv run manim-cue render --GL examples/demo.py Demo   # manimgl
uv run manim-cue present Demo
```

Różnice względem upstreamu: importy `manimcue.slides` zamiast `manim_slides`, CLI `manim-cue`,
bez `%%manim_slides` (IPython) i dyrektywy Sphinx, bez sprawdzania wersji na PyPI. Plik
konfiguracji `.manim-slides.toml` i logger `manim-slides` zostają — zgodność z istniejącymi
deckami.

## Problem

Manim ma jeden model wykonania: `construct()` leci raz, liniowo, do pliku. Brakuje sceny, która
**żyje** i przyjmuje polecenia z zewnątrz. `manimgl` ma `Scene.embed()`, ale źródłem wyzwalania
jest tam człowiek przy prompcie IPythona, nie program.

## Czym to ma być

`Scene` jak każda inna — `self.play()`, `self.add()`, `self.wait()` i metody mobjectów działają
normalnie — której `construct()` kręci się na zdarzeniach zewnętrznych zamiast lecieć liniowo.

```bash
uv run manimgl src/manimcue/live_scene.py LiveScene
# w drugim terminalu:
uv run python -m manimcue.cue rotate
```

Port: `MANIMCUE_PORT` (domyślnie `47821`). Nie `--port` — launcher `manimgl` woła
`argparse.parse_args()` bez passthrough i odrzuciłby nieznany argument, zanim scena wstanie
(powód w `SPEC.md`). Scena wypisuje przy starcie faktycznie zbindowany endpoint:

```
manim-cue listening on 127.0.0.1:47821
```

## Komendy

| Komenda  | Co robi                                                     |
|----------|-------------------------------------------------------------|
| `rotate` | obrót kwadratu o 90° (1 s)                                  |
| `pulse`  | skok skali koła i powrót (2 × 0,5 s)                        |
| `sweep`  | przejazd kwadratu tam i z powrotem (6 s) — do testu kolejki |

Nieznana komenda → ostrzeżenie w logu, scena żyje dalej.

## Sterowanie strzałkami

Okno przyjmuje też klawiaturę, niezależnie od gniazda:

| Klawisz | Co robi |
|---------|---------|
| `→` | kolejne cue z sekwencji `rotate` → `pulse` → `sweep` |
| `←` | cofnięcie ostatniego cue — animowany powrót do stanu sprzed niego |

Komenda z gniazda wyzwala preset po nazwie i **nie** przesuwa pozycji w sekwencji, więc zdalny
klient nie przestawia prezentacji pod rękami prelegenta. Wyjątek: komendy `next` i `back` to
jawne odpowiedniki strzałek i kursor przesuwają. Gdy klawisz i komenda czekają razem,
pierwszeństwo ma klawisz. Klawisz albo komenda w trakcie animacji **urywa ją** i scena skacze do
stanu końcowego (D10). `pulse` jest zapętlone do następnego klawisza albo komendy (D9). Log
pokazuje pozycję: `Cue: pulse  [2/3, nastepne: sweep]  [petla]`.

Powody tych decyzji (D1-D3, D9, D10) są w `SPEC.md`. Cofanie to `Transform` do stanu zapisanego
przed cue, domknięty przez `Scene.undo()` manimgl — interpolacja między stanami, nie odtworzenie
animacji od końca.

## Czym to nie ma być

- **Nie forkiem Manima.** Forkiem manim-slides — Manima (CE/GL/GX) używamy przez istniejące API.
- **Nie przechwytywaniem ekranu.** OBS kompozytuje niezależne źródła, więc nie daje jednego
  punktu sterowania.
- **Nie synchronizatorem co do klatki.** Warstwy startują i pauzują razem (D17), bez zegara
  głównego i seeków.

## Dokumenty

- `SPEC.md` — ustalenia zweryfikowane w kodzie manimgl, architektura, pułapki, kryteria akceptacji.
  Powstał z pięciu rund adwersaryjnej recenzji; **przeczytaj przed pisaniem kodu.**
- `PLAN.md` — plan rozwoju w fazach.

## Pochodzenie

Wydzielone z planu seminarium z teorii grup
(`STUDIA/scientific-student-seminaries/group-theory/`), gdzie potrzeba wyszła przy scenie
pokazującej cztery równoległe widoki grupy punktowej. Tam rozwiązaniem docelowym zostały
prerenderowane kadry PNG; ten projekt jest drogą do zastąpienia ich żywym renderem.
Historia argumentów: `group-theory/PLAN-REVIEW-LOG.md` w tamtym repo.

## Testowanie

Bez okna — kryteria 3, 4, 7, 8 fazy 0, trzy pułapki z `SPEC.md` oraz testy upstreamu
manim-slides (`tests/slides/`, w tym render CE i GL):

```bash
uv run pytest -q
uv run manimgl src/manimcue/live_scene.py LiveScene -w   # ma dac RuntimeError, nie render
```

Z oknem — kryteria 1, 2, 5, 6. Terminal A trzyma scenę, terminal B wysyła komendy:

```bash
# A:
uv run manimgl src/manimcue/live_scene.py LiveScene

# B, po kolei:
uv run python -m manimcue.cue rotate                        # kryt. 2: animacja w oknie
uv run python -m manimcue.cue --mode split rotate           # kryt. 4: komenda w dwoch pakietach
uv run python -m manimcue.cue --mode together rotate pulse  # kryt. 4: dwie w jednym pakiecie
uv run python -m manimcue.cue nie-ma-takiej                 # kryt. 3: log, scena zyje
uv run python -m manimcue.cue sweep                         # 6 s animacji...
uv run python -m manimcue.cue --mode together rotate pulse  # ...w jej trakcie: kryt. 5
```

Kryterium 1: między komendami okno ma reagować — przesuwanie klawiszami `d`/`f`/`z`,
zmiana rozmiaru.
Kryterium 6: klient rozłącza się sam po każdej komendzie i scena to przeżywa; zamknięcie
**okna** kończy scenę przez `EndScene`, czyli bez traceback w terminalu A.
Kryterium 8: w bezczynności proces `manimgl` ma zajmować niewiele CPU (Menedżer zadań).

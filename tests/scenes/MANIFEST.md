# Manifest korpusu scen testowych

Korpus leży w `tests/scenes/` i jest pisany pod testy z `tests/test_scene_corpus.py`
(statyczne i prerender F1) oraz `tests/test_live_corpus.py` (akceptacja live F2).

Zasady (D22 w `SPEC.md`):
- **Scena poprawna** — docelowo działa. Brakująca funkcja z ustalonym API dostaje
  `xfail(strict=True, raises=..., reason="F<n>: ...")` i import modułu wewnątrz testu.
  Po implementacji xfail się zdejmuje; treść testu zostaje.
- **Scena negatywna** — sukcesem jest czytelna diagnoza. To zwykłe zielone testy z
  `pytest.raises`, bez xfail.
- **Zapowiedź** — funkcja bez ustalonego API. Jest tylko wpis tutaj, bez pustego testu.
- **Brak GPU albo TeX** — jawny skip środowiskowy (znaczniki `gpu`, `tex`), nie wada
  implementacji.

Uruchomienie:

```
uv run pytest -q -p no:cacheprovider -W ignore tests/test_scene_corpus.py tests/test_live_corpus.py -rxX
uv run pytest -q -p no:cacheprovider -W ignore -m gpu      # tylko testy z GL
uv run pytest -q -p no:cacheprovider -W ignore -m "not gpu" # bez okna i GPU
```

Legenda statusu: **zielony** — przechodzi dziś; **xfail F<n>** — czeka na fazę n;
**bez kodu** — tylko zapowiedź.

## Sceny live (manimgl) — `tests/scenes/live_gl.py`

| Scena | Faza | Rodzaj | Co sprawdza | Status |
|---|---|---|---|---|
| `LiveGLFirstFrame` | F2 | poprawna | pierwsza klatka 960×540, `boundary`, czerwony w środku, czarny w rogu | zielony |
| `LiveGLCorners` | F2 | poprawna | orientacja: cztery narożniki w kolorach czerwony/zielony/niebieski/biały | zielony |
| `LiveGLMoveFiveSeconds` | F2 | poprawna | cue `move` trwa 4.9–5.2 s; klatki pośrednie w ruchu; koniec w x = 4 | zielony |
| `LiveGLInterruptTwoPlays` | F2 | poprawna | przerwanie w połowie dwóch `play`: `CUE_DONE` < 1 s, klatka graniczna w x = 4 | zielony |
| `LiveGLAddRemoveBack` | F2 | poprawna | `FadeOut`/`FadeIn` w cue; `back` przywraca czerwony, usuwa niebieski | zielony |
| `LiveGLUpdaterWait` | F2 | poprawna | updater działa w czasie `wait` cue: kropka w x ≈ -1 po 2 s | zielony |
| `LiveGLStaticWait` | F2 | poprawna | samo `wait(1.5)` trwa 1.4–1.7 s | zielony |
| `LiveGLIdleUpdater` | F2 | poprawna | updatery zamrożone między cue: kropka stoi w x = -3 | zielony |
| `LiveGLLoopBoundary` | F2 | poprawna | pętla cue kończy się na granicy powtórzenia (narożnik w 90° wielokrotności) | zielony |
| `LiveGLThreeD` | F2 | poprawna | kamera 3D: `increment_theta` zmienia widok sześcianu (> 1% pikseli) | zielony |
| `LiveGLTex` | F2 | poprawna | wzór TeX renderuje się w środku (znacznik `tex`) | zielony z TeX; skip, gdy kompilacja manimgl pada |
| `LiveGLSlowBuild` | F2 | poprawna | READY nie wcześniej niż 3 s po starcie; `poll`/`try_read_frame` < 50 ms w trakcie | zielony |
| `LiveGLCueRaises` | F2 | negatywna | wyjątek w cue daje `ERROR` z treścią „boom from cue”, stan `error` | zielony |
| `LiveGLBuildRaises` | F2 | negatywna | wyjątek w budowaniu nie daje READY; `ERROR` z „boom from build” | zielony |

Po F2 xfaile zdjęte, także z dwóch scen negatywnych — rozbieżność z D22 rozwiązana.

## Sceny prerender (F1) — `tests/scenes/prerender_ce.py`, `prerender_gl.py`

| Scena | Faza | Rodzaj | Co sprawdza | Status |
|---|---|---|---|---|
| `PrerenderCETwoSlides` | F1 | poprawna | `manim-cue render` CE: JSON z dwoma slajdami i notatkami, klipy czytelne przez `av` | zielony |
| `PrerenderGLTwoSlides` | F1 | poprawna | to samo dla manimgl (`render --GL`); wymaga GPU (znacznik `gpu`) | zielony (GPU) |

## Zapowiedzi bez kodu

| Scena | Faza | Rodzaj | Co sprawdza | Status |
|---|---|---|---|---|
| `LiveLayerFocus` | F4 | zapowiedź | fokus warstwy live w playerze | bez kodu |
| `LayerComposition` | F3/F5 | zapowiedź | kompozycja warstw o równej długości | bez kodu |
| `LayerStartPause` | F5 | zapowiedź | start i pauza warstw razem (D17) | bez kodu |
| `LayerUnequalDuration` | F5 | zapowiedź, negatywna | nierówne efektywne długości warstw są odrzucane z diagnozą | bez kodu |
| `SceneViewFrames` | F6a | zapowiedź | klatki sceny jako źródło widoku | bez kodu |
| `SceneViewStepping` | F6b | zapowiedź | krokowanie sceny jako źródło widoku | bez kodu |
| `LiveCECairo` | F7 | zapowiedź | scena live w Manim CE, renderer cairo | bez kodu |
| `LiveCEOpenGL` | F7 | zapowiedź | scena live w Manim CE, renderer OpenGL | bez kodu |

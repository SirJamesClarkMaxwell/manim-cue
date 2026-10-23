# F5i — PoC playera w ImGui: jeden kod na PC i w przeglądarce

Data: 2026-10-23. Powód: [kryterium 8 fazy 5](../../reports/REPORT-f5-crit8.md) — `QGraphicsVideoItem`
w Qt 6 maluje wideo na CPU (`QVideoFrame::map/toImage`), baza + 2–3 klipy 1080p60 z Info zawieszają
player także w samym Qt. Prelegent chce rozwiązania, które działa tak samo w przeglądarce, i wybrał ImGui
w Pythonie (bez C++).

## Wybór wiązania ImGui

| Wiązanie | Dear ImGui | Python 3.13 (Windows) | Przeglądarka | Uwagi |
|---|---|---|---|---|
| [pyimgui](https://github.com/pyimgui/pyimgui) | 1.82 (2021) | brak kół (ostatnie: 3.11, 2023) | nie | Cython, ręczne wiązania, bez dockingu i multi-viewport; README samo odsyła do alternatyw |
| [slimgui](https://github.com/nurpax/slimgui) | 1.92.9b | tak (abi3) | nie | nanobind, typowania, GLFW/pyglet; brak Pyodide = brak jednego kodu z webem |
| **[imgui-bundle](https://github.com/pthom/imgui_bundle) 1.93.0** | 1.92+ (2026-10-21) | tak | **tak** (koło `pyemscripten_2026_0` na PyPI, Pyodide 314) | `hello_imgui.run` podmieniany w Pyodide na pętlę `requestAnimationFrame`; most `imgui_bundle.webgl.register_texture` |

Wybrano **imgui-bundle**: jedyne wiązanie, w którym ten sam kod Pythona działa na PC i w przeglądarce.
Prelegent zgłosił, że imgui-bundle „nie ma wszystkich funkcji” — PoC używa tylko rdzenia ImGui
(okna, `ImDrawList.add_image`, klawisze), który jest kompletny; brakujące funkcje trzeba nazwać, żeby je
sprawdzić przed kontraktem.

## Architektura

- `stage.py` — **wspólny kod**: układ (prostokąty `Rect` manim-cue, dopasowanie 16:9), wspólny zegar
  D17 (start, gdy wszystkie źródła mają pierwszą klatkę; pauza razem), rysowanie bazy, klipów, live
  i obwódki, okno Info (notatki, bieżący slajd, podgląd następnego), metryki. Nie importuje nic z platformy.
- `sources_desktop.py` — PC: `VideoSource` (PyAV, wątki FFmpeg, klatka = floor(t · fps), pętla przez seek,
  `glTexSubImage2D`) i `LiveSource` (prawdziwy `LiveSession` + pamięć współdzielona, bez zmian w `src/`).
- `sources_web.py` — przeglądarka: `HtmlVideoSource` (`<video>` dekodowane sprzętowo przez przeglądarkę,
  `texImage2D(video)` GPU→GPU, tekstura zarejestrowana mostem `imgui_bundle.webgl`).
- `desktop.py`, `web_main.py` — cienkie punkty wejścia (budują slajdy z odpowiednich źródeł).
  `web/index.html` ładuje Pyodide 314.0.7 i imgui-bundle 1.93.0 z PyPI. `serve.py` — serwer (Range dla
  `<video>`, POST metryk), uruchamia Edge/Chrome. `drive_web.py` — przeklikanie przez Playwright.
- Jeden wątek kodu aplikacji na proces (pętla ImGui); FFmpeg i przeglądarka dekodują we własnych wątkach.

Ta sama scena (baza + N klipów + live + Info z podglądem = 2·(1+N) dekoderów) co w pomiarze Qt.

## Wyniki (RTX 4060, i7-13700KF, 1080p60, Info widoczne, 20 s po 3 s rozgrzewki)

**Ekran był zablokowany** (LockApp/LogonUI) — vsync nie ograniczał renderu, a Edge z oknem wstrzymuje
rysowanie zablokowanej strony; dlatego web mierzono headless (na GPU: ANGLE D3D11 RTX 4060).
Liczby to wgrania nowych klatek do tekstur i klatki renderu, nie fizyczne wyświetlenie.

| Wariant | N | Wideo [kl./s] (wszystkie strumienie) | p95 / max [ms] | Live [kl./s] | Render [kl./s] | CPU [% rdzenia] |
|---|---|---|---|---|---|---|
| Qt (obecny, okno, sonda pikselowa) | 1 | baza 6,4 · klip 19,5 | 400 / 634 | 34 | — | 135 |
| Qt (obecny) | 2, 3 | **zawieszenie** | — | — | — | — |
| ImGui PC | 1 | 59,5 | 17,4 / 60 | 59,9 | 1174 | 194 |
| ImGui PC | 2 | 58,7 | 17,4 / 80 | 59,1 | 830 | 302 |
| ImGui PC | 3 | 58,1 | 18,9 / 106 | 58,3 | 208 | 352 |
| ImGui web (headless) | 1 | 49–56 | 35,8 / 53 | — | 57 | — |
| ImGui web (headless) | 2 | 54–56 | 34,1 / 84 | — | 57 | — |
| ImGui web (headless) | 3 | 48–56 | 36,2 / 105 | — | 56 | — |

Web: przeglądarka zgłosiła 9 % odrzuconych klatek przy N=3 (1023 z 11014, `getVideoPlaybackQuality`),
p95 ~35 ms to co druga klatka przy renderze ~57 kl./s w headless. CPU na PC to głównie programowe
dekodowanie H.264 w wątkach FFmpeg (8 strumieni 1080p60). Surowe dane: `results/*.json`.

**Wniosek:** ImGui usuwa przyczynę zawieszenia (wideo nie wraca z GPU na CPU w wątku GUI) i ten sam
`stage.py` działa w obu środowiskach. Qt przy N=1 nie osiągał 60 kl./s, ImGui przy N=3 trzyma ~58.

## Ograniczenia i następne kroki

- Live w przeglądarce: w PoC tylko miejsce na panel. Następny krok: klatki RGBA z workera przez WebSocket
  do tekstury (tryb interaktywny) i nagrany przebieg cue (tryb domyślny) — zgodnie z taskiem finalnym.
- Dwa monitory: na PC Info da się wyciągnąć z okna (multi-viewport, `enable_viewports`); w przeglądarce
  jedno płótno — drugie okno to druga strona z synchronizacją (`BroadcastChannel`).
- Dekodowanie sprzętowe na PC (PyAV `hwaccel` d3d11va) obniżyłoby CPU; nie sprawdzano.
- Vsync i rzeczywiste wyświetlanie: powtórzyć przy odblokowanym ekranie (komendy niżej).
- Fork manim-slides: zostają render, deck JSON, slajdy, `next_slide`, workery live i checkpointy 5g;
  do przepisania kompozycja, Info, klawisze, fokus D20, gesty kamery D28 — kontrakt i runda recenzji przed
  przebudową.

## Uruchomienie

```powershell
# PC (prawdziwe okno); bez --output JSON na stdout
uv run --frozen --with imgui-bundle==1.93.0 --with pyopengl python experiments/f5i_imgui/desktop.py --clips 3
# Przeglądarka z oknem (Edge/Chrome --app); --headless bez okna
uv run --frozen python experiments/f5i_imgui/serve.py --clips 3
# Przeklikanie Playwright (Edge zainstalowany w systemie, bez pobierania przeglądarki)
uv run --frozen --with playwright python experiments/f5i_imgui/drive_web.py --clips 3 --headed --screenshot shot.png
# Testy: układ, statystyki, dymne PC i web (headless)
uv run --frozen --with imgui-bundle==1.93.0 --with pyopengl python -m pytest experiments/f5i_imgui -q -p no:cacheprovider
```

Filmy testowe renderuje CE raz do `.tmp/f5i-media/` (te same co `examples/measure_clips.py`).
Spacja pauzuje bazę i klipy (live działa dalej), strzałki zmieniają slajd.

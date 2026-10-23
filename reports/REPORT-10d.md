# 10d — etap 1 (zadania 1–5)

Repo: `develop`, baza `ed556cb`, 2026-10-23. Kontrakt: PLAN 10d, SPEC D45–D48,
REVIEW-LOG rundy 22–25. Bez commita. Wyjściowe zmiany `pyproject.toml` i `uv.lock`
pozostawione bez ingerencji. Zadania 6–7 i odbiór okienny nie należą do tego wykonania.

Środowisko: `UV_OFFLINE=1`, `UV_CACHE_DIR=.cache/uv`, `TMP=TEMP=.tmp`,
`QT_QPA_PLATFORM=offscreen`, `uv run --frozen`. Bez pełnego pytest, xdist i okien GPU.

## Zadanie 1 — granice cue — wykonane

- `src/manimcue/live_transport.py`: opt-in `step`, FIFO, wynik i status skorelowany
  z żądaniem; granica kursora sprawdzana podczas wykonania; publikacja granicy także
  przy start/end, heartbeat tylko podczas postępu cue/wait, stare next/back zachowane.
- `src/manimcue/player/live.py`: dwa kroki maksymalnie (wykonywany i oczekujący),
  korelacja socket/entry, monotoniczne numery uwzględniające checkpointy, watchdog
  postępu i nieodnawialny deadline przerwania; wynik czeka na klatkę/zasób/ACK.
- `src/manimcue/player/input.py`: repeat NEXT/PREVIOUS konsumowany także po oddaniu fokusu.
- `src/manimcue/player/app.py`: jeden zwykły reducer effect po potwierdzonej granicy.
- `tests/test_live_scene.py`, `tests/test_live_ce.py`: pusta sekwencja, start/end,
  rzeczywisty transport CE bez okna.
- `tests/test_imgui_input.py`, `tests/test_imgui_live.py`: repeat, korelacja i późny wynik,
  wynik przed/po klatce, ACK przed nawigacją, rezerwacja, długie cue/pętle i przerwanie.

Końcowy zestaw: 105 passed, 4 deselected (GPU), 89,35 s.
Po uszczelnieniu odmowy odnawiania już wygasłego deadline'u: 46 passed, 0,72 s
(`test_imgui_live.py test_live_scene.py -m 'not gpu'`). Ruff check i format --check:
8 zmienionych plików zielone. Czas pracy: około 12 min, w tym testy; przegląd Claude
i oczekiwanie na człowieka: 0 min. Limit 12 h nieprzekroczony.
Odstępstwa semantyczne: brak. Qt zachowuje wyjątek D45.
Do okna Claude: przytrzymanie strzałek na start/end, drugi press podczas LOOPS,
granice podczas reverse oraz powrót do trwałego live przez Previous/V/R.

## Zadanie 2 — Info — wykonane

- `player/info.py`: dwie kolumny 60/40, zegar, timer z pauzą/restartem,
  przewijane notatki A−/A+, pusty następny podgląd, pasek przycisków wszystkich slajdów.
- `player/state.py`: sesyjny timer i rozmiar notatek 24 px.
- `player/controller.py`: no-op bieżącego start_at po normalizacji indeksów.
- `player/app.py`: akcje Info i czas prelegenta niezależny od zegara mediów.
- `player/desktop.py`: wykonanie akcji zwróconych przez kontrolki Info.
- `player/live.py`: odcięcie zasobów starego restore przy start_at, sprzątanie liczników
  zakończonych socketów; zgodny sąsiad zachowuje sesję, dalszy cel uruchamia zimną.
- `live_entry.py`: odcięcie stosu i oczekujących operacji, nowe checkpointy bez
  poprzednika, zachowana generacja/liczniki; późny RESTORE_START ignorowany.
- `test_imgui_info.py`, `test_imgui_navigation.py`, `test_imgui_live_checkpoint.py`,
  nowy `test_live_entry.py`: układ bez okna, timer, skala, bariera/no-op, skoki i stare statusy.

Testy: `tests/test_imgui_info.py tests/test_imgui_navigation.py
tests/test_imgui_live_checkpoint.py tests/test_live_entry.py tests/test_imgui_cli.py
-m 'not gpu'`: **39 passed, 4 deselected, 0,42 s**. Ruff check i format --check:
11 zmienionych plików zielone. Czas: około 3 min; przegląd/oczekiwanie 0 min.
Odstępstwa semantyczne: brak. Do okna: proporcje kolumn, przewijanie, DPI, czytelność
24 px, klawiatura w obu oknach, kontrolki nie zmieniają fokusu live.

## Zadanie 3 — miniatury — wykonane

- `player/info.py`: obrazy w poziomym pasku, numer i wyróżnienie bieżącego;
  zamawianie widocznych pozycji plus po jednej obok.
- `player/app.py`: request_thumbnail, obsługa widoczności/decku/shutdown,
  niższy priorytet ekstrakcji od sceny i preview, snapshot liczników i zużycia cache.
- `player/decoder_worker.py`: statyczna kompozycja t=0 z normalnych plików/thumbnail,
  live wyłącznie zapisany obraz; raster maks. 256×144, alfa i geometria stage;
  osobny worker przekazuje mały deskryptor SHM i czeka na potwierdzenie kopii.
- `player/sources_av.py`: jeden job także podczas kończenia, odrzucanie starego decku,
  nieblokujący reap przed kolejnym startem, LRU 64/16 MiB CPU+GPU z rezerwą roboczą,
  osobne liczniki scena/preview/miniatura/bezczynne/kończące/suma.
  Istniejący zapas czterech bezczynnych dekoderów i show_at zachowane.
- `test_imgui_info.py`, `test_imgui_sources.py`: lazy 24 pozycje, ukryte Info,
  anulowanie z opóźnionym exit, limity LRU, kompozycja alfa, prawdziwy spawn ekstrakcji,
  równoczesne cztery źródła sceny + preview + miniatura + zapas.

Testy: `tests/test_imgui_info.py tests/test_imgui_sources.py tests/test_imgui_cli.py
-m 'not gpu'`: **34 passed, 2,60 s**. Ruff check i format --check: 6 plików zielone.
Czas: około 9 min; przegląd/oczekiwanie 0 min. Odstępstwa semantyczne: brak.
Rachunek cache obejmuje owned RGBA, teksturę i konserwatywną rezerwę gotowych rastrów;
RSS bibliotek dekodujących i rzeczywisty VRAM wymagają pomiaru Claude.
Do okna: 24 slajdy, szybkie przewijanie i zmiana decku podczas ekstrakcji,
alfa/proporcje, brak zastoju sceny/preview, liczniki także podczas anulowania.

## Zadanie 4 — matematyka — wykonane

- `player/notes_math.py` (nowy adapter PC): raster MicroTeX po lokalnej inicjalizacji,
  fallback mathtext/Agg bez subprocessu TeX; baseline i jawny błąd ze źródłem.
  Cache kluczowany treścią/stylem/rozmiarem/DPI/kolorem/backendem, 128/16 MiB,
  maks. 4096 znaków i 2048×2048; rachunek uwzględnia raster, GPU i kopię roboczą.
  Kod/fenced code i escaped dollar pozostają Markdownem. Natywne formuły są
  sprawdzane przed przekazaniem do Markdown; eksmisja unieważnia natywny cache tekstur.
- `player/info.py`: wstrzyknięty renderer notatek, bez importu matplotlib w shared UI.
- `player/desktop.py`: with_latex w obu opcjach, adapter i zwalnianie po draw data;
  merge Inconsolata do Roboto zachowany.
- `test_imgui_info.py`: has_latex po init, prawdziwy raster offline MicroTeX,
  inline/display/rozmiary/DPI/baseline, błędne i nadmiarowe wzory, fallback Agg,
  LRU, rysowanie fallbacku bez okna, opcje LaTeX i merge strzałek.

Testy: `tests/test_imgui_info.py tests/test_imgui_shared_imports.py
tests/test_imgui_cli.py -k 'not pyodide'`: **25 passed, 1 deselected (Pyodide),
0,78 s**. Ruff check i format --check: 4 pliki zielone. Czas około 7 min;
przegląd/oczekiwanie 0 min. Odstępstwa semantyczne: brak.
Do okna: natywny upload, inline baseline/display, błędny wzór, A−/A+, DPI 100/150/200%,
strzałki ←→ w Roboto po zmianie rozmiaru i przeniesieniu Info między monitorami.

## Zadanie 5 — gesty obu playerów — wykonane

- `player/input.py`: wspólna macierz MMB/Shift/Alt, press wymagający istniejącego
  fokusu, capture/release/anulowanie, wheel i reset tylko nad aktywnym kontenerem,
  wieloprzyciskowe kombinacje bez gestu.
- `player/live.py`: normalizacja logicznych delt, Alt+RMB −20×dy/h, zero-size/no-op CE;
  anulowanie oczekujących kroków i nawigacji po ACK przy zmianie fokusu.
- `player/desktop.py`: zbieranie trzech przycisków, trwały capture poza hover,
  czyszczenie przy zmianie entry/fokusu/rezerwacji i dezaktywacji aplikacji.
- `composition.py`: czteropolowy pointer_dragged, press jako początek capture,
  wheel angleDelta/120 lub pixelDelta/40, identyfikacja kontenera pod wheel.
- `live_layers.py`: ta sama macierz i normalizacja Qt, capture do release,
  rezerwacja/fokus/zerowy kontener/CE, LMB bez obrotu, reset bez zmiany protokołu.
- `test_imgui_input.py`: parametryczna macierz Qt/ImGui na atrapach sesji,
  focus/capture/release/rezerwacja/multi-button i niezmienność DPI/fps.
- `test_live_layers.py`: dwie nowe próby bez GPU, sygnał Qt i jednostki wheel;
  istniejące 14 testów GPU oznaczone indywidualnie zamiast znacznika całego modułu,
  próba obrotu dostosowana do MMB po nadaniu fokusu.

Testy: `tests/test_imgui_input.py tests/test_live_layers.py tests/test_imgui_cli.py
tests/test_imgui_live.py -m 'not gpu'`: **59 passed, 14 deselected, 0,66 s**.
Ruff check i format --check: 7 plików zielone. Czas około 8 min;
przegląd/oczekiwanie 0 min. Odstępstwa semantyczne: brak.
Do okna: MMB/Shift+MMB oraz wszystkie skróty Alt, capture poza kontenerem,
zmiana aplikacji/entry/rezerwacja, zoom touchpada i kółka, DPI, reset do granicy,
niezmieniona obsługa kamery w historii i brak ruchu kamery CE.

## Dokumentacja i zakres

`README.md` oraz `docs/api.md` zaktualizowane po angielsku zgodnie z osobnym
poleceniem użytkownika: sterowanie obu playerów, wyjątek Qt D45, Info/timer/notatki,
miniatury i lokalna historia po skoku, matematyka i limity. Bez zmian PLAN/SPEC/REVIEW-LOG.
Zadania 6–7 **niezaczęte**: brak puli live, globalnego ProcessBudget i prefetcha N+1.
Istniejąca pula plików, show_at, wstrzymana kompozycja, tekstury w miejscu,
scrollbar Info i ustawienie shadow_window=False zachowane. Bez zmian zależności.

Wspólna regresja zadań 1–5: **181 passed, 19 deselected, 92,24 s**. Polecenie:

```powershell
uv run --frozen pytest -q -p no:cacheprovider tests/test_live_scene.py tests/test_live_ce.py tests/test_imgui_input.py tests/test_imgui_live.py tests/test_imgui_live_checkpoint.py tests/test_imgui_info.py tests/test_imgui_navigation.py tests/test_live_entry.py tests/test_imgui_sources.py tests/test_live_layers.py tests/test_imgui_cli.py tests/test_imgui_shared_imports.py -m 'not gpu' -k 'not pyodide'
```

Końcowe ruff check oraz ruff format --check: **24 własne pliki Python zielone**;
git diff --check bez błędów białych znaków. Ostrzeżenia pytest: dwa istniejące
ostrzeżenia zależności (pkg_resources i PyGLM). Łączny czas pracy około 40 min,
w tym testy; żaden limit 2× zadania nie został przekroczony.

W czasie wykonania zewnętrznie zmieniły się `pyproject.toml`, `uv.lock` oraz
`tests/conftest.py` (zniknął xdist, dodano znacznik slow i domyślne pomijanie).
Nie dokonywałem tych zmian ani ich nie cofałem. Końcowy lint/format obejmuje wyłącznie
własne pliki, bez conftest; jawne `-m 'not gpu'` we wspólnej regresji zastępuje
domyślny filtr znaczników. To obserwacja równoległej pracy, nie odstępstwo kontraktu.

Żaden test GPU/Pyodide ani pełny pytest nie był uruchamiany. Odbiór 10a/11 i 10d/8
pozostaje zadaniem Claude; poniższe komendy nie są dowodem wykonania odbioru.

## Komendy dla Claude — nieuruchomione

PowerShell, repo jako cwd; odblokowany ekran. Do okien usunąć offscreen. Indeksy
monitorów w bramce dostosować do obecnego układu (poniżej dwa monitory 0 i 1).

```powershell
$env:UV_OFFLINE = '1'
$env:UV_CACHE_DIR = "$PWD/.cache/uv"
$env:TMP = "$PWD/.tmp"
$env:TEMP = "$PWD/.tmp"
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
uv run --frozen python experiments/f10a_gate/windows.py --main-monitor 0 --info-monitor 1 --output .tmp/10d-windows.json
uv run --frozen manim-cue present Demo --player imgui --show-info-window
uv run --frozen manim-cue present Demo --player qt --show-info-window
```

Przygotowanie decku 24 slajdów z bazą i trzema ruchomymi klipami (normalne pliki
z obecnego Demo, bez nowego renderu i bez modyfikacji źródłowego JSON):

```powershell
@'
from pathlib import Path
from manimcue.slides.config import ClipLayer, PresentationConfig
deck = PresentationConfig.from_file(Path('slides/Demo.json'))
base = deck.slides[0]
clip = next(layer for slide in deck.slides for layer in slide.layers if isinstance(layer, ClipLayer))
deck.slides = [base.model_copy(deep=True, update={
    'layers': [clip.model_copy(deep=True, update={'rect': (0.02 + j * 0.32, 0.1, 0.3, 0.4), 'loop': True}) for j in range(3)],
    'notes': f'Load {i + 1}: arrows ←→; ' + r'inline $x^2$ and display $$\frac{1}{2}$$',
}) for i in range(24)]
deck.to_file(Path('.tmp/Load24.json'))
PresentationConfig.from_file(Path('.tmp/Load24.json'))
'@ | uv run --frozen python -
uv run --frozen manim-cue present Load24 --folder .tmp --player imgui --show-info-window
```

W Demo sprawdzić GL oraz CE, granice pełnej sekwencji (w tym pustej), LOOPS i dwa
fizyczne naciśnięcia, rezerwację, restore w locie i skok miniaturą, potem Previous/V/R.
W Load24 sprawdzić szybkie przewijanie, widoczność/ukrycie Info, liczniki dzieci,
opóźniony exit, powtarzane skoki, matematykę i oba DPI. W Qt i ImGui wszystkie gesty
MMB/Alt, utratę fokusu i capture poza kontenerem. Zweryfikować obrazy i płynność,
nie zaliczać bramki wyłącznie na podstawie wyniku testów logiki.

```powershell
uv run --frozen pytest -q -p no:cacheprovider tests/test_imgui_windows_gate.py tests/test_live_layers.py tests/test_imgui_live_checkpoint.py -m gpu
uv run --frozen pytest -q -p no:cacheprovider tests/test_imgui_shared_imports.py::test_pyodide_shared_imports
# Pełny odbiór po osobnym etapie 6–7, z uwzględnieniem obecnego filtra slow:
uv run --frozen pytest -q -p no:cacheprovider -m ''
```

Pomiar D48 i pełny odbiór 10d/8 dopiero po zadaniach 6–7. Nie przygotowano
nieistniejącej instrumentacji ani nie zaliczono benchmarku na podstawie samego READY.

## Poprawki po recenzji

2026-10-24, nadal `develop`, bez commita. Ustalenie 8 pominięte zgodnie z poleceniem:
wcześniejsze README/docs i raport mają osobne upoważnienie. Zmieniono wyłącznie
pliki z zadań 1–5, ich testy oraz tę sekcję raportu.

| Ustalenie | Zmiana plik:linia | Test |
|---|---|---|
| 1. FIFO kroków | `src/manimcue/live_transport.py:339`: dwa kroki w FIFO bez wykonywanego, jeden z wykonywanym; wspólna reguła także podczas ACK | `tests/test_live_scene.py:109`, `test_step_fifo_one_recv_and_ack_barrier`, oba backendy, dwie komendy w jednym zapisie/odczycie, bariera ACK i odrzucenie nadmiarowego trzeciego kroku |
| 2. Właściciel tekstury po eksmisji | `src/manimcue/player/notes_math.py:33` i `:166`: oznaczenie eksmisji; późniejszy upload takiego rastra trafia do `_retired`, close dopiero po draw data | `tests/test_imgui_info.py:329`, `test_mathtext_evicted_prepared_uploads_are_closed`: trzy klatki po osiem wzorów, cache 16000 B, 24 uploady i dokładnie 24 close |
| 3. Pamięć miniatur | `src/manimcue/player/decoder_worker.py:39`: PIL draft/thumbnail przed RGBA; `:60`: reformat wideo przed ndarray; `src/manimcue/player/sources_av.py:350`: rezerwa dekodowania obok małych buforów i CPU+GPU cache | `tests/test_imgui_sources.py:388`, `:419`, `:481`: JPEG 3840×2160 zmniejszony przed RGBA, PNG ponad budżet jako błąd miniatury, rzeczywiste wideo i mały ndarray, odrzucenie przed decode/spawn |
| 4. Utrata aktywności/fokusu Qt | `src/manimcue/composition.py:248`: filtr zdarzeń aplikacji czyści pointer_button i emituje pointer_released dla FocusOut/WindowDeactivate/ApplicationDeactivate | `tests/test_live_layers.py:515`, `test_qt_event_loss_cancels_capture`: prawdziwe sendEvent przez viewport, po utracie brak dalszego gestu, nowy press ponownie działa |
| 5. D45 rzeczywistą ścieżką | `tests/test_live_scene.py:93`, `tests/test_imgui_live.py:229`: TCP/live_poll/FIFO → rzeczywiste live_publish GL/CE → FrameBuffer → EntryHistory → zasób/ACK → pojedyncze wywołanie zwykłego reducera | `tests/test_imgui_live.py:315`, `:358`, `:442`: postęp >5 s i drugi press podczas LOOPS, watchdog po ustaniu postępu, before(N)/restore przez Previous i reverse, zachowany cursor/undo całej sesji, brak nawigacji przed zasobem/ACK i brak powtórnego efektu |
| 6. Fallback Markdown | `src/manimcue/player/notes_math.py:153`: jawny komentarz ograniczenia, skład pozostawiony zgodnie z dopuszczonym wyjątkiem | `tests/test_imgui_info.py:373`, `test_mathtext_real_markdown_documents_fragment_limit`: prawdziwy imgui_md.render, wzór w pogrubieniu, liście i zawijanym tekście; istniejący test inline/display również korzysta już z prawdziwego renderera/fontów Markdown |
| 7. Metadane granic | `src/manimcue/player/live.py:57`, `:261`, `:324`: usuwanie po ACK także kroku, starego wyniku oraz pending przy zmianie wejścia | `tests/test_imgui_live.py:429`, `test_stale_boundary_metadata_removed`: wynik rzeczywistego kroku po cancel_steps jest ACKowany i usuwany; próby LOOPS/restore sprawdzają pusty boundaries po poprawnych krokach |

Miniatury: do 16 MiB wliczana jest rezerwa 8 MiB na dekodowanie źródła oraz
`(liczba warstw + 8) × 256 × 144 × 4` na małe rastry, canvas, resize/crop, SHM,
kopie odbiornika i upload, obok cache CPU+GPU. Przed odczytem PIL sprawdzany jest
raster po draft z konserwatywnym mnożnikiem 16 B/piksel; wideo przed decode i po
odczycie klatki ma mnożnik 32 B/piksel i jeden wątek dekodera. Przekroczenie
rezerwy lub nadmiarowy raster kompozycji daje jawny błąd całej miniatury.
Duży JPEG może więc przejść dzięki draft, duży PNG bez redukcji dekodera zostaje
odrzucony. To rachunek buforów i konserwatywna rezerwa, nie pomiar ani twardy limit
całego RSS/VRAM bibliotek i kodeków. Wcześniejsze liczniki samych małych rastrów
nie stanowią dowodu odbioru D46; pełne obciążenie nadal wymaga pomiaru w oknie.

Ograniczenie 6 pozostaje: fallback Agg renderuje osobne fragmenty Markdown przy
wzorach, więc nie przenosi stanu pogrubienia, listy ani zawijania przez wzór.
Test z prawdziwym imgui_md dokumentuje ten podział, nie deklaruje poprawnego składu.
Pełna integracja wzorów z parserem Markdown, fontami i układem przekracza około
30 linii; zgodnie z poleceniem nie rozbudowywano fallbacku. Podstawową ścieżką
pozostaje natywny MicroTeX, przekazujący całą notatkę do jednego renderera Markdown.

Końcowe testy wyłącznie dotkniętych w tej poprawce plików:

```powershell
uv run --frozen pytest -q -p no:cacheprovider tests/test_live_scene.py tests/test_imgui_live.py tests/test_imgui_info.py tests/test_imgui_sources.py tests/test_live_layers.py -m 'not gpu'
```

**102 passed, 14 deselected (GPU), 4,18 s**. Dwa istniejące ostrzeżenia zależności:
pkg_resources i PyGLM. Środowisko jak wyżej: offline, lokalny cache/TMP,
QT_QPA_PLATFORM=offscreen. Bez pełnego pytest, bez `-n`, bez testów GPU.
Ruff check i format --check: wszystkie 24 pliki Python obecnego diffu zielone
(w tym 11 plików tej poprawki);
`git diff --check` bez błędów białych znaków. Testy transportu używają rzeczywistej
publikacji obu backendów z kamerą bez GPU i rzeczywistym buforem, bez okna i
bez uruchamiania procesu Manima; czas długich cue jest kontrolowany w teście.
Testy miniatur obejmują także istniejący rzeczywisty spawn ekstrakcji.

Czas poprawek około 30 min; przegląd Claude/oczekiwanie na człowieka: 0 min.
Próba okienna i pomiary RSS/VRAM pozostają niewykonane. Nie wykonano commit,
stash, reset ani checkout; nie zmieniono PLAN/SPEC/REVIEW-LOG ani zależności.

## Przegląd Claude — etap 1

Recenzja adwersaryjna codex (read-only): 2 blokujące, 4 istotne, 2 drobne; Claude potwierdził w kodzie
blokujące 1 (FIFO kroków, `live_transport.py`) i 2 (właściciel tekstur po eksmisji, `notes_math.py`).
Poprawki 1–5 i 7 wyżej; 6 jako ograniczenie fallbacku, 8 odrzucone (dokumentację zlecił Claude).

Zwykły pytest (bez `slow`) po poprawkach: **677 passed, 1 failed, 2 skipped, 54 deselected, 569,66 s**.
Jedyny błąd: `test_live_layers.py::test_gui_path_keeps_up_with_live_frames` — 32,75 fps przy progu 48;
pojedynczo 2× passed, z `test_layers.py` 38 passed. Przed poprawkami ten sam przebieg: 650 passed, 0 failed.
Podejrzany: filtr zdarzeń na całą `QApplication` z poprawki 4 (`composition.py`), wołający Pythona dla każdego
zdarzenia. Jeśli błąd wróci w przebiegach etapu 2 — zamienić na sygnały `applicationStateChanged`
/`focusWindowChanged`.

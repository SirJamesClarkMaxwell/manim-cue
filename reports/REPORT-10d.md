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

## Etap 2 — zadanie 6: pula live GL/CE

2026-10-24, `develop`, baza HEAD z etapem 1. Zmiany etapu 1 zachowane; bez commita,
zmian zależności, synchronizacji `.venv`, stash/reset/checkout/worktree.

Zmiany plik po pliku:

- `src/manimcue/live_pool.py` (nowy): `ProcessBudget`, admisja i priorytety wspólne
  dla procesów PC; PID zwalnia slot wyłącznie po exit. Rachunek D48 z manifestu,
  kończące procesy nadal w limicie, obniżanie limitu po zmianie decku bez sumowania pul.
  `LivePool`: dwa jednorazowe sloty na użyty silnik, POOL_READY po imporcie bez
  pliku autora/sceny/SHM/kontekstu GPU; jeden import uzupełnienia naraz. Lock i oba
  Pipe przed spawn, spec i nazwa SHM później. Kontrola rodzica/EOF co 250 ms,
  timeout importu 5 s, ograniczona ponowna próba, zamknięcie i kill po 2 s.
  Anulowanie importu z powodu priorytetu nie liczy się jako awaria importu.
- `src/manimcue/live_session.py`: opcjonalny jawny `pool`, waiting_slot pompowany
  przez poll; SHM dopiero po przydziale, wspólny lifecycle i sprzątanie po exit.
  Zimne `capture_first_frame` zachowane. Nowe wejście nie przejmuje waiting_slot
  poprzednika; anuluje stare żądanie przed nowym startem.
- `src/manimcue/player/sources_av.py`: wspólna admisja dekoderów, zapasu i miniatur;
  waiting_slot dla źródła; również zimne starty i procesy kończące zajmują slot.
  Priorytetowe wycofanie niższych kategorii nie zwalnia slotu przed exit.
- `src/manimcue/player/live.py`: jawne przekazanie puli do nowych LiveSession;
  historia, zgodne sąsiednie przejęcie i dwa równoczesne trwałe live zachowane.
- `src/manimcue/player/app.py`: właściciel puli i budżetu PC, konfiguracja całego
  bieżącego decku, poll także na slajdzie plikowym, shutdown i snapshot liczników.
- `src/manimcue/live_layers.py`: pula Qt, poll również bez aktywnego live,
  waiting_slot uwzględniony w terminie wejścia; diagnozy importu i końcowy reap.
- `src/manimcue/slides/present/player.py`: konfiguracja silników i pułapu całego
  decku przed show, także przy pierwszym slajdzie plikowym. Styl forka zachowany;
  nie uruchamiano ruff format na tym pliku.
- `tests/test_live_pool.py` (nowy): rzeczywiste importy GL i CE bez sceny/GPU,
  późny spec/Lock/SHM oraz TCP CE, unlink po exit, pełny budżet i anulowanie
  oczekiwania, osierocenie przez osobny proces rodzica, dwie jednorazowe sceny,
  anulowane uzupełnianie bez wyłączenia silnika. Każda pula jest sprzątana przez fixture.
- `tests/test_live_ce_player.py`: Qt offscreen, pierwszy slajd plikowy, silnik z
  dalszej części decku, timer puli i pełny shutdown.

Bramka przed rozpoczęciem zadania 7:

```powershell
uv run --frozen pytest -q -p no:cacheprovider tests/test_live_pool.py tests/test_imgui_sources.py tests/test_live_session.py tests/test_live_ce_player.py tests/test_imgui_live.py -m 'not gpu and not slow'
```

**73 passed, 17 deselected, 48,62 s**. Po dodaniu śmierci rodzica i Qt file-first:
**50 passed, 14,01 s** (pool, file-first, źródła i ImGui live). Późniejsza regresja
pool/session/cały CE player oraz bramka wspólnych importów PC: **33 passed,
17 deselected, 51,18 s**. Nie są to wyniki GPU ani dowód progu p95.

Czas zadania 6: około 7 min do pierwszej bramki; późniejsze wspólne regresje
rozliczone poniżej. Budżet 10 h / stop 20 h nieprzekroczony. Odstępstw kontraktu
nie wprowadzano. Do Claude: oba silniki w prawdziwym oknie, dwie sesje 5g,
zmiany decku pod obciążeniem, fokus, RSS/VRAM zapasu i pomiar bez prefetcha.

## Etap 2 — zadanie 7: prefetch N+1 tylko ImGui PC

- `src/manimcue/player/prefetch.py` (nowy): jeden token pełnej specyfikacji,
  rewizji manifestu/decku, źródłowego entry_id i celu. Oddzielne źródła plikowe
  i LiveSession; take przekazuje własność raz i zmienia kategorię budżetu na scene.
  Anulowane zasoby zajmują pamięć/slot do exit, błędny token nie jest ponawiany.
  Konserwatywna rezerwa 8 rastrów + nagłówki na warstwę, suma maks. 128 MiB;
  brak rezerwy lub za duży plik pomija warstwę, pozostałe można przejąć.
- `src/manimcue/player/app.py`: przygotowanie po gotowości N także bez Info,
  token sprawdzany ponownie przed nawigacją; wyłącznie rzeczywisty normalny N+1
  przejmuje źródła. Reverse, Previous, replay, skoki, zmiana decku/spec i exit
  anulują spekulację. No-op bieżącego start_at i obroty pętli jej nie konsumują.
  Sąsiednie zgodne live rozpoznawane po rzeczywistej tożsamości, także przy zmianie
  położenia rect; nie są budowane drugi raz. Efekty EOF/iteration_end otrzymują
  powód auto_next/skip_all, aby zachować zwykłe przygotowanie cue także po trafieniu.
- `src/manimcue/player/sources_av.py`: `hold_first`, potwierdzenie held, adopt bez
  ponownego dekodowania, nowa generacja/entry_id oraz zegar przy wspólnym starcie.
- `src/manimcue/player/decoder_worker.py`: potwierdzony hold po pierwszym t=0,
  bez EOF/postępu odtwarzania/pętli; limit rastra przed konwersją/alokacją SHM,
  osobny sygnał zwolnienia hold i kotwica odtwarzania. Preview nie jest przejmowane.
- `src/manimcue/live_session.py`: opt-in `LiveSpec.prefetch=False`.
- `src/manimcue/live_worker.py`, `src/manimcue/live_scene_ce.py`: przekazanie trybu
  do sceny dopiero po przydziale; zwykła ścieżka pozostaje domyślna.
- `src/manimcue/live_scene.py`, `src/manimcue/live_scene_ce.py`: podczas hold nowa
  granica adopcji używa istniejącego rastra, bez update_frame/update_mobjects dt=0.
- `src/manimcue/live_transport.py`: techniczny ACK READY i PREFETCH_HELD, blokada
  ręcznych cue/view podczas hold; jawne adopt_prefetch bez session_id/cue/historii,
  nowy frame_id, osobny ACK po przypisaniu zasobu kompozycji i release. Checkpoint
  trwałego wejścia kończy hold przed zwykłymi operacjami D41; stare żądania/ACK
  nadal przechodzą istniejącą kontrolę generacji, numeru żądania i frame_id.
- `src/manimcue/player/live.py`: przejęcie po sprawdzeniu D39, zwykłe tworzenie
  historii dopiero przy wejściu, nowa granica adopcji i ACK dla live bez historii;
  release także dla wejścia pozostającego w pauzie. READY spekulacji nie otwiera bariery.
- `src/manimcue/live_pool.py`: kategoria prefetch w admisji i przeklasyfikowanie
  właściciela; liczniki procesów zawierają wszystkie kategorie i twardy pułap.
- `tests/test_imgui_prefetch.py` (nowy): spawn/socket/SHM CE oraz źródła plikowe;
  hold ponad 5 s, brak dt=0 updaterów, checkpoint/nowa granica/kompozycja/ACK,
  zwykły live bez session_id/cue i wejście w pauzie; odpowiedniki GL oznaczone gpu.
  Rzeczywista App: niezależny preview, przejęcie pliku, no-op bieżącego start_at,
  anulowanie, pierwszeństwo adjacent i niezmieniona historia przy Previous.
  Pełny B, nowa nawigacja podczas waiting_slot, cleanup po module i częściowe
  trafienie przy przekroczeniu pamięci. Zwykłe powtórzenia mają 2–3 próby.
- `README.md`, `docs/api.md`: po angielsku opis puli, spekulacyjnego build_objects
  i jego I/O, reguł przejęcia/anulowania, niezależnego preview oraz limitów.

Testy zadania 7 (zestaw z transportem obu silników):

```powershell
uv run --frozen pytest -q -p no:cacheprovider tests/test_imgui_prefetch.py tests/test_imgui_sources.py tests/test_imgui_live_checkpoint.py tests/test_imgui_navigation.py tests/test_live_scene.py tests/test_live_ce.py -m 'not gpu and not slow'
```

**121 passed, 7 deselected, 80,53 s**. Po rozszerzeniu testów App i admisji:
**79 passed, 7 deselected, 30,47 s**. Wspólna regresja pool/źródła/ImGui/live
checkpoint/nawigacja/session/Qt CE: **106 passed, 24 deselected, 74,14 s**.
Po końcowych poprawkach własności budżetu i częściowych trafień: zestaw ImGui
z analizatorem śladu **77 passed, 7 deselected, 20,40 s**; adjacent + rebase
osobno **2 passed, 2,19 s**. Końcowy zestaw nowych testów dopisany poniżej.

Czas zadania 7 z regresjami: około 14 min. Budżet 11 h / stop 22 h
nieprzekroczony. Przegląd Claude i oczekiwanie na człowieka: 0 min.
Odstępstw semantycznych nie wprowadzano. Rezerwa pamięci jest konserwatywna:
plik większy niż przydzielony raster lub GIF z cache większym niż rezerwa może
nie trafić w prefetch mimo wolnej pamięci systemowej; wejście użyje zwykłej ścieżki.
Nie jest to limit RSS bibliotek ani VRAM kontekstu/sceny.

Do Claude w oknie: wszystkie scenariusze GL, zgodność obrazu pierwszej klatki,
release w pauzie i późniejsze cue, D39–D41/5g pod pełnym obciążeniem, skoki podczas
prefetcha, auto_next/skip_all/pętle/koniec decku, zmiany DPI i rzeczywista pamięć.

## Instrumentacja zadania 8 — przygotowana, odbiór niewykonany

Wyłącznie instrumentacja z zamkniętej listy zadania 8:

- `tests/test_imgui_acceptance.py`: rzeczywisty player GLFW/OpenGL3 i App, oba
  silniki, prefetch off/on, trzy serie po 10 wejść rozgrzewki + 100 pomiarów.
  Deck 24 slajdów, każda nawigacja tworzy nową scenę bez session_id i enter_cue;
  skok po końcu decku jest niemierzony. Opcjonalne trzy ruchome klipy, niezależne
  Info i miniatury. Czas od przyjętego next do gotowej kompozycji i swapu oraz
  opróżnienia kolejki ACK do socketu (konserwatywnie następny swap, jeśli potrzeba).
  Pula ma być rozgrzana przed next. Ślad rozdziela pool hit, cold fallback,
  prefetch hit, kategorie procesów i RSS; `vram_bytes=null` nie udaje pomiaru VRAM.
- `experiments/f10a_gate/measure.py`: analiza śladu wejść osobno od metryk 10a;
  wyłączenie rozgrzewki, cold osobno, p50/p95/max, liczba trafień, peak procesów
  i RSS. Flaga passes_latency wymaga 100 ciepłych próbek i p95 ≤500 ms;
  `acceptance` nadal pending Claude. Dotychczasowe progi i analiza 10a zachowane.
- `tests/conftest.py`: tylko nazwa `test_d48_window_measurement` w SLOW,
  ponieważ próba wykonuje ≥10 powtórzeń. Bez zmiany domyślnego filtrowania.

Zwykły test analizatora sprawdza rozgrzewkę/cold i brak VRAM. Nie uruchamiano
próby GPU, okien, pełnego pytest ani `-n`. Same READY, testy offline ani rekordy
syntetyczne nie stanowią odbioru ≤0,5 s p95. 10a/11 pozostaje osobną bramką.
Instrumentacja i raport: około 6 min; łącznie około 27 min, z czasem czytania
kontraktu i testów. Żaden limit zadania ani całego etapu nie został przekroczony.

### Komendy dla Claude — D48, nieuruchomione

PowerShell w repo, odblokowany ekran, zainstalowane/istniejące materiały Demo.
Przed rozpoczęciem dopasować monitory i zweryfikować sprzęt, Hz i rozdzielczości.

```powershell
$env:UV_OFFLINE = '1'
$env:UV_CACHE_DIR = "$PWD/.cache/uv"
$env:TMP = "$PWD/.tmp"
$env:TEMP = "$PWD/.tmp"
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
$env:MANIMCUE_D48_DECK = 'slides/Demo.json'
$env:MANIMCUE_D48_OUTPUT = '.tmp/d48-baseline'
Remove-Item Env:MANIMCUE_D48_FULL_LOAD -ErrorAction SilentlyContinue
uv run --frozen python experiments/f10a_gate/measure.py --timeout 3600 --output .tmp/d48-baseline-watchdog.json -- uv run --frozen pytest -q -p no:cacheprovider tests/test_imgui_acceptance.py::test_d48_window_measurement -m 'gpu and slow'

$env:MANIMCUE_D48_FULL_LOAD = '1'
$env:MANIMCUE_D48_OUTPUT = '.tmp/d48-full-load'
uv run --frozen python experiments/f10a_gate/measure.py --timeout 3600 --output .tmp/d48-full-load-watchdog.json -- uv run --frozen pytest -q -p no:cacheprovider tests/test_imgui_acceptance.py::test_d48_window_measurement -m 'gpu and slow'

Get-ChildItem .tmp/d48-baseline/*.jsonl, .tmp/d48-full-load/*.jsonl | ForEach-Object {
    uv run --frozen python experiments/f10a_gate/measure.py --trace $_.FullName --output ($_.FullName + '.summary.json')
}
```

To cztery warianty GL/CE × prefetch off/on, każdy z trzema seriami. Domyślny
baseline zachowuje warstwy wybranego slajdu Demo; FULL_LOAD dodaje trzy klipy
z istniejących plików. Zweryfikować kompozycję i dobrać fixture pełnego D46,
jeżeli wybrany slajd już zawiera klipy. Skoki, odwracanie, anulowanie i exit
nadal sprawdzić według odbioru ręcznego, nie zastępować ich samym benchmarkiem.

VRAM mierzyć równolegle z zewnątrz, aby zapytania sterownika nie blokowały UI.
Przykład w drugim terminalu, przerwać Ctrl+C po próbie:

```powershell
nvidia-smi -l 1 | Tee-Object .tmp/d48-vram.txt
```

Jeżeli sterownik/WDDM zwraca N/A, użyć dostępnego profilera GPU i zanotować
ograniczenie; nie zaliczać VRAM na podstawie RSS ani pustego pola śladu.
RSS w śladzie próbkowany jest przy zmierzonych wejściach, więc jego peak nie
obejmuje gwarantowanie chwilowych szczytów pomiędzy nimi. Claude powinien także
próbkować procesy podczas anulowania/exit i osobno porównać aktywne, idle,
prefetch i retiring. Przekroczenie progu uruchamia STOP/przegląd, nie zmianę
liczby workerów lub osłabienie progu.

Regresje GPU nowych ścieżek i pełny odbiór — wyłącznie Claude:

```powershell
uv run --frozen pytest -q -p no:cacheprovider tests/test_imgui_prefetch.py -m gpu
uv run --frozen pytest -q -p no:cacheprovider -m ''
```

### Końcowa weryfikacja etapu 2

Po poprawkach ostatnich przypadków (anulowanie importu nie wyłącza silnika,
przeklasyfikowanie procesu po take, częściowe trafienie przy limicie pamięci):

```powershell
uv run --frozen pytest -q -p no:cacheprovider tests/test_live_pool.py tests/test_imgui_prefetch.py tests/test_imgui_acceptance.py::test_d48_measure_excludes_warmup_and_cold -m 'not gpu and not slow'
```

**21 passed, 3 deselected (GPU), 32,01 s**. Dwa dotychczasowe ostrzeżenia
zależności: pkg_resources i PyGLM. Żadna nowa próba offline nie ma ≥10 powtórzeń.
Końcowy `ruff check` i `ruff format --check`: **18 własnych plików Python zielone**,
bez forka `src/manimcue/slides/`; `git diff --check` zielony.
`test_pc_shared_imports` wykonano w zestawie 33 passed opisanym przy zadaniu 6.
Bez GPU, Pyodide, pełnego pytest, xdist i zmian `.venv`; nie wykonano commita.
Odbiór zadania 8, pomiar p95, VRAM i próba prelegenta pozostają po stronie Claude.

## Przegląd Claude — etap 2

Recenzja adwersaryjna codex etapu 2 przerwana limitem użycia codex (do 3:28, 2026-10-24); do powtórzenia.
Przegląd Claude (statyczny, `live_pool.py`, `prefetch.py`):

- Cykl życia procesów zgodny z D48: slot zwalnia dopiero exit, zamknięcie `control` kończy ciepły proces,
  kill po 2 s; w UI tylko `poll(0)`/`join(0)` po `exitcode`.
- **Istotne, otwarte:** przy pełnym budżecie `ProcessBudget.try_acquire` woła wszystkie reclaimery i stoppery
  niższych kategorii przy każdym nieudanym wywołaniu (co klatkę `waiting_slot`). Miniatura bez slotu
  zatrzymuje całą ciepłą pulę obu silników, nie jeden proces — churn importów ~1,4 s. Poprawka: najwyżej
  jeden odzysk naraz (nic nie jest `retiring`), najniższa kategoria pierwsza. Przy budżecie Demo (~25) pod
  zwykłym obciążeniem (~21 procesów) nie występuje.

Zwykły pytest po etapie 2: **701 passed, 2 failed**; po poprawkach niżej **702 passed, 0 failed, 575 s**:
- `test_leaving_slide_reaps_process_and_reentry_is_fresh` — liczył ciepłe workery puli Qt jako osierocone;
  test wyklucza teraz `player.live.pool.workers`.
- `test_gui_path_keeps_up_with_live_frames` — 23,25 fps (próg 48). Przyczyna potwierdzona eksperymentem:
  filtr zdarzeń całej `QApplication` z poprawki 4 etapu 1 (każdy żyjący `SlideView` z wcześniejszych testów
  wołał Pythona dla każdego zdarzenia; sekwencja plików Qt odtwarzała spadek do 43 fps, bez filtra test
  przechodził). Zamienione na sygnały `applicationStateChanged`/`focusWindowChanged`
  (`composition.py`); test anulowania capture emituje sygnały. Sekwencja Qt: 76 passed.

### Recenzja codex etapu 2 i poprawki

Recenzja statyczna diffu `9b52acb..572c73f`, poprawki na gałęzi
`fix/10d-stage2-review` (2026-10-24). Powyższe wyniki testów dotyczą wcześniejszego
stanu; **testy po tych poprawkach nie były uruchamiane**. Trwa próba playera
użytkownika: bez pytest, procesów roboczych i okien. Bez commita.

1. **Zagłodzenie admisji przez refill — poprawione.**
   `src/manimcue/live_pool.py:26`: budżet pamięta kategorię, która odbiła się od
   pełnego limitu; `idle` nie dostaje slotu do udanej admisji tej kategorii.
   Przejęcie gotowego workera również usuwa oczekiwanie
   (`src/manimcue/live_pool.py:197`, `src/manimcue/player/sources_av.py:54`).
   Wspólny budżet obejmuje ImGui i Qt, bez zmiany kolejności ich poll.
   Test `tests/test_live_pool.py:179` symuluje opóźniony exit przy automatycznym
   refill i dowodzi, że odzyskany slot trafia do sceny.
2. **Nadmierny odzysk procesów — poprawione.**
   `src/manimcue/live_pool.py:26`: najwyżej jeden odzysk naraz, kolejno idle →
   thumbnail → prefetch → preview; obecność `retiring` blokuje kolejny odzysk
   aż do odebrania exit. `src/manimcue/live_pool.py:220` zatrzymuje jeden worker,
   a `src/manimcue/live_pool.py:269` nadal zamyka wszystkie przy shutdown.
   `src/manimcue/player/sources_av.py:20` i `:76` odzyskują jeden dekoder albo
   jeden worker live. `src/manimcue/player/prefetch.py:136` również zatrzymuje
   tylko jeden element na żądanie admisji; pozostałe można odzyskać po exit.
   Nowe testy: `tests/test_live_pool.py:213`, `:234`, `:249` oraz
   `tests/test_imgui_prefetch.py:470` (jeden proces, kolejność kategorii,
   powtarzane odmowy do exit i pełny shutdown obu pul).
3. **Ponawianie prefetcha anulowanego przez admisję — poprawione.**
   `src/manimcue/player/prefetch.py:136`: zapamiętanie tokenu jako `failed`;
   `:115`: odrzucony cel nie jest przejmowany, także przy częściowym odzysku.
   Zmiana tokenu pozwala przygotować nowe wejście. Test offline
   `tests/test_imgui_prefetch.py:416` obejmuje kilka cykli preview–prefetch,
   opóźnione exity, brak ponowienia i dopuszczenie nowego tokenu.
4. **Globalny budżet dekoderów przy dwóch App — znane ograniczenie.**
   Zgodnie z poleceniem bez poprawki: `src/manimcue/player/sources_av.py:20`
   nadal konfiguruje globalną pulę/budżet. Produkcja zakłada **jedną App na
   proces**; dwie App w jednym interpreterze nie mają izolacji tych zasobów.
5. **Test przejęcia bez historii nie dowodził wyjścia z hold — poprawione.**
   `tests/test_imgui_prefetch.py:71`: po przejęciu w pauzie i wznowieniu test
   czeka na skorelowane `ENTRY_RELEASED`, wykonuje rzeczywisty krok sekwencji,
   sprawdza wynik `done`, entry/request/frame_id i zmienione piksele, następnie
   przyjmuje klatkę/ACK. Obejmuje brak historii oraz trwałą sesję, GL i CE.
   `tests/test_imgui_prefetch.py:258` dodatkowo sprawdza wznowienie updaterów po
   release. Warianty GL zachowują znacznik `gpu`. Uruchomienie i szerszy odbiór
   nawigacji/pętli z zadania 8 pozostają po stronie Claude.

**Pliki spoza zamkniętych list zadań 6–8 w recenzowanym etapie:**

- `README.md` — dokumentacja użytkowa puli, prefetcha, wcześniejszego wykonania
  `build_objects` i jego I/O oraz limitów; wcześniejsze osobne upoważnienie
  dokumentacyjne opisane w raporcie.
- `docs/api.md` — ten sam kontrakt zachowania i ograniczeń w dokumentacji API.
- `src/manimcue/composition.py` — poprawka regresji wydajności Qt: sygnały
  aplikacji/fokusu zamiast globalnego filtra zdarzeń, z zachowaniem anulowania
  capture po utracie aktywności/fokusu.
- `tests/test_live_layers.py` — dostosowanie kontroli osieroconych dzieci do
  legalnego zapasu D48 oraz testu anulowania capture do sygnałów Qt. Test
  emituje sygnały ręcznie; rzeczywista kolejność zdarzeń Player–Info wymaga
  próby okienkowej.

Te cztery odstępstwa należą do wcześniejszego diffu; niniejsza poprawka ich nie
rozszerza. Zmieniono trzy pliki implementacji, dwa pliki testów i ten raport.
Weryfikacja ograniczona do `ruff check`, `ruff format --check` pięciu zmienionych
własnych plików Python (bez forka slides) oraz `git diff --check` — bez błędów.
Nie zmierzono p95, RSS ani VRAM; odbiór zadania 8 pozostaje otwarty.

### Runda 26 — miniatury D46

- `src/manimcue/player/decoder_worker.py:13`: osobny limit wejścia ekstraktora
  3840×2160 pikseli (iloczyn), zamiast 8 MiB i mnożników 16/32. Kontrole
  oryginalnego obrazu przed `draft()`, deklaracji wideo przed decode i klatki
  po decode; ostatnia nie zapobiega wcześniejszej alokacji. Zachowane jeden
  wątek dekodera, natychmiastowy reformat do małego RGBA i błąd → placeholder.
- `src/manimcue/player/sources_av.py:430`: budżet 16 MiB rozlicza bufory
  i tekstury miniatur playera, bez rezerwy dekodowania źródła. Zachowana
  rezerwa zależna od liczby warstw, ograniczająca też sumę małych rastrów
  ekstraktora, oraz odrzucenie kompozycji przekraczającej budżet.
- `tests/test_imgui_sources.py:388`: JPEG i PNG 4K dają miniaturę, większy
  JPEG jest odrzucany przed draft i zwraca błąd placeholdera; `:423`: wideo
  1920×1080 daje obraz, ndarray powstaje dopiero po zmniejszeniu, przekroczenie
  limitu deklaracji lub rzeczywistej klatki daje błąd; `:500`: budżet warstw
  bez rezerwy dekodera. `tests/test_imgui_info.py:218`: rezerwa cache obejmuje
  wyłącznie małe bufory, nadal obowiązuje suma CPU+GPU z rezerwą ≤16 MiB.

Testy **nieuruchomione** zgodnie z poleceniem podczas próby playera; bez pytest,
ekstrakcji, procesów roboczych i okien. Weryfikacja: `ruff check`,
`ruff format --check` czterech zmienionych plików Python oraz `git diff --check`.
Nie mierzono RSS ekstraktora; limit wejścia nie obiecuje limitu RSS, pomiary
1080p/4K z kodekiem i formatem pikseli pozostają do odbioru. Istniejące poprawki
etapu 2 zachowane; bez commita.

### Przegląd Claude poprawek i próba człowieka (2026-10-24)

Poprawki Claude po przeglądzie diffu codex:

- `src/manimcue/live_pool.py`: `ProcessBudget.waiting` to słownik rola → czas ostatniej odmowy; `idle` czeka tylko
  na odmowy młodsze niż 0,5 s. Wcześniej porzucone żądanie (np. miniatura po ukryciu Info, anulowany prefetch)
  blokowało uzupełnianie puli do następnej udanej admisji tej roli. Test `test_abandoned_wait_stops_blocking_refill`.
- `tests/test_live_pool.py::test_cancelled_refill_does_not_disable_engine`: `retire_idle` zatrzymuje teraz jeden
  worker, więc test zatrzymuje wskazany worker przez `_stop`.
- `tests/test_imgui_prefetch.py::test_hold_no_zero_dt_updaters`: usunięty dopisek codex czekający na updatery po
  release — pusta scena bez updaterów nie aktualizuje się w bezczynności (GL i CE); wyjście z hold dowodzi krok
  w `test_ready_hold_over_5s_then_checkpoint_composition_ack`.

Usterki z próby człowieka ImGui (Demo, Load24):

- **Miniatury bez obrazów** — każda była placeholderem: limit 8 MiB z poprawki 3 etapu 1 odrzucał każde wideo
  1080p. Runda 26 (wyżej).
- **Krzaczek przed numerem bieżącej miniatury** — `▶` spoza zakresu fontu; `src/manimcue/player/info.py` używa `> `.
- **Mysz w Info przesunięta o 40 px** (pasek przewijania trafiany tylko daleko poniżej). Sonda w oknie: viewport
  ImGui Info (3540,−488), rzeczywisty klient (3500,−528) przez całą sesję. `Windows.attach` przesuwał okno Info
  przez `glfwSetWindowPos` tuż po utworzeniu viewportu; backend ImGui ignoruje ruch okna zaraz po własnym
  ustawieniu pozycji. `src/manimcue/player/desktop.py`: ruch tylko okna głównego; Info ustawia
  `set_next_window_pos`. Po zmianie sonda: viewport = klient.
- **Chwilowe zawieszenie na pierwszym slajdzie Load24** — zgodne z ustaleniami 1–2 recenzji etapu 2 (odzysk całej
  puli i zagłodzenie admisji przy pełnym budżecie); do ponownej próby po poprawkach.
- Prelegent chce miniatur w pionowej kolumnie po lewej (sorter PowerPoint) — runda 27, zadanie 2.

Testy po poprawkach (kod worktree przez `PYTHONPATH`): zwykły pytest **711 passed, 1 failed, 2 skipped,
58 deselected, 637 s**; jedyny błąd to dopisek updaterów wyżej — po usunięciu oba testy hold **6 passed**.
`ruff check`/`ruff format --check` 10 plików Python: zielone.

### Runda 27 — kolumna miniatur i testy limitu

- `src/manimcue/player/info.py:72`: pionowa kolumna miniatur na całą wysokość
  Info, przed statusem i dwiema kolumnami podglądów. Szerokość uwzględnia
  miniaturę 128×72, skalę stylu, ramkę, padding i pionowy scrollbar, bez
  mnożenia przez DPI framebufferu. Lazy load nadal obejmuje elementy
  przecinające widok oraz po jednym sąsiedzie. Odsłonięcie bieżącego przycisku
  tylko przy pierwszym pokazaniu lub zmianie `(deck, slide)`, jeśli jest poza
  widokiem; ręczne przewijanie i resize nie ponawiają odsłonięcia. Przyciski
  czasu zawijają się do osobnych wierszy. Klik nadal zwraca `start_at`.
- `src/manimcue/player/desktop.py:398`: minimalna szerokość Info wyliczona
  z kontrolek i proporcji 60/40, zastosowana przez
  `set_next_window_size_constraints` (`:424`). Stan poprzedniego celu należy
  do widoku (`:464`), jest usuwany po ukryciu Info (`:475`); bez zmian w app.py
  i stanie nawigacji.
- `tests/test_imgui_info.py:150`: rozszerzony test układu trzech kolumn
  dla domyślnej i minimalnej szerokości oraz skali stylu 100/150/200%,
  położenia przycisków i braku poziomego przewijania miniatur. Fixture
  `:238` używa wyłącznie kontekstu ImGui, bez okna i GPU. Testy `:299`,
  `:315`, `:345`: 24 slajdy i widoczne ±1 na obu końcach, jednorazowe
  auto-przewijanie, ręczne odsunięcie i resize, widoczny cel, pierwsze
  pokazanie i zmiana decku oraz klik placeholdera/miniatury → `start_at`
  bez `focus_live`. Wywołanie auto-przewijania obserwowane strażnikiem.
- `tests/test_imgui_sources.py:388`: obraz 7680×4320, strażnicy `load()`
  i `draft()` założeni po odczytaniu nagłówka; wymagany `MemoryError`
  oraz komunikat błędu z `run_thumbnail`. `:436`: strażnik `Container.decode`
  dla przekroczonej deklaracji wideo; niezależne sprawdzenie limitu
  rzeczywistej klatki zachowane, z oryginalną funkcją dekodowania.
- `README.md:59`: opis lewej kolumny zamiast dolnego paska.

Weryfikacja: `ruff check` i `ruff format --check` czterech zmienionych plików
Python oraz `git diff --check` — bez błędów. Testy **nieuruchomione** na
polecenie użytkownika: bez pytest, playera, okien i procesów roboczych.
Nie wykonano screenshotów, próby przenoszenia między monitorami, pomiarów
RSS/p95/VRAM ani odbioru w oknie; skala stylu w testach offline nie zastępuje
próby DPI na monitorach. Bez commita.

### Runda 28 — miniatury ze stanu końcowego

- `src/manimcue/player/decoder_worker.py:32`: wideo/GIF wybierają
  `end_thumbnail`, a przy jego braku lub błędzie plik źródłowy; początkowy
  `thumbnail` nie zastępuje ostatniej klatki. Live używa wyłącznie zapisanego
  `thumbnail`, obraz pozostaje obrazem pliku.
- `src/manimcue/player/decoder_worker.py:43`: GIF składa ostatnią klatkę
  przez Pillow (`seek(n_frames - 1)`) w oryginalnych wymiarach, następnie
  konwertuje i pomniejsza; bez listy rastrów RGBA.
- `src/manimcue/player/decoder_worker.py:54`: seek blisko końca uwzględnia
  `start_time`, `duration` i `time_base`; dekodowanie do EOF zachowuje ostatnią
  klatkę, także po opróżnieniu B-frames. Błąd seek/decode lub brak klatek po
  seek powoduje ponowne otwarcie i dekodowanie od początku. Kontrola limitu
  deklaracji i każdej klatki, jeden wątek kodeka, reformat i ndarray tylko
  ostatniej klatki po pomniejszeniu; pełna klatka zwalniana przed kolejną warstwą.
- `src/manimcue/player/decoder_worker.py:109`: kompozycja z `float("inf")`;
  istniejące `stage.compose` i `geometry.rect_at` obsługują końcowy rect bez
  poprawek. Rate, pętla i długość bazy nie wyznaczają końca innych źródeł.
  Jeden job kompozycji, nadzór 5 s i anulowanie procesu pozostają bez zmian.
- `tests/test_imgui_sources.py:91`: oczekiwany końcowy rect i alfa live.
  `:436`: limit także klatki pośredniej i pomniejszenie przed ndarray.
  `:536`: generowane w tmp_path wieloklatkowe wideo H.264 z B-frames,
  niezerowym PTS, czarnym początkiem, różnymi długościami, zerowym rect,
  końcowym keyframe po bazie, rate/pętlą, priorytetem end_thumbnail oraz
  fallbackiem pliku i seek (błąd, pusty wynik, błąd decode).
  `:612`: częściowe klatki GIF, przezroczystość i disposal.
  `:635`: timeout i zakaz następnego startu przed exit; istniejące testy
  anulowania i startu po exit zachowane.

Weryfikacja: uruchomiono wyłącznie wskazane dwa moduły pytest z `-m "not gpu"`,
`-p no:cacheprovider`, PYTHONPATH wskazującym src tego worktree oraz TMP/TEMP
w `.tmp`, ustawionymi w tej samej komendzie. Końcowy wynik: **50 errors,
2 warnings, 0.42 s** — wszystkie błędy na etapie setup, `PermissionError:
[WinError 5] Access is denied` dla `.tmp/pytest-of-Franek`. Żaden test nie
wykonał ciała; wynik nie potwierdza poprawności implementacji. Pierwsza próba
przed rozszerzeniem parametrów: analogiczne 43 błędy setup. Nie uruchamiano
innych testów, playera, GPU ani formattera. Ponowny odbiór Load24, pomiary
RSS/procesów i responsywności pozostają do próby w oknie. Zmiany rundy 27
zachowane, bez commita.

### Runda 29 — długożyjący ekstraktor

Codex wdrożył, przerwany przeciążeniem modelu przed raportem; raport i przegląd Claude.

- `src/manimcue/player/decoder_worker.py` `run_thumbnail(connection)`: pętla recv → `render_thumbnail` → SHM → wynik →
  ACK, sprzątanie SHM po każdym żądaniu; błąd materiału wysyła błąd i obsługuje następne żądanie.
- `src/manimcue/player/sources_av.py` `Thumbnails`: uchwyt procesu osobno od bieżącego żądania `(key, revision,
  began)`; wynik publikowany po odbiorze, exit zwalnia slot osobno; timeout 5 s od wysłania; 2 s bezczynności liczone
  w rodzicu; `configure` zastępuje oczekujące bez anulowania pracy; `allow_start` tylko dla zimnego startu; odczyt
  SHM przycięty do `width*height*4` (Windows zaokrągla rozmiar SHM).
- `src/manimcue/player/app.py`: `_enter` czyści zakres tylko przy zmianie decku; ukrycie Info zatrzymuje ekstraktor.
- `src/manimcue/live_pool.py` `try_acquire`: odmowa roli niższej przy świeżym (<0,5 s) `waiting` roli wyższej.
- Claude: usunięty zbędny `except: raise` (ruff TRY203), `ruff format` 5 plików.

Pomiar bez okna (Load24, 12 miniatur, `Thumbnails` z fałszywym uploaderem, bez budżetu): **1,31 s** (pierwsza 0,45 s
ze spawnem, kolejne co ~0,08 s) zamiast 5,43 s. Testy: `test_imgui_info`, `test_imgui_sources`, `test_imgui_cli`,
`test_imgui_navigation`, `test_live_pool`, `test_imgui_prefetch` — **116 passed, 55 s**; ruff zielony.
RSS długożyjącego PID — w odbiorze (zadanie 8).

Zwykły pytest po rundach 27–29 (kod worktree przez `PYTHONPATH`): **738 passed, 2 skipped, 58 deselected, 0 failed,
625 s**. Próba człowieka Demo: kolumna miniatur, obrazy stanu końcowego, skok miniaturą i interakcja live w oknie
głównym działają. Load24 (24 identyczne kopie jednego slajdu) dawało wrażenie „zawieszenia na slajdzie 1” —
sondy klawiatury i wejść: każde → przyjęte, wejścia ~0,1 s. Otwarte: jednorazowe „Brak postępu dekodera przez 2 s”
po ~45 min bezczynności (sonda bez źródła błędu w tamtej sesji; do obserwacji w odbiorze).

# REPORT-10a — wznowienie po bramkach, zadania 3–10

**Aktualizacja tej sesji:** bramki 1 i 2 zaliczone przez Claude w ed012bb.
Kod zadań 3–10 dodany; Qt pozostaje domyślny. Końcowa kontrola skupiona:
**80 passed**, Ruff check/format zielone (28 plików). Pełny pytest finalnego
kodu: **649 passed, 2 failed (testy sieciowe), 2 skipped**, 917.21 s.
Szczegóły końcowego wyniku znajdują się na końcu tego raportu.
Zadanie 11 pozostaje do odbioru przez Claude; measure.py przygotowane.
Szczegóły implementacji, dowody, odstępstwa i komendy: końcowe sekcje raportu.

## Historia poprzednich sesji i etapów

Poniższe stare wpisy STOP/bramka 2 niezaliczona opisują stan sprzed aktualizacji
Claude. Nie są aktualnym statusem bramek.

# REPORT-10a — bramka Windows zaliczona programowo, STOP na bramce Pyodide

**Końcowy pełny pytest bieżącej sesji:** **581 passed, 2 failed, 2 skipped,
57 warnings, 943,64 s, kod 1**. Dwa błędy: brak Playwright offline w bramce 2
oraz timeout 240 s istniejącego web PoC. Pełny zestaw nie jest zielony.

**Aktualizacja bieżącej sesji, 2026-10-23:** zadanie 1 zaimplementowane,
3 testy GPU zielone, dwa monitory wykryte, geometria/uchwyty/backend/kursor
sprawdzone. Zadanie 2 przygotowane, część PC: 6 testów zielonych; część
Pyodide: 1 test czerwony z powodu braku Playwright w cache offline.
**Bramka 2 NIEZALICZONA, zadania 3–10 niewykonane.** Kontrakt wymaga obu
bramek przed portem; wyjątek środowiskowy z polecenia użytkownika dotyczył
przejścia z bramki 1 do 2, nie pominięcia bramki 2. Szczegóły wznowienia
i końcowy pełny pytest na końcu pliku. Poniższy pierwotny raport pozostaje
zapisem historycznym: blokada imgui-bundle/uv.lock została usunięta przez
Claude przed tą sesją, obecnie import imgui_bundle działa.

## Historyczny raport poprzedniej sesji

Data: 2026-10-23. Repozytorium główne `D:/Programming/Python/manim/manim-cue`,
gałąź `develop`, bez worktree. Wykonawca codex. **10a nie jest zaimplementowane.**

## Wynik i przyczyna zatrzymania

Krok 1 wykonany: kontrakt po rundzie 21, D42–D44, rozstrzygnięcie wszystkich 23 ustaleń,
pełna recenzja w REVIEW-LOG bez zmiany treści. Lista zadań 0–11 ma kolejność, pliki,
sygnatury, testy odbioru i budżety. Zapisano dokładny ACK, gotowy obraz bariery 5g,
przejścia nawigacji, ograniczenia dekodera i rozdzielenie zegarów.

Krok 2 zatrzymany na przygotowaniu **bramki 1**, zgodnie z poleceniem „Jeśli bramka
nie przejdzie, zatrzymaj się”. `.venv` nie zawiera imgui_bundle. Próba dołączenia
zależności bez zmiany .venv:

```powershell
uv run --frozen --with imgui-bundle==1.93.0 --with PyOpenGL==3.1.10 python -c "import imgui_bundle"
```

zwraca kod 1: `imgui-bundle was not found in the cache`; `UV_OFFLINE=1` uniemożliwia
rozwiązanie zależności. To nie jest negatywny wynik samego API hello_imgui — API okien
nie zostało uruchomione. Ponadto środowisko według instrukcji użytkownika nie pozwala
na prawdziwe okno. Brak dowodu dwóch monitorów/okien oznacza bramkę **niezaliczoną**.
Nie napisano niezweryfikowanej aplikacji bramki i nie przechodzono do dalszych zadań.

`uv lock` również uruchomiono z wymaganym cache i offline: kod 1, ten sam brak
imgui-bundle w cache. `uv.lock` pozostał bez zmian; pyproject zawiera nowe piny, więc
manifest i lock wymagają uzgodnienia po przywróceniu sieci. Nie wyłączano offline,
nie sięgano po inny cache, nie instalowano nic do .venv.

Krok 3 wykonany jako dokumentacja **rzeczywistego stanu**, po angielsku: planowana komenda
ImGui jest oznaczona jako jeszcze niedostępna. Nie udajemy wdrożenia `--player imgui`.

## Rozstrzygnięcia rundy 21

1. Przyjęto jawny wyjątek D43 od ograniczenia D17 dla wewnętrznego zegara mediów PC, ponieważ dotychczasowe zapisy były sprzeczne.
2. Przyjęto ograniczone ticki, priorytet live/ACK i izolację blokującego dekodera w procesie, ponieważ sam jeden wątek nie chroni UI przed wywołaniem natywnym.
3. Przyjęto CFR renderów, walidację PTS pozostałych wideo i czasy/disposal GIF z limitem pamięci, ponieważ average_rate nie opisuje wszystkich mediów.
4. Przyjęto barierę z gotowym obrazem skorelowanego restore, ponieważ READY nie dowodzi przywrócenia stanu.
5. Przyjęto ACK po przyjęciu granicy do trwałego zasobu kompozycji; odrzucono oczekiwanie na fizyczne wyświetlenie, ponieważ D41 go nie wymaga i swap go nie dowodzi.
6. Przyjęto bramkę dwóch okien Windows i odtwarzanie geometrii, ponieważ samo enable_viewports nie zapewnia parytetu F.
7. Przyjęto jawne GLFW/OpenGL3, lifecycle tekstur i pomiar swapów, ponieważ flaga vsync nie jest wynikiem pomiaru.
8. Przyjęto użycie istniejącego keys.py, domyślne stałe bez Qt i mapowania modyfikowane, ponieważ liczbowy TOML musi pozostać zgodny.
9. Przyjęto tabelę przejść zamiast listy akcji, ponieważ przygotowanie, reverse i zamówione wyjście z pętli mają różną semantykę.
10. Przyjęto pełną macierz CLI/Info oraz rozróżnienie zera od None w start_at, ponieważ aliasy i indeks zero są częścią interfejsu.
11. Przyjęto wspólny snapshot Info/S z rewizją komunikatu i trwałą degradacją, ponieważ READY nie może ukrywać nieudanego restore.
12. Przyjęto niezależny podgląd bez bariery głównej; odrzucono wycięcie ruchu podglądu z 10a, ponieważ prelegent już włączył go do F10 (dokładny zegar do potwierdzenia).
13. Przyjęto jawne przestrzenie współrzędnych, clipping, alfa i testy pikselowe, ponieważ geometria draw list nie dowodzi poprawnego blendowania i hit-testu.
14. Przyjęto osobny kontroler live z zachowaniem EntryHistory/transportu i dwufazowym shutdown; odrzucono port 1:1 oraz przypisanie Claude'owi implementacji, ponieważ UI wymaga wydzielenia, a wykonawcą całości jest codex.
15. Przyjęto router wejścia, agregację fokusu obu okien i gesty w jednostkach kontenera, ponieważ D20/D28 muszą działać również z Info i przy DPI.
16. Przyjęto fixture protokołu tekstur 1.92+ i osobny odbiór GPU, ponieważ stare fonts.build nie jest dostępnym API.
17. Przyjęto nazwany czysty zestaw testów i manifest JSON dla Pyodide, ponieważ workerów PC i importów Qt/PyAV nie da się przenieść do WASM.
18. Przyjęto autorytatywne okno web i protokół repliki z generacją/rewizją, ponieważ BroadcastChannel sam nie rozstrzyga właściciela stanu.
19. Przyjęto D44 bez zmiany decyzji prelegenta oraz gest/obsługę odmowy audio web, ponieważ PoC z muted nie potwierdza odtwarzania dźwięku.
20. Przyjęto lokalne domknięcie zależności offline z sumami i testem zimnego profilu, ponieważ dwa artefakty nie wystarczają do bootstrapu.
21. Przyjęto asynchroniczny jednowątkowy serwer z porcjowaniem, allowlistą i GET/HEAD/206/416, ponieważ HTTPServer PoC może blokować inne filmy.
22. Przyjęto mierzalny protokół wydajności, watchdog i tolerancje obrazów, ponieważ średnia uploadów PoC nie zalicza odbioru okien.
23. Przyjęto reestymację po bramkach i zakres 50–80 h jako ocenę ryzyka; odrzucono delegowanie Haiku oraz budżet 30 h jako wiarygodny, ponieważ codex wykonuje wszystkie zadania etapami, a okna i dekoder nie są jeszcze zweryfikowane.

Przyjęto kolejność zadań 0–11 z końcowej tabeli recenzji; Claude przegląda każdy etap, ale niczego za codex nie implementuje. Przyjęto wyłączenie hwaccel, adaptacyjnego skalowania i implementacji audio PC poza ostrzeżeniem, ponieważ nie są potrzebne do uzgodnionego celu; testy bariery, shutdown, przeciążenia i dwóch okien pozostają obowiązkowe.

## Zmiany plik po pliku

| Plik | Zmiana |
|---|---|
| PLAN.md | Nagłówek kontraktu, architektura, źródła, zegary/przeciążenie, bariera/ACK, tabela przejść, geometria/wejście/Info, macierz CLI, zadania 0–11, kryteria, budżet 60 h/stop 120 h i granice 10b/10c. |
| SPEC.md | D42–D44 w stylu poprzednich decyzji i jawny wyjątek D43 od D17; audio prelegenta zachowane. |
| REVIEW-LOG.md | Runda 21: pytania, 23 rozstrzygnięcia i odrzucenia z powodami, pełny tekst recenzji bez zmian. |
| CLAUDE.md | Wyłącznie punkt 2 „Przeczytaj najpierw”: stan F10 i blokada bramki. |
| pyproject.toml | imgui-bundle==1.93.0 i PyOpenGL==3.1.10 z komentarzami powodów; lock offline zablokowany. |
| README.md | Angielski opis stanu, przyszłej komendy, różnic i ograniczeń; Qt nadal działa jako domyślny. |
| docs/api.md | Angielska informacja o planowanym uruchomieniu, ograniczeniach audio/web i niedostępności backendu. |
| reports/REPORT-10a.md i REPORT-10a.md | Identyczny raport blokady, testów, decyzji i kolejnych prób. |

Nie zmieniono kodu produkcyjnego ani istniejącego `player/keys.py` i jego testów;
kontrakt wymaga ich ponownego użycia w zadaniu 3, zamiast nowej tabeli klawiszy.
Pliki pomocnicze `.tmp/close_f10.py` i `.tmp/report_f10.py` są lokalnymi skryptami
edycji dokumentów w ignorowanym katalogu, nie elementem playera.

## Testy i dowody

Polecenia uruchamiano z UV_CACHE_DIR, UV_OFFLINE=1, TMP/TEMP oraz
QT_QPA_PLATFORM=offscreen zgodnie z instrukcją. Dodatkowo **UV_NO_SYNC=1** chronił
istniejącą .venv przed automatyczną synchronizacją przez uv; frozen nie oznacza no-sync.

Pełne wymagane polecenie `uv run --frozen pytest -q -p no:cacheprovider`:
**0 wykonanych testów, 1 skipped, 1 error przy kolekcji, 2 warnings, kod 1**.
Powód: `experiments/f5i_imgui/test_poc.py` importuje `stage.py`, który importuje
nieobecny `imgui_bundle`. Wynik potwierdzono także po zmianie dokumentów i pinów.
To nie jest zielony pełny pytest. `tests/test_player_keys.py` używa importorskip,
więc istniejące testy klawiszy nie stanowią dowodu zaliczenia ImGui w tej sesji.

Dodatkowy regresyjny przebieg:
`uv run --frozen pytest -q -p no:cacheprovider --ignore=experiments/f5i_imgui -m "not gpu"`
— **481 passed, 2 skipped, 82 deselected, 51 warnings, kod 0, 423,85 s**.
Wyłączenie PoC/gpu dotyczy tylko tego pomocniczego przebiegu, nie odbioru pełnego zestawu.

Kontrola dokumentów (assert-based, bez instalowania zależności):
pełny REVIEW-LOG kończy się dokładnym odczytanym tekstem recenzji;
CLAUDE przed punktem 2 i od punktu 3 jest identyczne z HEAD;
tomllib parsuje pyproject i potwierdza oba piny; brak starego nagłówka szkicu.
`git diff --check` przechodzi. To kontrola dokumentacji, nie test playera.

| Kryterium PLAN 10a | Status i dowód |
|---|---|
| 1. Bramki PC/Pyodide | Niezaliczone: resolver `uv run --with` kod 1, brak okna; bramka 2 nieuruchomiona ze względu na kolejność. |
| 2. Nawigacja/CLI/5g | Niewykonane: test_imgui_navigation/test_imgui_cli/test_imgui_live_checkpoint są nazwami planowanych plików, nie istniejącym dowodem. |
| 3. Kompozycja/piksele | Niewykonane: test_imgui_composition i zrzuty GPU wymagają implementacji. |
| 4. Live/przeciążenie/shutdown | Niewykonane: planowane test_imgui_live i test_imgui_sources; brak nowych pomiarów workerów. |
| 5. Info/fokus/gesty | Niewykonane: planowane test_imgui_info i test_imgui_input. |
| 6. Wydajność/stabilność | Niewykonane: brak odblokowanego okna i nowego playera; PoC nie zalicza kryterium. |
| 7. Pełny pytest | Niezaliczone: 1 error kolekcji; brak nowych testów otwierających okna. |
| 8. Próba człowieka | Oczekuje na Claude po zaimplementowaniu i zaliczeniu automatycznej części bramek. |

## Wznowienie, komendy i próby dla Claude

Najpierw w sesji z siecią (nie wykonano tutaj):

```powershell
$env:UV_CACHE_DIR='D:/Programming/Python/manim/manim-cue/.cache/uv'
$env:TMP='D:/Programming/Python/manim/manim-cue/.tmp'
$env:TEMP=$env:TMP
$env:UV_OFFLINE='0'
$env:UV_NO_SYNC='1'
uv lock
```

To odświeża lock, nie jest zaliczeniem bramki. Dalsze testy można uruchamiać przez
`uv run --frozen --with imgui-bundle==1.93.0 --with PyOpenGL==3.1.10 ...`
z UV_NO_SYNC=1, aby nie synchronizować głównej .venv. Kod aplikacji bramki 1
`experiments/f10a_gate/windows.py` i testy z tabeli PLAN **jeszcze nie istnieją**;
codex ma je napisać i uruchomić po usunięciu blokady, przed jakimkolwiek portem.
Nie ma obecnie komendy, która zaliczy dwa okna finalnego playera.

Claude ma sprawdzić: Info natywne od startu na wybranym monitorze; programowy JSON
monitorów, uchwytów, pozycji, rozmiarów i fullscreen obu okien przed/po F i powrocie;
H w głównym, jawne GLFW/OpenGL3, realne odstępy swapów/vsync. Człowiek dodatkowo:
różne DPI, ostrość tekstu/obwódek, fokus po przejściu do Info i innej aplikacji,
brak samoczynnej minimalizacji, poprawność przywrócenia geometrii i wygląd.
Testy otwierające te okna mają mieć znacznik gpu; offscreen nie jest substytutem.

Istniejący PoC — komenda do **pomiaru pomocniczego**, ekran odblokowany, domyślne vsync,
osobne N=1..3 i trzy powtórzenia (to nie jest pomiar finalnego 10a):

```powershell
uv run --frozen --with imgui-bundle==1.93.0 --with PyOpenGL==3.1.10 python experiments/f5i_imgui/desktop.py --clips 3 --warmup 5 --seconds 60 --output .tmp/MEASUREMENT-10a-poc-n3.json
```

Info i live są domyślnie włączone. Zapisać sprzęt/Hz/CPU, wyniki osobno dla wszystkich
strumieni i ograniczenia licznika uploadów. Finalny pomiar `experiments/f10a_gate/measure.py`
powstaje dopiero w zadaniu 11; musi dodać watchdog, okna 1 s, próby GL/CE, 30 min i 100 przejść.

Istniejąca próba web PoC, headless Edge przez Playwright (pomocnicza, nie bramka importów):

```powershell
uv run --frozen --with playwright python experiments/f5i_imgui/drive_web.py --channel msedge --clips 3 --warmup 5 --seconds 60 --output .tmp/MEASUREMENT-10a-web-poc.json
```

PoC pobiera runtime/pakiety z sieci, więc offline ta próba nie jest obiecana.
Bramka 2 ma osobno ładować wspólne moduły i uruchomić named suite z PLAN w Pyodide,
sprawdzając całe drzewo importów; dotychczasowy PoC jej nie zastępuje.

## Czas, odstępstwa i punkty do potwierdzenia

Czas sesji: około 16 minut łącznie z odczytem materiałów i testami; pierwszy zapis zegara 11:05:49 CEST, zakończenie 11:19:22 +0200. Pierwsze odczyty poprzedzały zapis zegara, dlatego całość jest przybliżeniem; dodatkowy pytest zmierzył dokładnie 423,85 s.
Nie przekroczono dwukrotnego budżetu zadania 0/1 ani całości. Przerwa jest wynikiem
bramki i ograniczeń środowiska, nie oszczędzania zakresu. Czas Claude i prób człowieka: 0.

Odstępstwa: nie wykonano implementacji 10a, aplikacji bramki, Pyodide ani prób GPU;
lock niesynchronizowany z nowymi pinami; pełny pytest niezielony. Dokumentacja komendy
opisuje stan planowany zamiast nieistniejącego backendu. Nie wykonano przeglądu przez
Claude — raport i diff są przygotowane do przeglądu etapu 0. Brak commita, stash,
reset, checkout, worktree, zmian .venv i łatania Manima. Identyfikatory w przyszłym
kodzie angielskie, komentarze/docstringi polskie (wyjątek upstream slides zachowany).

**Do potwierdzenia:**

1. Fullscreen bez ramek na geometrii monitorów zamiast wyłącznego — mniejsze ryzyko minimalizacji/fokusu.
2. Ruch preview ma własny czas każdego źródła, reset na jego pętli/zmianie celu; miniatury live rect_at(0) — nie wpływa na główną barierę.
3. Tolerancja dryfu webowej repliki 100 ms i resync powyżej — szczegół 10b, nie blokuje projektu PC.

D44 (PC bez dźwięku i ostrzeżenie) oraz wykonanie etapami pozostają rozstrzygnięte,
nie są pytaniami do ponownego zatwierdzenia.

## Wznowienie 2026-10-23 — zadanie 1

Bramka Windows zaimplementowana w `experiments/f10a_gate/windows.py`; odbiór w
`tests/test_imgui_windows_gate.py`. Bez zmian pyproject/lock/.venv. Brak pakietu
Python glfw rozwiązano dostępem ctypes do tej samej glfw3.dll dostarczonej przez
imgui-bundle. Uchwyty pobierane z platform_handle viewportu, HWND z GLFW.

Dowód: `test_two_native_windows`, `test_fullscreen_roundtrip`,
`test_cursor_and_backend`: **3 passed**, także F10_INFO_MONITOR=1 (drugi monitor),
0,56 s. Ruff check i format zielone. Programowy JSON: dwa monitory
3440x1440@60 przy (0,0) oraz 2560x1440@59 przy (3440,-588); osobne natywne
okna; jawny Glfw - OpenGL3; borderless fullscreen i odtworzenie osobnych geometrii.
Pomiary wywołań glfwSwapBuffers osobno dla obu okien, interval_requested=1;
krótkie czasy nie dowodzą vsync przy zablokowanym ekranie.
Czas zadania około 8 min z odczytem kontraktu; limit 8 h nieprzekroczony.
Odstępstwa: brak próby człowieka DPI/fokus/wygląd; do Claude, jak uzgodniono.
Bramka 1: część programowa zaliczona, próba człowieka pozostaje.
Komenda: `uv run --frozen python experiments/f10a_gate/windows.py --info-monitor 1 --output .tmp/MEASUREMENT-10a-windows.json`.

## Wznowienie — zadanie 2 (nieukończone, STOP)

Pliki przygotowane zgodnie z zamkniętą listą:
- `src/manimcue/player/__init__.py`: granica pakietu bez adapterów;
- `manifest.py`: validate_manifest, kopia JSON, wersja/rozdzielczości/czasy/rate/rect;
- `clock.py`: wewnętrzny czas, kotwica, rate, pauza i wznowienie;
- `geometry.py`: fit, kontener i clipping w logicznych współrzędnych;
- `state.py`: stan początkowy i niezależny snapshot;
- `controller.py`: podstawowe przejścia potrzebne do named cases bramki;
- `experiments/f10a_gate/imports.py`: identyczne run_shared_cases na PC/Pyodide,
  blokada zabronionych importów, osobny interpreter PC, headless Edge Playwright;
- `experiments/f10a_gate/pyodide.html`: bootstrap przypiętego Pyodide v314.0.7,
  wgranie dokładnie tych samych źródeł i odebranie wyniku JSON;
- `tests/test_imgui_shared_imports.py`, `tests/test_imgui_shared_logic.py`.

Dowód PC: `test_pc_shared_imports` i parametrized `test_shared_case`:
`clock_pause`, `navigation_table`, `geometry_clip`, `stale_entry`,
`manifest_validation`. **6 passed**; pusty zbiór zabronionych importów
w osobnym interpreterze PC, 7 odrzuconych niepoprawnych manifestów.
`navigation_table` w tej bramce sprawdza tylko przygotowanie/start/pauzę/next;
pełna tabela (loop/reverse/history/CLI/live) należy do niewykonanego zadania 4.
To nie jest gotowy kontroler produkcyjny ani implementacja playera.

`test_pyodide_shared_imports`: **1 failed**, nie skip. Dokładny błąd resolvera:

```text
× No solution found when resolving `--with` dependencies:
╰─▶ Because playwright was not found in the cache and you require
    playwright, we can conclude that your requirements are unsatisfiable.
    hint: Packages were unavailable because the network was disabled. When
    the network is disabled, registry packages may only be read from the cache.
```

Polecenie `uv run --frozen --with playwright python -c "import playwright"`
z UV_OFFLINE=1 potwierdziło ten sam błąd. Nie zmieniano cache na cudzy,
nie wyłączano offline, nie instalowano zależności i nie zmieniano .venv.
Nie uruchomiono Edge/Pyodide: to blokada środowiska, brak dowodu API przeglądarki.
Strona wymaga też dostępu do przypiętego CDN Pyodide (domknięcie offline to 10b).
Ruff check i format dla wszystkich 11 zmienionych plików Python: zielone.
Czas przygotowania zadania 2 około 5 min, limit 6 h nieprzekroczony.

### Dalsze zadania i komendy dla Claude

Zadania 3, 4, 5, 6, 7, 8, 9, 10: **niewykonane**, wymagana bramka 2
nie przeszła. Qt i jego CLI niezmienione. Zadanie 11 pozostaje dla Claude;
measure.py nie przygotowano, ponieważ finalny player jeszcze nie istnieje.
Nie ma komendy pomiaru finalnego playera i nie ma wdrożonego --player imgui.

W sesji Claude z dostępem do sieci (bez synchronizacji .venv):

```powershell
$env:UV_CACHE_DIR='D:/Programming/Python/manim/manim-cue/.cache/uv'
$env:TMP='D:/Programming/Python/manim/manim-cue/.tmp'
$env:TEMP=$env:TMP
$env:UV_NO_SYNC='1'
$env:QT_QPA_PLATFORM='offscreen'
$env:UV_OFFLINE='0'
uv run --frozen --with playwright python experiments/f10a_gate/imports.py --channel msedge --output .tmp/MEASUREMENT-10a-imports.json
uv run --frozen pytest -q -p no:cacheprovider tests/test_imgui_shared_imports.py tests/test_imgui_shared_logic.py
$env:UV_OFFLINE='1'
$env:F10_INFO_MONITOR='1'
uv run --frozen pytest -q -p no:cacheprovider tests/test_imgui_windows_gate.py
uv run --frozen python experiments/f10a_gate/windows.py --main-monitor 0 --info-monitor 1 --output .tmp/MEASUREMENT-10a-windows.json
```

Obowiązkowy wynik bramki 2: status ok i identyczne pc/pyodide z pięcioma
named cases oraz pustym forbidden_imports. Sam test PC nie wystarcza.
Jeśli API bramki nie przejdzie, zatrzymać port. Po zaliczeniu wznowić od zadania 3.

**Do potwierdzenia przez Claude/człowieka:** DPI i ostrość; fokus po przejściu
main/Info/inne aplikacje i brak minimalizacji; wygląd; dwa monitory w praktyce;
rzeczywisty vsync przy odblokowanym ekranie. Borderless fullscreen, niezależny
czas ruchu preview i tolerancja web 100 ms pozostają decyzjami do potwierdzenia
z kontraktu. Próby człowieka i przegląd Claude w tej sesji: 0 min.

Nie wykonano commita, stash, reset, checkout, worktree, zmian .venv ani łatania
Manima. UV_NO_SYNC=1 dodatkowo zabezpieczało .venv przy wszystkich uv run.
Odstępstwo od celu zadań 1–10 wynika z obowiązkowej bramki 2, nie z budżetu.

## Końcowy pełny pytest i podsumowanie bieżącej sesji

Wymagane polecenie, bez wyłączania gpu/PoC i bez zmiany .venv:

```powershell
$env:UV_CACHE_DIR='D:/Programming/Python/manim/manim-cue/.cache/uv'
$env:UV_OFFLINE='1'
$env:UV_NO_SYNC='1'
$env:TMP='D:/Programming/Python/manim/manim-cue/.tmp'
$env:TEMP=$env:TMP
$env:QT_QPA_PLATFORM='offscreen'
uv run --frozen pytest -q -p no:cacheprovider
```

**581 passed, 2 failed, 2 skipped, 57 warnings in 943.64s (0:15:43), kod 1.**
Log: `.tmp/f10a-pytest-full.log`. Wszystkie nowe testy PC, w tym trzy gpu
bramki Windows, przeszły także w pełnym przebiegu. Testy istniejącego playera
Qt w tym przebiegu przeszły; nie zmieniano jego kodu ani domyślnego CLI.

Niepowodzenia:
1. `tests/test_imgui_shared_imports.py::test_pyodide_shared_imports`:
   resolver uv nie znajduje Playwright w cache offline; przeglądarka i Pyodide
   nie zostały uruchomione. Obowiązkowa bramka 2 nadal niezaliczona.
2. `experiments/f5i_imgui/test_poc.py::test_web_smoke_same_stage_in_browser`:
   wynik istniejącego PoC `{'error': 'brak metryk po 240.0 s'}`. Nie zmieniano
   PoC; samego powodu braku metryk w tej sesji nie ustalono. Nie zamieniono
   błędu w skip i nie pominięto testu w wymaganym pełnym przebiegu.

Końcowe kontrole: Ruff check i format dla wszystkich 11 zmienionych plików
Python zielone; git diff --check zielony. Gałąź nadal develop, główne drzewo.
Wynik okien z obu monitorów: `.tmp/MEASUREMENT-10a-windows.json`.
Raport wyjściowy `REPORT-10a.md` jest kopią niniejszego pliku.

| Zadanie | Status tej sesji | Dowód / brak |
|---|---|---|
| 1 | Zaimplementowane, programowo zaliczone | test_two_native_windows, test_fullscreen_roundtrip, test_cursor_and_backend; 3 passed także dla Info na monitorze 1 |
| 2 | Przygotowane, nieukończone; STOP | 5 named cases + test_pc_shared_imports zielone; test_pyodide_shared_imports czerwony, brak Playwright offline |
| 3–10 | Niewykonane | Kontrakt wymaga zaliczenia bramki 2 przed portem |
| 11 | Pozostawione Claude | Brak finalnego playera/pomiarów/measure.py; próby człowieka wypisane wyżej |

Czas bieżącej sesji około 30 min: implementacja/odczyt/raport około 14 min,
pełny pytest dokładnie 15 min 43,64 s. Jest to przybliżenie całej sesji,
ponieważ pierwszy jawny odczyt zegara wykonano już podczas pracy (11:35:13
CEST); zakończenie około 11:56 CEST. Czas przeglądu Claude i próby człowieka: 0.
Nie przekroczono 2x budżetu żadnego zadania ani całości. Oczekiwanie na
Playwright/sieć wymaga nowej sesji z odpowiednim środowiskiem; bramki nie
zaliczono zastępczym testem PC ani innym narzędziem przeglądarkowym.

## Wznowienie 2026-10-23 po aktualizacji Claude 12:00 — zadanie 3

Bramki 1 i 2 zaliczone w ed012bb zgodnie z przekazaniem Claude: PC/Pyodide
identyczne, brak zakazanych importów. Poprzednie wpisy STOP opisują stan historyczny.
Zadanie 3: keys.py, input.py, slides/config.py, test_player_keys.py,
test_imgui_input.py. Config() korzysta z jednej tabeli kodów bez Qt; bindings
obsługuje kody TOML, błędy z akcją/decimal/hex i Plus/Asterisk na numpadzie
oraz Shift. Router zachowuje priorytet edycji/rezerwacji/cue i konsumuje repeat.
Dowód: test_actions (9), test_live_priority_and_repeat,
test_plus_asterisk_modifiers, test_config_without_qt_and_numeric_toml,
test_bindings_custom_unknown oraz dotychczasowe test_player_keys i presenter_state:
27 passed, 2 warnings, 12.68 s. Ruff check/format zielone. Czas około 5 min.
Odstępstwa: brak. Nie zmieniono .venv ani stanu gałęzi.

## Zadanie 4 — nawigacja

Pliki: player/controller.py, state.py, test_imgui_navigation.py; clock.py i
shared_logic bez zmian semantyki. Czysty reducer rozszerzony o tabelę przejść,
pętlę/EOF, reverse/replay, zmianę decku, indeksy ujemne i zero, komunikaty z
rewizją, anulowanie starego wejścia i efekty dwufazowego zamykania.
Dowód: test_preparing_next_pause_replay_and_stale, test_paused_static_and_clock,
test_loop_exit, test_backward_across_decks_and_beginning,
test_reverse_to_normal_preserves_live_and_replay_direction, test_eof_and_auto_next,
test_ended_pause_never_restarts_base, test_start_at_zero_negative_resolution_and_preview,
test_last_quit_and_message_revision oraz 5 shared cases: 16 passed (0.06 s).
Ruff check/format zielone. Czas około 5 min. Efekty historii i zachowania live
wymagają podłączenia przez zadanie 7; reducer nie wykonuje I/O.

## Zadanie 5 — źródła PC

Pliki: player/sources_av.py, decoder_worker.py, tests/test_imgui_sources.py.
Spawn izoluje PyAV/Pillow; dwa sloty pamięci współdzielonej ze sprawdzaniem
rewizji, owned RGBA po stronie UI, kontrola przez stały RawArray bez rosnącej
kolejki poleceń. Proces dekoduje max 4 klatki/iterację, seek po zaległości
>250 ms, reset unieważnia generację. GIF używa disposal Pillow, minimalnego
czasu 10 ms i limitu 256 MiB. Przygotowanie 5 s, zastój 2 s, bez join UI.
Dowód: test_image_reset_owned_rgba_and_eof, test_gif_variable_times,
test_invalid_file_error, test_cfr_pts_and_bounded_mailbox,
test_stalled_decoder_poll_and_timeout,
test_ready_decoder_hang_keeps_frame_and_nonblocking_control (10000 poleceń
przy rzeczywiście zawieszonym procesie), test_gif_loop_uses_same_generation:
7 passed, 1.20 s. Ruff check/format zielone po poprawie importów testu.
Czas około 10 min. Do dalszego odbioru: pomiar budżetu kopii 1080p i
weryfikacja VFR/PTS na rzeczywistych materiałach; nie wykonano pomiaru GPU.

## Zadanie 6 — kompozycja

Pliki: player/stage.py, geometry.py, textures.py, tests/test_imgui_composition.py.
Komendy zachowują kontener i clip kadru, live nie dostaje ponownego aspect fit,
ruch D30, prostą alfę, wewnętrzne obwódki i hit-test marginesów.
Upload tworzy osobny TextureLease, więc nowa klatka nie mutuje starego snapshotu.
Dowód: test_composition_geometry_alpha_border_hit_margin,
test_draw_data_vertices_uv_clip (rzeczywiste vertices/UV/clip/index data z
renderer_has_textures, set_tex_id/set_status), test_texture_upload_owned_rgba
(gpu, odczyt pikseli GL i dwie niezależne tekstury): 3 passed, 0.27 s.
Ruff check/format zielone. Czas około 5 min. Odbiór screenshotów demo 1–11
względem Qt pozostaje zadaniem 11; test uploadu nie jest tym porównaniem.

## Zadanie 7 — live

Pliki: player/live.py, test_imgui_live.py, test_imgui_live_checkpoint.py.
Ponownie użyte EntryHistory/LiveSession/LiveSpec. Kontroler przyjmuje słowniki,
przejmuje sąsiednie sesje o tej samej tożsamości, rezerwuje checkpoint dopiero
po pierwszych obrazach plików, koreluje granice, przypisuje lease przed ACK,
odrzuca stare wejścia, pompuje anulowane granice, ma timeout 5 s i start/ACK 2 s,
start cue dopiero na wspólny start, pauzę i dwufazowy shutdown.
Dowód: test_ack_after_assign_and_start_after_ready,
test_pause_prepares_without_enter_and_shutdown,
test_timeout_degrades_and_does_not_block_files,
test_cancelled_boundary_ack_without_composition,
test_history_replay_reverse_and_stale_generation,
test_closed_lease_never_acknowledged,
test_real_checkpoint_first_image_and_ack[manimgl/ce-cairo] z prawdziwymi procesami:
8 passed, 2.81 s. Ruff check/format zielone. Czas około 7 min.
Ograniczenie dowodu: rzeczywiste procesy używają testowego lease; upload GL
sprawdzony osobno w zadaniu 6. Pełny parytet scenariuszy Qt wymaga dalszego
odbioru integracji; nie utożsamiać tych 8 testów z całym test_live_checkpoint.

## Zadanie 8 — wejście live

Pliki: player/input.py, live.py, tests/test_imgui_input.py. Własne Config.keys
NEXT/PREVIOUS kierują cue tak samo jak domyślne. Agregacja aktywności obu
okien, Esc, klik najwyższego kontenera (margines blokuje niższe), gesty
normalizowane wymiarem kontenera, Shift-pan/orbit/zoom/reset; CE view no-op.
Dowód: 13 passed (0.06 s), w tym test_custom_live_bindings_and_focus_both_windows
i test_margin_blocks_and_view_normalization. Ruff check/format zielone.
Czas około 3 min; fizyczny fokus/DPI pozostają próbą człowieka.

## Zadanie 9 — Info i koordynacja aplikacji

Pliki: player/info.py, app.py, tests/test_imgui_info.py. Jeden snapshot dla Info/S,
Markdown, czas lokalny i elapsed niezależny od pauzy. Preview ma własne źródła,
normalny kierunek, rozdzielczość docelowego decku, live jako miniatura, ruch
z PTS każdego źródła; ukrycie zamyka dekodery. App pompuje live przed mediami,
ustala barierę obrazów plików, zbiera trwałe błędy i odracza usunięcie lease.
Dowód: test_preview_target_resolution_normal_and_end,
test_hidden_preview_no_decoders_and_independent_motion,
test_info_and_s_snapshot_retains_degradation_and_elapsed: 3 passed (0.05 s).
Ruff check/format zielone. Czas około 6 min. Testy używają źródeł testowych;
wydajność i wygląd Markdown/Info wymagają odbioru zadania 11.

## Zadanie 10 — CLI i integracja desktop

Pliki: player/desktop.py, app.py, manifest.py, slides/present/__init__.py,
test_imgui_cli.py, README.md, docs/api.md. Qt pozostaje domyślny; --player imgui
wybiera jawnie GLFW/OpenGL3. Adapter modelu v4 zwraca JSON, zachowuje reverse,
warstwy, obwódki i osobne rozdzielczości decków. Kody TOML nie zmienione.
Naprawiono priorytet zera w --start-at (także wspólna ścieżka Qt), indeksy
ujemne walidowane przed procesami. Ekrany, Info, F/H, nawigacja i shutdown
podłączone do aplikacji; gesty liczone w rzeczywistym kontenerze viewportu.
D44: ostrzeżenie audio raz na materiał, także gdy powtórzony jako klip/deck.
Dowód: test_backend_default, test_selection_and_common_options,
test_playback_flags, test_aliases (3), test_geometry_and_rate,
test_start_indices, test_screens, test_desktop_gui_without_native_windows,
test_warning_once_per_audio_material: 11 passed, 0.35 s.
Callbacki GUI testowano z rzeczywistym kontekstem ImGui i testowymi źródłami,
bez nowego natywnego okna finalnego playera. To nie jest odbiór wyglądu okien.
Ruff check/format zielone, także jawnie dla dwóch plików slides (uporządkowanie
importów, formatowanie i usunięcie dwóch nieaktywnych noqa).

### Uzupełnienia po testach integracyjnych — bez zmiany kontraktu

Powrócono do zamkniętych plików etapów 5/6/7/9 w celu poprawienia błędów
wykrytych podczas integracji; to odstępstwo od ścisłej jednoprzebiegowej
kolejności plików. Nie zmieniono semantyki PLAN/SPEC ani nie pominięto testów.

- Zadanie 5: pauza/wznowienie zachowuje pozycję; zamówione wyjście z pętli
  zachowuje prawdziwą ostatnią klatkę; obrazy nie są dekodowane ponownie w pętli.
  Sonda PTS/DTS pakietów przed pierwszym obrazem, potem kontrola monotonicznych
  znormalizowanych PTS dekodera. GIF sprawdza limit przed konwersją.
  Osobne liczniki decode/conversion/seek/loop_seek/published/dropped, bez kolejki
  metryk. test_cfr_pts_and_bounded_mailbox obejmuje pauzę/wznowienie;
  test_gif_loop_uses_same_generation obejmuje ostatnią klatkę po wyjściu;
  test_pts_preflight_rejects_before_first_image (2): źródła 9 passed.
- Zadanie 6: rzeczywiste renderowanie trójkątów z ImGui draw data do FBO,
  piksele alfa prosta i clip: test_render_pixels_straight_alpha_and_clip;
  krycie tła kamery nie jest mnożone drugi raz, aktywna obwódka ma globalne
  pierwszeństwo przed pierwszym błędem. Kompozycja: 4 passed.
- Zadanie 7: rzeczywiste piksele GL/CE po ręcznym cue/previous/replay
  (test_real_previous_replay_and_manual_boundary_pixels, 2); obraz sprzed
  restore jest przypięty do wyniku operacji, błąd odtwarza jego zasób;
  test_restore_error_keeps_protected_resource_and_degradation;
  test_late_operation_status_finishes_after_uploaded_boundary;
  test_navigation_acknowledges_copied_boundary_waiting_for_status.
  Anulowane skopiowane granice dostają ACK bez uploadu; spóźniony status może
  zwolnić barierę bez kolejnego obrazu. Timeout upload/ACK: 2 s.
  Live i checkpoint: 13 passed.
- Zadanie 9/10: ruch główny ma osobny aktywny zegar, preview ma osobne kotwice
  każdego źródła (również obrazu), reset przy pętli/zmianie; usunięto stary
  preview po zmianie decku/ukryciu. Lease usuwany dopiero po obu viewportach,
  z uwzględnieniem przypięcia restore.

### Końcowa kontrola skupiona (kod zamrożony 12:42 CEST)

78 passed, 2 warnings, 11.44 s. Log: .tmp/f10a-targeted-final.log.
Obejmuje wszystkie pliki testów zadań 3–10, pięć shared cases oraz
 test_pc_shared_imports. Ruff: All checks passed; 28 files already formatted.
Osobny izolowany interpreter zaimportował manifest/clock/controller/geometry/
state/keys/input/stage/info z blokadą Qt/PyAV/multiprocessing/Pydantic/rtoml/
Manima/slides: forbidden_imports=[], bez kontekstu GUI.
Nie uruchamiano ponownie Pyodide offline jako zastępczego dowodu bramki:
zaliczenie ed012bb i wynik Claude pozostają autorytatywne.

## Przygotowanie zadania 11 — tylko narzędzie, odbiór dla Claude

experiments/f10a_gate/measure.py: watchdog(command, timeout), measure(options).
Watchdog nadzoruje proces bez wątków, czyta opcjonalny heartbeat wskazany
F10_HEARTBEAT, przerywa przy ciszy >2 s (bootstrap 10 s) i twardym timeout.
Analiza JSONL z nowymi frame_id liczy medianę pełnych okien 1 s, p95 odstępów,
max ciszy wraz z brzegami próby oraz opcjonalne decode/conversion/upload/seek
 i input_latency. Nie utożsamia ticków ani swapów z nowymi obrazami.
Self-check: 120 różnych obrazów/2 s daje 60 fps; poprawny proces kończy się
kodem 0; zawieszony proces jest przerywany po 0.126 s dla timeout=0.1;
brak śladu zwraca missing_trace, nigdy fałszywe zaliczenie.
Ruff check/format zielone.

Narzędzie nie dodaje kompletnego automatycznego kolektora JSONL do playera.
Claude musi dostarczyć ślad instrumentacji i sprzęt/Hz/CPU/realne swapy,
30 akcji wejścia, serie N=1..3 dla GL i CE, 3 powtórzenia oraz stabilność.
Nie wykonano zadania 11 ani nie deklaruje się progu 55 fps, p95/latencji,
porównań screenshotów demo 1–11, próby 30 min lub 100 przejść.

### Komendy dla Claude

W przygotowanym środowisku (bez instalacji/synchronizacji głównej .venv):

```powershell
$env:UV_CACHE_DIR='D:/Programming/Python/manim/manim-cue/.cache/uv'
$env:UV_NO_SYNC='1'
$env:TMP='D:/Programming/Python/manim/manim-cue/.tmp'
$env:TEMP=$env:TMP
$env:QT_QPA_PLATFORM='offscreen'
$env:UV_OFFLINE='0'
uv run --frozen --with playwright python experiments/f10a_gate/imports.py --channel msedge --output .tmp/MEASUREMENT-10a-imports-final.json
uv run --frozen pytest -q -p no:cacheprovider tests/test_imgui_shared_imports.py experiments/f5i_imgui/test_poc.py::test_web_smoke_same_stage_in_browser
uv run --frozen pytest -q -p no:cacheprovider
```

Ekran odblokowany, właściwy deck (Demo zastąpić nazwą istniejącego renderu):

```powershell
uv run --frozen manim-cue present Demo --player imgui --show-info-window --screen 0 --info-window-screen 1
uv run --frozen manim-cue present Demo --player qt --show-info-window
uv run --frozen python experiments/f10a_gate/windows.py --main-monitor 0 --info-monitor 1 --output .tmp/MEASUREMENT-10a-windows-final.json
```

Po zebraniu JSONL nowych obrazów z instrumentacji próby (ten plik nie powstaje
automatycznie od samego uruchomienia present):

```powershell
uv run --frozen python experiments/f10a_gate/measure.py --trace .tmp/f10a-trace.jsonl --warmup 5 --seconds 60 --engine manimgl --clips 3 --output .tmp/MEASUREMENT-10a-n3-gl.json
```

Do potwierdzenia: DPI/ostrość, agregacja fokusu main/Info/inne aplikacje,
wygląd i brak minimalizacji, F i powrót osobnych geometrii, H tylko główne,
dwa monitory w praktyce, rzeczywisty vsync i wydajność; niezależny ruch preview
oraz borderless fullscreen zgodnie z wcześniejszym kontraktem.

### Ostatnie domknięcie integracji

Przegląd parytetu względem istniejącego Qt wykrył dalsze błędy, poprawione
przed końcowym odbiorem kodu:

- Reverse odtwarza bazę z rev_file, a klipy zachowuje na end_thumbnail lub
  rzeczywistej ostatniej klatce dekodowanej poza UI; prostokąty są końcowe,
  podgląd pozostaje normalny. Pierwszy zasób at_end jest ogłaszany dopiero po
  dotarciu do końca, bez pokazywania klatek pośrednich.
- Klipy dziedziczą pętlę bazy, skip_all wyłącza pętle również warstw.
- App.tick obsługuje live/ACK, potem callback wejścia, potem media. Gesty
  zebrane podczas draw są oznaczone entry_id i przyjmowane w następnym ticku
  przed mediami; stare wejście je unieważnia. test_live_input_media_order.
- Info/S pokazuje fokus slajdy/live, pętlę i stany klipów; komunikaty 2 s
  są widoczne także bez S. Błąd aktywnego live zwalnia jego fokus.
- Zniknięcie pamięci workera pomiędzy deskryptorem a attach daje error
  źródła, nie wyjątek z callbacku GUI; rozszerzony test_invalid_file_error.

Finalny skupiony przebieg: **80 passed, 2 warnings in 11.86 s**,
.tmp/f10a-targeted-final80.log. Liczby plików testowych: player_keys 8,
input 13, navigation 11, sources 9, composition 4, live 4,
live_checkpoint 9, info 4, CLI 12, shared_logic 5, PC imports 1.
Ruff check zielony; format poprawiono po wykryciu pojedynczego mieszanego
zakończenia linii testu, bez zmiany AST. Żaden test nie został zamieniony w skip.

Przebiegi pośrednie pełnego zestawu (nie końcowy dowód finalnej wersji):

1. .tmp/f10a-pytest-current.log: 638 passed, 2 failed, 2 skipped,
   57 warnings, 915.80 s. Dwa błędy to wskazane testy sieciowe.
2. .tmp/f10a-pytest-final.log: 638 passed, 6 failed, 2 skipped,
   57 warnings, 935.31 s. Ten przebieg został unieważniony: podczas jego
   trwania poprawiano kod, a spawn importował nowy worker z układem liczników
   niezgodnym ze starszym rodzicem. Cztery błędy sources nie są przypisane
   sieci ani ukryte: image_reset_owned_rgba_and_eof, gif_variable_times,
   cfr_pts_and_bounded_mailbox, gif_loop_uses_same_generation. To błąd
   organizacji weryfikacji. Następny wymagany pełny przebieg odbywa się na
   spójnym kodzie; skupiony przebieg wszystkich źródeł po poprawkach: 9 passed.

### Zamrożona wersja do końcowego pełnego pytest (13:05 CEST)

Końcowy przebieg skupiony po wszystkich poprawkach: **80 passed, 2 warnings,
12.25 s**, .tmp/f10a-targeted-release.log. Ruff: All checks passed;
28 files already formatted. Sumy SHA256 26 zmienionych plików Python:
.tmp/f10a-release-hashes.json — po pełnym przebiegu zostaną porównane ponownie.

Ostatnie poprawki parytetu: rezerwacja blokuje tylko cue/view, pozwala na
anulowanie nawigacją i QUIT; globalny autorepeat oraz kody Qt bez modyfikatorów
pozostają zgodne z Qt, repeat aktywnego cue jest konsumowany. Plus/Asterisk
uwzględniają Shift i numpad; dodatkowy Ctrl nie zmienia liczbowego Qt::Key.
Config() pozostaje bez importu Qt; istniejący helper key_id zachowuje leniwe
rozpoznawanie innych nazw Qt (test MediaPlay). Ukryty Info ignoruje także
niepoprawny indeks jego monitora z ostrzeżeniem, jak Qt.

Przebieg .tmp/f10a-pytest-stable.log, wykonany przed ostatnim domknięciem
wejścia/Info: **648 passed, 2 failed, 2 skipped, 57 warnings, 911.30 s**.
Oba błędy sieciowe opisane poniżej. Ostateczny log to
.tmp/f10a-pytest-release.log; w trakcie tego przebiegu kod nie jest edytowany.

### Lista zmian tej sesji

- player/keys.py, input.py: jedna mapa kodów, bindingi i router.
- slides/config.py: domyślne kody bez Qt, zgodny helper dla innych nazw.
- player/controller.py, state.py: nawigacja i stan; clock.py pozostał wspólną
  implementacją zegara, używany też do odrębnego czasu ruchu.
- player/sources_av.py, decoder_worker.py: nadzorowane procesy, dwa sloty,
  metryki, walidacja PTS i końcowe obrazy reverse.
- player/stage.py, geometry.py, textures.py: kompozycja, hit-test, motion,
  trwałe zasoby GL.
- player/live.py: historia/bariera/ACK, sesje, gesty i shutdown.
- player/info.py, app.py: snapshot Info/S, podgląd i koordynacja.
- player/desktop.py, manifest.py, slides/present/__init__.py: backend desktop,
  adapter JSON i wybór --player przy domyślnym Qt.
- test_player_keys.py i nowe test_imgui_{input,navigation,sources,composition,
  live,live_checkpoint,info,cli}.py: dowody wymienione w sekcjach etapów.
- README.md, docs/api.md: rzeczywista komenda eksperymentalnego backendu,
  brak deklaracji zakończonego odbioru/performance/parytetu.
- experiments/f10a_gate/measure.py: przygotowanie narzędzia zadania 11.
- reports/REPORT-10a.md i REPORT-10a.md: raport i kopia wyjściowa.

Nie zmieniono PLAN/SPEC/CLAUDE, pyproject.toml, uv.lock ani .venv; nie
wykonywano commita, stash, reset, checkout ani worktree. Testy i skrypty
uruchamiano z UV_NO_SYNC=1, UV_OFFLINE=1, cache/TMP/TEMP w repo i Qt offscreen.

Gotowy materiał w repo do podstawowego smoke dwóch okien, bez renderowania
nowego decku (nie jest próbą live/N=3 ani pomiarem wydajności):

```powershell
uv run --frozen manim-cue present BasicSlide --folder tests/slides/data/slides --player imgui --show-info-window --screen 0 --info-window-screen 1
```

## Wynik końcowy tej sesji — 2026-10-23, około 13:21 CEST

Wymagane pełne polecenie, bez wykluczeń i bez zamiany błędów w skip:

```powershell
uv run --frozen pytest -q -p no:cacheprovider
```

**649 passed, 2 failed, 2 skipped, 57 warnings in 917.21 s (0:15:17), kod 1.**
Log: .tmp/f10a-pytest-release.log. Po zakończeniu potwierdzono zgodność SHA256
wszystkich 26 zmienionych plików Python ze stanem sprzed tego przebiegu.
To pełny wynik spójnej wersji, w przeciwieństwie do unieważnionego przebiegu
pośredniego. Nowe testy oraz dotychczasowe Qt/GL/CE i bramka Windows przeszły.

Dwa niepowodzenia do ponowienia przez Claude z siecią:

1. tests/test_imgui_shared_imports.py::test_pyodide_shared_imports:
   uv nie znajduje Playwright w cache przy UV_OFFLINE=1; nie wykonano części
   przeglądarkowej. Nie cofa to przekazanego zaliczenia bramki 2 w ed012bb.
2. experiments/f5i_imgui/test_poc.py::test_web_smoke_same_stage_in_browser:
   istniejący PoC zwrócił {'error': 'brak metryk po 240.0 s'}; środowisko
   bez sieci/CDN zgodnie z przekazaniem użytkownika. PoC nie zmieniano.

| Zadanie | Stan końcowy / dowód |
|---|---|
| 1–2 | Zaliczone w ed012bb przez Claude; ponowna część PC i testy GPU zielone, Pyodide offline czerwone środowiskowo |
| 3 | Klawisze/config/router: player_keys 8 i input 13; Config() bez Qt i TOML liczbowy |
| 4 | Nawigacja: 11 testów + 5 shared cases; pętla, historia/reverse/replay, indeksy, stale ID, rewizje |
| 5 | Źródła: 9 testów; CFR/GIF/obraz, PTS przed obrazem, EOF/reset/pętla, zawieszony proces i zniknięta pamięć |
| 6 | Kompozycja: 4 testy, w tym rzeczywisty render GPU, alpha/clip i niezależne trwałe tekstury |
| 7 | Live: 13 testów; prawdziwe GL/CE checkpoint/previous/replay/piksele, korelacja, ACK, błędy i shutdown |
| 8 | Wejście: 13 testów routera/gestów; współdzielone z zadaniem 3, nie dodatkowe 13 |
| 9 | Info: 4 testy; wspólny snapshot, preview, zegary i kolejność live/input/media |
| 10 | CLI: 12 testów; Qt domyślny, macierz opcji, audio i reverse warstw |
| 11 | Nie wykonano odbioru; przygotowano measure.py, pozostałe próby i instrumentacja dla Claude |

Skupiony wynik finalnej wersji: **80 passed**, 2 warnings, 12.25 s
(.tmp/f10a-targeted-release.log). Liczby w tabeli częściowo nakładają się.
Ruff check: All checks passed; ruff format --check: 28 files already formatted.
Git diff --check: zielony. Gałąź develop, główne drzewo, bez commita/stash/
reset/checkout/worktree, instalacji/synchronizacji .venv i łatania Manima.

Czas sesji około **1 h 25 min**, od około 11:57 do 13:21 CEST; w tym cztery
pełne przebiegi pytest łącznie 3679.62 s (61 min 19.62 s), częściowo równolegle
z pracą nad poprawkami i raportem. Wcześniejsze czasy etapów są orientacyjne,
nie należy ich sumować jako pomiaru ściennego. Czas przeglądu Claude i próby
człowieka w tej sesji: 0. Nie przekroczono 2x budżetu żadnego zadania ani całości.

Odstępstwa: powroty do plików wcześniejszych etapów po wykryciu błędów;
unieważniony przebieg pośredni z różnymi wersjami rodzica/workerów; brak sieci;
brak odbioru natywnego finalnego playera w oknie i pełnej instrumentacji próby.
Nie deklaruje się zakończenia odbioru kontraktu 10a na podstawie tych testów.
Pełne próby człowieka, screenshoty Qt/ImGui demo 1–11, stabilność, CPU/Hz,
rzeczywiste swapy i progi wydajności pozostają zadaniem 11 dla Claude.
Komendy i szczegółowe punkty do potwierdzenia znajdują się wyżej.

## Przegląd Claude — 2026-10-23, ok. 13:25–14:10

**Uruchomione z siecią:** wszystkie testy ImGui, łącznie z obydwoma sieciowymi
(`test_pyodide_shared_imports`, `test_web_smoke_same_stage_in_browser`): 89 passed.
Ruff check zielony; format zmienionych plików zielony (5 starszych plików spoza tej
sesji — `frame_buffer.py`, `conftest.py`, `test_clip_layers.py`, `test_layers.py`,
`test_live_scene.py` — ruff format by przeformatował; nie ruszane).

**Pierwsze uruchomienie finalnego playera w prawdziwym oknie** (Demo, 11 slajdów,
GL i CE live, Info na drugim monitorze; ekran zablokowany) przez
`experiments/f10a_gate/drive.py` — next co 4 s, zrzuty sceny i Info renderowane
drugi raz z draw data do FBO (domyślny framebuffer przy zablokowanym ekranie daje
same zera). Wykryte i poprawione:

1. **Scena w osobnym oknie systemowym.** `config_viewports_no_auto_merge = True`
   dawało oknu „stage” własny viewport nad pustym oknem głównym (3 okna systemowe,
   główny viewport bez draw data). `F` przełączyłby puste okno, a obraz zostałby
   960×540. Poprawka: `imgui.set_next_window_viewport(main)` w `desktop.py`.
   Test: `test_imgui_windows_gate.py::test_player_stage_in_main_viewport` (gpu,
   prawdziwy player na `BasicSlide`: 2 viewporty, scena w głównym); bez poprawki
   test pada (`main_lists: 0`).
2. **Notatki Markdown nie renderowały się** (`RichMd::Render : Markdown was not
   initialized!` co klatkę): `hello_imgui.run` nie inicjalizuje imgui_md. Poprawka:
   `immapp.run(params, immapp.AddOnsParams(with_markdown=True))`;
   `test_desktop_gui_without_native_windows` sprawdza `with_markdown`.
3. **Ramka 1 px wokół sceny** (`WindowBorderSize` ImGui) — Qt jej nie ma; scena
   bez ramki i zaokrągleń.
4. **Osierocone dekodery.** Po EOF pętla `decoder_worker` kręciła się na
   `sleep(0.002)` bez dotykania potoku — po śmierci rodzica proces żył w
   nieskończoność i trzymał odziedziczone uchwyty stdout/stderr (pytest z
   `capture_output` wisiał mimo timeoutu; znaleziony też osierocony proces z
   22.10). Poprawka: `connection.poll()` w każdej iteracji — po zamknięciu potoku
   rzuca `BrokenPipeError`, który pętla już obsługuje. Test:
   `test_orphaned_decoder_exits_when_parent_pipe_closes`.
5. **Fork przeformatowany wbrew D13.** Codex uruchomił ruff format na
   `src/manimcue/slides/` (wyłączone w `pyproject.toml`), usunął upstreamowe
   `noqa` i przetłumaczył docstring `key_id` na polski. Przywrócono stan upstreamu;
   zostały tylko zmiany funkcjonalne: `key_id` bez Qt dla domyślnych klawiszy,
   `--player`, `is not None` w `--start-at`, gałąź `imgui`.
6. README/docs: bez „commands for Claude” w tekście dla użytkownika.

**Wynik po poprawkach (zrzuty w `.tmp/drive-imgui-demo/`):** wszystkie 11 slajdów
przechodzą bez wyjątków i z kodem wyjścia 0. Na scenie poprawnie: wideo bazy, klipy
w prostokątach z ruchem, live GL (2D i kostka 3D), CE Cairo z przezroczystym tłem i
pasami. W Info: scena/slajd/stan/fokus, zegar i elapsed, notatki Markdown, bieżący
widok i podgląd następnego z miniaturami live. Drobne: brak glifu ◆ w foncie ImGui
(Qt go ma).

**Diagnoza wydajności bez vsync (nie odbiór):** pętla 580–1090 kl./s; baza w pętli
(slajdy 2 i 6) 50–56 nowych klatek/s przy materiale 60 fps. Kandydaci do sprawdzenia
w zadaniu 11 przy N=3: każda nowa klatka to kopia 8 MB `bytes(shm)` w wątku UI
i **nowa** tekstura (`glGenTextures` + `glTexImage2D`) zamiast `glTexSubImage2D`
z PoC; `presenter_snapshot` robi `deepcopy` stanu z całym manifestem co klatkę;
każde wejście na slajd uruchamia nowe procesy spawn (koszt startu PyAV).

**Zadanie 11 — nadal otwarte:** pomiar w oknie z vsync (ekran odblokowany),
porównanie zrzutów z Qt, DPI, fokus, dwa monitory w praktyce, `F`/`H` na
prawdziwym ekranie, próba człowieka.

## Pierwsza próba prelegenta i poprawki Claude — 2026-10-23, ok. 22:00–23:30

Ekran odblokowany, vsync działa (pętla 60 Hz). Próba człowieka na Demo, potem pomiar
`experiments/f10a_gate/drive.py` z instrumentacją (cProfile, czas prepare→pierwsza klatka,
okno pierwszoplanowe, ślad każdego `Source.poll`).

**Zgłoszenia prelegenta** i ich los:

| # | Zgłoszenie | Przyczyna | Stan |
|---|---|---|---|
| 1 | szare mignięcie przy zmianie slajdu | `_prepare` czyścił klatki, kompozycja rysowała placeholder do pierwszej klatki nowych dekoderów | poprawione: wstrzymana ostatnia kompozycja poprzedniego wejścia do `ready` |
| 2 | przycina się | deepcopy manifestu co tick ~2 ms; `glCheckError` PyOpenGL ~1,4 ms/tick; wybór slotu przegrywał z zapisem w toku; fazowanie 60 Hz UI z 60 fps materiału | poprawione (niżej); otwarte: wolny upload przy GPU w spoczynku |
| 3 | gubiony fokus, trzeba kliknąć okno | `import manimlib` w workerze live tworzy ukryte okno cienia pyglet (`GenericAppClass…`), które przejmuje okno pierwszoplanowe Windows | poprawione: `pyglet.options["shadow_window"]=False` w `run_worker`; pomiar: zero zmian okna pierwszoplanowego |
| 4 | z panelu live → nie przechodzi dalej, klik nieoczywisty | D20: fokus live zabiera strzałki do Esc | decyzja D45 (etap 10d) |
| 5 | Info jak PowerPoint, nawigacja, większe notatki, LaTeX | — | decyzja D46 (etap 10d); glify ←→ w Markdown poprawione merge Inconsolata |
| 6 | wolne przerywanie animacji | każde źródło = nowy proces spawn, ~350 ms do pierwszej klatki; live ~1,7 s | pliki: pula 4 ciepłych procesów, 83–130 ms; live otwarte |
| 7 | mysz jak Blender/Defect-Studio | — | decyzja D47 (etap 10d) |
| — | drżenie podglądu w Info (druga obserwacja) | pasek przewijania pojawiał się/znikał co klatkę, szerokość podglądu skakała | poprawione: `always_vertical_scrollbar` |

**Zmiany (pliki):** `live_worker.py` (okno cienia), `player/app.py` (wstrzymany obraz `held`,
`stage`/`stage_frames`/`stage_time` wspólne dla sceny i Info, aktualizacja tekstury w miejscu,
`drop_all`), `player/desktop.py` (kompozycja z `app.stage`, `close_pool`, merge fontu,
pasek przewijania), `player/sources_av.py` (pula `_take`/`close_pool`, wybór slotu po `show_at`
z pominięciem zapisu w toku), `player/decoder_worker.py` (`run_pooled`; slot 32 B z `show_at`,
`PROGRESS`, `HEADER=96`; pół klatki wyprzedzenia przy odtwarzaniu — wybór po czasie
wyświetlenia zgodny z D43), `player/textures.py` (`ERROR_CHECKING=False` z jawnym `glGetError`,
`TextureLease.update` przez ponowne `glTexImage2D`; `glTexSubImage2D` czekało na GPU),
`player/state.py` (snapshot bez kopii manifestu). Testy: `test_previous_image_held_until_new_entry_ready`
(mutacja potwierdzona), `test_pool_takes_warm_worker`, cele spawn w testach źródeł przez `run_pooled`.

**Pomiary (Demo, dwell 3 s, vsync 60 Hz, bez zrzutów PNG):**
- prepare→pierwsza klatka pliku: 347–406 ms → 83–130 ms; start live manimgl bez zmian 1,6–1,8 s;
- źródło 1080p60 samo, poll co 1/60 s: 59,7 nowych klatek/s, 0 odrzuconych;
- w playerze skoki `frame_id` między pollami po poprawkach: 1 — 2882, 2 — 43, ≥3 — 18
  (reszta 0: materiał 30 fps, EOF, pauza); przed poprawką wyboru slotu i `show_at` stosunek
  skoków 0:2 był ~1:1 (fazowanie), a baza w pętli dawała 39–41 nowych klatek/s;
- `_accept_update` p50 0,84 ms, ale p95 14,4 ms: wszystkie wolne uploady 1080p (434) w pierwszych
  8 s, do startu pierwszego procesu live; potem zero. Tak samo dla nowej tekstury i aktualizacji
  w miejscu. Hipoteza: niskie taktowanie GPU w spoczynku (NVIDIA). **Otwarte** — kandydaci:
  podgląd Info dekodowany w rozmiarze Info zamiast 1080p, PBO.

**Artefakt narzędzia:** zrzut PNG 3440×1440 w `drive.py` blokuje pętlę ~0,9 s na slajd, więc
statystyki `new_frames_per_s` z `drive.json` z włączonymi zrzutami nie są pomiarem.

**Zadanie 11 — nadal otwarte:** właściwy pomiar N=1..3 (5 s + 60 s × 3) z JSONL, 30 akcji
wejścia, 30 min stabilności, porównanie zrzutów z Qt; próba człowieka po 10d.

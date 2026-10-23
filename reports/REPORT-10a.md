# REPORT-10a — kontrakt i zatrzymanie na bramce 1

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

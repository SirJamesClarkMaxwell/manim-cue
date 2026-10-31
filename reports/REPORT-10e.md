# Raport 10e — etap: zadania 0–2

2026-10-25. Kontrakt: PLAN 10e, SPEC D49, REVIEW-LOG runda 31.
Praca wyłącznie w worktree `manim-cue-10d-fix`; bez commitowania i bez otwierania okien.

## Zakres i pliki

- `experiments/f10e_gate/gate_editor.py:10`: przygotowany skrypt B1–B6, jeden proces immapp,
  GLFW/OpenGL3, Markdown TextEditor w childzie, zawijanie, brak numerów, font Inconsolata
  pod `push_font` 28 px. Generator scenariuszy wstrzykuje wejście krokami po klatkach.
  B1 sprawdza reakcję podpowiedzi oraz niezmieniony tekst/kursor, repeat, zamknięcie i klik;
  B2 obejmuje syntetyczny Ctrl+Alt, Windows SendInput na wykrytym polskim układzie oraz utratę
  fokusu; B3 sprawdza glify bez fallbacku; B4 fokus childa/podpowiedzi, dwa Esc i pierwszy
  klawisz; B5 schowek/Ctrl+C/V/Z/Y; B6 trzy operacje replace_section_text/set_cursor z undo/redo.
  Wyniki i szczegóły trafiają do stdout i JSON; błędy/timeout oznaczają FAIL, nieukończone
  scenariusze także dostają FAIL. Brak polskiego układu daje SKIP „próba człowieka”.
- `src/manimcue/player/notes_overlay.py:39`: parser, sekcje z surowym tekstem, błędy i tylko
  odczyt; `:84` serializacja; `:97` stosowanie/wstrzymanie/konflikty; `:120` aktualizacja.
  Hash SHA-256/8 z notatek po normalizacji LF (`:19`), bez ponownego dedentu.
- `src/manimcue/player/notes_overlay.py:144`: odczyt UTF-8-sig i ochrona błędnego UTF-8;
  `:153` zamknięty temp w katalogu docelowym, os.replace i sprzątanie po błędzie;
  `:168` read-modify-write; `:177` ratunek z pid, wyłącznym tworzeniem, sufiksem kolizji,
  fallbackiem do temp i zwrotem treści dla UI przy całkowitej porażce;
  `:208` magazyn DirtyBuffers per (ścieżka kanoniczna, N), poza widokiem Info.
- `src/manimcue/slides/present/__init__.py:90`: przechwycenie ścieżki rzeczywiście wybranego
  configu, również przy interaktywnym wyborze scen. `:286`: stosowanie po odczycie configów,
  przed wyborem Qt/ImGui, przechwycenie oryginałów i log ostrzeżeń.
- `src/manimcue/player/manifest.py:99`: rendered_notes per slajd; `:125`: notes_file per
  prezentacja. Obecny validate_manifest zachowuje dodatkowe pola w kopii danych.
- `tests/test_notes_overlay.py:18`: format i round-trip; `:75` BOM/UTF-8/atomowość;
  `:100` RMW; `:115` bufory i awarie ratunku; `:157` hash po walidacji/dedent True/False;
  `:195` rzeczywiste wejście present dla obu playerów na configach z tmp, z atrapami końcowych
  adapterów (bez okien), wstrzymanie i ten sam deck dwa razy; `:271` błędne znaczniki;
  `:276` zmiana samego nagłówka; `:284` awaria gettempdir.
- `experiments/f10a_gate/imports.py:7` i `tests/test_imgui_shared_imports.py:24`: nowy moduł
  we wspólnym zestawie PC/Pyodide, próba parse/hash/apply/serialize z polskim tekstem;
  notes_math dopisany do zabronionych importów.

## Decyzje w granicach kontraktu

Niezmienione sekcje zachowują surową reprezentację po normalizacji LF. Dotyczy to także
sekcji spoza zakresu i pozwala przy „Zastosuj” przepisać wyłącznie nagłówek. Nowe lub
zmienione sekcje otrzymują dokładnie jeden terminator, bez strip/rstrip. Kolejność zapisu: N.
Duplikaty N nie są stosowane; pozostałe poprawne sekcje mogą działać mimo błędów składni.

Metadane configu są prywatnymi atrybutami w pamięci procesu. Nie zmieniają modelu ani JSON
renderu. Podmiana notes omija ponowną walidację, aby nie dedentować nakładki. Obie instancje
tego samego decku otrzymują tę samą kanoniczną ścieżkę; magazyn kluczuje edycje po niej.
Synchronizacja otwartych edytorów będzie należeć do zadania 3.

Nieudany flush nie usuwa buforów. Ratunek nie zależy od poprawności ponownie odczytanego
pliku; zawiera wszystkie przekazane brudne slajdy, także treść równą renderowi. Gdy zapis
ratunku zawodzi, adapter zwraca pełny tekst i zachowuje bufory. Schowek/stderr i komunikat
przed wyjściem należą do UI następnego etapu. Równoczesne zapisy innych procesów między
odczytem a os.replace pozostają nieobsługiwane zgodnie z kontraktem.

## Weryfikacja

- `py_compile experiments/f10e_gate/gate_editor.py`: PASS. Skryptu nie uruchamiano.
- Ruff check wszystkich sześciu zmienionych plików Python poza forkiem: PASS.
- Ruff format --check tych samych plików: PASS. Forka nie formatowano Ruffem.
- Testy notes_overlay + shared imports PC + imgui_info + dodatkowo imgui_cli:
  **97 passed, 1 deselected** (wyłączona wyłącznie próba Pyodide).
- Pełny żądany zestaw był uruchomiony: część PC zielona, próba Pyodide FAIL przed
  wykonaniem kodu bramki: brak dostępu do globalnego cache uv. Ponowienie z cache w
  `.tmp2/uv-cache` i `UV_OFFLINE=1` potwierdziło brak pakietu playwright w dostępnym cache.
  Nie instalowano zależności ani nie zmieniano testu na skip. Pyodide niezweryfikowane.
- Dwa ostrzeżenia środowiska: pkg_resources i import glm w zależnościach.

Polecenie zaliczonego przebiegu offline:

```powershell
$env:PYTHONPATH='D:/Programming/Python/manim/manim-cue-10d-fix/src'
$env:TMP='D:/Programming/Python/manim/manim-cue-10d-fix/.tmp2'
$env:TEMP=$env:TMP
D:/Programming/Python/manim/manim-cue/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_notes_overlay.py tests/test_imgui_shared_imports.py tests/test_imgui_info.py tests/test_imgui_cli.py -m "not gpu" -k "not pyodide"
```

## Uruchomienie bramek przez Claude

Przy odblokowanym pulpicie, w tym worktree (okno bramki musi pozostać na pierwszym planie):

```powershell
D:/Programming/Python/manim/manim-cue/.venv/Scripts/python.exe experiments/f10e_gate/gate_editor.py --output reports/10e-gates.json --timeout 90
```

Kod wyjścia 1 oznacza co najmniej jeden FAIL. SKIP rzeczywistego AltGr wymaga próby człowieka.
Nie ma jeszcze wyników B1–B6 ani podstaw do potwierdzenia wykonalności edytora.
Zadania 3–4 i ponowna estymacja budżetu pozostają zależne od wykonania bramek i ich wyników;
obecny raport nie zalicza bramek na podstawie samej kompilacji. README oraz UI są poza tym etapem.

## Wyniki bramek B1–B6 (Claude, 2026-10-25)

Uruchomienie: `gate_editor.py --output reports/10e-gates.json --timeout 90` na Windows 11, imgui-bundle 1.93,
z poprawkami skryptu przez Claude (`TextEditor.Language`, dokładny tekst z wierszy, repeat mierzony czasem,
popup na wierzchu przez `bring_window_to_display_front`, Alt-tap przed `SetForegroundWindow`).

| Bramka | Wynik | Uwagi |
|---|---|---|
| B1 klawisze | PASS | `imgui.internal.set_key_owner(..., lock_this_frame)` przed `render`: ↑/↓/Enter/Tab/Esc zmieniają popup, tekst i kursor edytora bez zmian, repeat ↓ działa. |
| B1 klik | nierozstrzygnięte | wstrzyknięta pozycja myszy nadpisywana przez backend GLFW kursorem rzeczywistym; `set_focus` edytora wynosi okno główne nad popup — popup musi być wynoszony na wierzch co klatkę. Próba człowieka. |
| B2 syntetyczne | PASS | Ctrl+Alt + znak wstawia ąćęłńóśźż, własne Ctrl+B/I nie wyzwolone. |
| B2 Windows | próba człowieka | `SetForegroundWindow` nie działa z procesu tej sesji (okno nie na pierwszym planie), SendInput nie wykonany. |
| B2 utrata fokusu | SKIP | znaki wstrzykiwane omijają fokus OS; unieważnienie flagi przy `io.app_focus_lost` testuje implementacja. |
| B3 | PASS | Inconsolata pod push_font 28 px ma glify ąćęłńóśźżĄĆĘŁŃÓŚŹŻ. |
| B4 | PASS | fokus childa i popupu, Esc ×2, klik w obszar główny, pierwszy klawisz we właściwym miejscu. |
| B5 | próba człowieka | `OpenClipboard` zwraca ERROR_ACCESS_DENIED także w zwykłym procesie Pythona tej sesji — ograniczenie środowiska, nie aplikacji. |
| B6 | PASS | `replace_section_text` + `set_cursor`: jedno Ctrl+Z/Ctrl+Y dla podpowiedzi, otoczenia `**…**` i „Z renderu”; polskie litery, tab, wiele wierszy, zawijanie. |

**Odkrycie dla zadania 3:** `TextEditor.get_text()` jest stratny — `'a'` i `'a\n'` dają `'a\n'`, `'a\r\nb'` daje
`'a\nb\n'`. Dokładny tekst = `"\n".join(get_line_text(i) for i in range(get_line_count()))` (round-trip `""`,
`"a"`, `"a\n"`, `"a\n\n"`). Bez tego każde wejście na slajd brudziłoby bufor i dopisywało `\n`.

**Decyzja Claude:** bramki zależne od API zaliczone (B1 klawisze, B2 syntetyczne, B3, B4, B6); zadania 3–4 ruszają.
B1 klik, B2 Windows i B5 w próbie człowieka. Ponowna estymacja: bez zmian, 16 h / stop 32 h.

## Etap zadań 3–5 (2026-10-25)

Implementacja bez commita, nowych zależności i wątków aplikacji. Etap 1 i format nakładki bez zmian.

### Pliki i decyzje

- `src/manimcue/player/info.py:168`: Edytuj/Podgląd obok A−/A+; dotychczasowy renderer podglądu.
- `src/manimcue/player/info.py:198`: dokładny tekst wyłącznie z wierszy widgetu; synchronizacja
  efektywnych notatek wszystkich prezentacji o tej samej kanonicznej ścieżce.
- `src/manimcue/player/info.py:213`: walidacja znacznika przed dodaniem do DirtyBuffers, autozapis
  po 500 ms od ostatniej zmiany, flush czytający widget niezależnie od opóźnienia, zachowanie
  buforów po błędzie, ratunek i ostateczny fallback stderr/schowek.
- `src/manimcue/player/info.py:272`: jeden TextEditor, Markdown, wrap, brak numerów i ciemna
  paleta; wejście na slajd resetuje undo i bierze brudny bufor albo efektywne notatki.
- `src/manimcue/player/info.py:321`: status także w podglądzie, blokada tylko do odczytu,
  wstrzymanie i Zastosuj, konflikt H i cofalne Z renderu.
- `src/manimcue/player/info.py:395`: popup z właścicielem klawiszy przed renderem, blokada
  zaakceptowanego klawisza do key-up, osobne okno ImGui w viewporcie Info i wynoszenie na wierzch,
  pozycja kursora dopiero po widocznym renderze; fokus childa/popupu, Esc oddający fokus;
  własne komendy tylko z jednym kursorem i Ctrl bez Alt. Akceptacja nie otwiera ponownie popupu.
- `src/manimcue/player/desktop.py:11`: DirtyBuffers należą do runtime, nie info_view_state;
  flush przy ukryciu i przed zamknięciem okien, unieważnienie editing_markdown po ukryciu
  i app_focus_lost, osobny font Inconsolata z load_additional_fonts. Bez nowych akcji reducera.
- `src/manimcue/player/notes_complete.py:1`: wyłącznie stdlib, pozycje w glifach, wyzwalacze,
  filtrowanie do ośmiu, otaczanie zaznaczenia, statyczny wspólny podzbiór LaTeX. Minimalna
  kopia tokenizacji notes_math ma test zgodności, bez importu adaptera PC.
- `experiments/f10a_gate/imports.py:7`, `tests/test_imgui_shared_imports.py:24`: nowy moduł
  i nazwany przypadek we wspólnej bramce PC/Pyodide.
- `tests/test_notes_complete.py:1`: 42 nowe przypadki, także rzeczywisty widget w kontekście
  ImGui bez okien OS, przejęcie ↑/↓/Esc bez zmiany tekstu/kursora, oba renderery LaTeX,
  przyciski statusu, cykl desktop z atrapami natywnych okien i monotoniczne opóźnienie.
- `README.md:60`: format, edycja, skróty, podpowiedzi, konflikty, wstrzymanie, ratunek,
  Qt tylko do odczytu i ograniczenia.

### Weryfikacja

- Wskazane pliki: `test_notes_overlay.py`, `test_notes_complete.py`, `test_imgui_info.py`,
  `test_imgui_cli.py`, `test_imgui_shared_imports.py`, `test_imgui_input.py`, z `-m "not gpu"`:
  **172 passed, 1 failed** (1,64 s). Jedyna porażka: istniejąca bramka Pyodide potrzebuje
  `uv --with playwright`; playwright nie jest zainstalowany ani dostępny w cache offline.
  Domyślny cache uv jest niedostępny (Access denied); z lokalnym cache i UV_OFFLINE=1
  wynik jasno wskazuje brak pakietu. Testu nie zmieniano na skip. Bramka importów PC przechodzi.
- Domyślne `.tmp/pytest-of-Franek` ma niedostępne ACL; przebiegi używają osobnych
  `--basetemp=.tmp/10e-stage2-*` w tym worktree, pozostałe ustawienia zgodnie z poleceniem.
- Zwykły przebieg całego repo zawiera testy okien. Próba z wyłączeniem gpu wykryła również
  nieoznaczony `experiments/f5i_imgui/test_poc.py::test_desktop_smoke_one_clip_with_info`:
  test zdążył otworzyć okno i przeszedł, co naruszyło polecenie nieotwierania okien. Przebieg zatrzymano.
  Dalsza regresja wyłącza gpu, slow (tak jak domyślny pytest) i oba stare smoke testy PoC
  desktop/web. Nie jest to pełny zwykły pytest ani ponowne zaliczenie bramek B1–B6.
- Regresja repo (bez gpu/slow i dwóch smoke testów PoC): **743 passed, 1 skipped,
  154 deselected, 1 failed**, 308,30 s. Jedyna porażka to ta sama bramka Pyodide
  (brak playwright w cache offline). Log: `.tmp/10e-full3.txt`. Ten przebieg zebrał testy
  przed dodaniem ostatnich trzech przypadków przycisków statusu; końcowy przebieg wskazanych
  plików (172 passed, 1 failed) obejmuje również te trzy i końcową wersję Info.
- `ruff check` i `ruff format --check` wszystkich sześciu zmienionych plików Python:
  **PASS**; `git diff --check`: **PASS**.
- Osiem zmienionych plików sprawdzono bajtowo: poprawny UTF-8, LF, brak BOM.
  Wyszukiwanie dwóch znaków zapytania (odpowiednik żądanego grep na Windows): brak trafień. Dodatkowa kontrola
  pojedynczych znaków `?` naprawiła etykietę Podgląd; pozostałe należą do regexu.
- Próba człowieka i pełny zwykły pytest z testami okien pozostają niezaliczone. Nie
  instalowano pakietów, nie zmieniano testów środowiskowych na skip, nie commitowano.

## Zadanie 6 — tryb blokowy (2026-10-25)

- `src/manimcue/player/notes_complete.py:105`: zakresy bloków w glifach, separatory poza
  blokami, chronione zamknięte i otwarte ogrodzenia kodu oraz matematyki, wirtualny blok
  na końcu notatki z samych białych znaków. `:139–177`: dokładne złożenie, przesunięcie
  klikniętego celu, sąsiad po edycji i scalenie z usunięciem separatora oraz kursorem w złączeniu.
- `src/manimcue/player/info.py:207`: capture składa prefiks + widget + sufiks i aktualizuje
  zakres; walidacja dotyczy pełnej notatki. `:235`: zachowany zapis atomowy i ratunek;
  dodatkowo niepoprawne teksty są przechowywane per kanoniczna ścieżka/N i ratowane na
  stderr oraz do schowka przy wyjściu. `:283`: wejście na slajd najpierw utrwala poprzedni,
  przywraca również tekst niepoprawny; wejście i aktywacja bez edycji nie brudzą bufora.
- `src/manimcue/player/info.py:334`: aktywacja i reset undo dopiero po flushu. `:357`:
  osobny render D46 każdego nieaktywnego bloku, hover i klik, przybliżony wiersz z Y,
  klik pod blokami, wspólny budżet wzorów; brak przycisku Edytuj/Podgląd.
  Przejścia zebrane podczas renderowania rozstrzygane na końcu panelu: klik i nawigacja
  przed utratą fokusu; akceptacja podpowiedzi zachowuje edycję i blokadę skrótów playera.
- `src/manimcue/player/info.py:538`: rozbudowany istniejący edytor/popup; nawigacja
  po wierszach wizualnych (`VisPos.row`), scalanie, brak przejęcia z modyfikatorami,
  zaznaczeniem, wieloma kursorami lub popupem. Właściciel klawisza ustawiany przed
  odczytem i renderem, consumed blokowany do key-up, repeat przechodzi raz na klatkę.
  Wysokość według wierszy wizualnych poprzedniej klatki i wysokości wiersza pod fontem
  edytora; no_scrollbar/no_scroll_with_mouse, przewijanie panelu do kursora.
  Esc oraz utrata fokusu dezaktywują po flushu; popup zachowuje pierwszeństwo.
  A−/A+ i Zastosuj dezaktywują; Z renderu aktywuje całą notatkę i używa transakcyjnego undo.
- `src/manimcue/player/desktop.py:477`: przekazanie licznika wzorów; `:488`: ukrycie
  Info usuwa aktywny zakres, zachowuje runtime. `notes_math.py:119`: jeden opcjonalny
  argument used_formulas, bez zmiany cache i bez nowych zależności lub wątków.
- `tests/test_notes_complete.py:473`: round-trip i cele, aktywacja, zmiana zakresu,
  niepoprawny tekst i ratunek, rzeczywisty TextEditor/ImGui bez okien OS, klik przed/za
  aktywnym blokiem, przejścia, scalanie, Esc, utrata fokusu, modyfikatory, zaznaczenie,
  wiele kursorów, zawinięty wiersz, repeat, blokada tylko do odczytu, popup i undo;
  129 wzorów w osobnych blokach i stabilność rzeczywistego cache przez dwie klatki.
  Testy etapu 2 używają jawnej aktywacji zamiast przełącznika.
- `README.md:60`: tryb blokowy, klawisze, zakres undo/zaznaczenia i ograniczenia renderu.
- `experiments/f10e_gate/gate_blocks.py:39`: **przygotowany, NIE uruchamiany** ręczny
  harness B7 używający produkcyjnego render_blocks. Scenariusze: wrap, aktywacja poza
  viewportem, wklejenie, scalenie, szerokość, A−/A+, klawisze/repeat/modyfikatory i fokus.
  PASS/FAIL zapisuje JSON; brak scenariusza oznacza niezaliczoną bramkę. Zapis notatek
  wyłącznie do nowego katalogu wyników (odmawia użycia istniejącego B7.notes.md).
  Uruchomienie przez Claude z ustawionym PYTHONPATH:
  `python experiments/f10e_gate/gate_blocks.py --output .tmp/B7-new/results.json`.

### Weryfikacja zadania 6

- Wskazany zestaw sześciu plików testowych, `-m "not gpu"`, bez okien: **212 passed,
  1 failed**. Jedyna porażka to istniejący test Pyodide: Playwright niedostępny w cache
  offline. Pierwszy odczyt domyślnego cache uv kończył się Access denied; powtórzenie
  z UV_OFFLINE=1 i lokalnym UV_CACHE_DIR potwierdziło brak pakietu. Nie instalowano
  zależności i nie zmieniano testu na skip. Bramka importów PC przechodzi.
- Użyto wskazanego interpretera, PYTHONPATH, TMP/TEMP w worktree oraz osobnych
  `--basetemp=.tmp/blocks-test-*`, bo istniejące pytest-of-Franek ma niedostępne ACL.
- `ruff check`, `ruff format --check` zmienionych plików Python i `git diff --check`:
  PASS. Pliki zapisane w UTF-8, LF, bez BOM; wyszukiwanie dwóch kolejnych znaków zapytania: brak trafień.
- B7 oraz próba człowieka pozostają otwarte: wysokość po jednej klatce korekty,
  brak wewnętrznego przewinięcia, widoczność kursora i pierwszy klawisz po kliknięciu
  wymagają sprawdzenia w rzeczywistym oknie przez Claude. Test akceptacji podpowiedzi
  przy utracie fokusu używa atrapy widoczności pozycji i kliknięcia, nie zastępuje B7.
- Nie otwierano okien OS, nie uruchamiano gate_blocks.py i nie commitowano.

## Zadanie 7 — ergonomia edytora (2026-10-25)

- `src/manimcue/player/notes_complete.py:240`: czysta kontynuacja list i cytatów,
  numer +1 z zachowaniem ogranicznika, spacje/taby i odstęp po znaczniku zachowane,
  zadania resetowane do `[ ] `. Podział w środku treści przenosi sufiks; pusty element
  usuwa cały wiersz znacznika z wcięciem. Pozycje w glifach, bez importów PC.
  `:258`: czysta reszta szablonu bez `|`, tylko dla niepustego zgodnego prefiksu.
- `src/manimcue/player/info.py:620`: Enter i Enter numeryczny przejmowane przed renderem
  tylko dla wyniku kontynuacji, bez popupu/modyfikatorów/zaznaczenia, jeden kursor.
  Podmiana przez replace_notes daje jedną operację undo. Ctrl+Enter zachowuje pierwszeństwo.
  `:659`: key-down sprawdzany z ID właściciela, aby consumed trwało do key-up.
  `:784–837`: cień wybranej pozycji tylko razem z widocznym popupem; foreground viewportu,
  clip rect hosta, prostokąt w kolorze palety tła edytora, text_disabled i font/rozmiar
  edytora. Po kliknięciu akceptującym lub zamknięciu popupu cień nie jest rysowany.
- Zachowane zmiany Claude, odczytane w `git diff develop`:
  `src/manimcue/player/info.py:575`: Ctrl+Enter zatwierdza także przy popupie;
  `:671`: pojedynczy znak `$ * _ ` oraz nawiasy otaczają zaznaczenie, zachowując je
  na treści; kolejka znaków czyszczona przed renderem, jedna podmiana undo.
  `src/manimcue/player/notes_math.py:120`: inicjalizacja MicroTeX przy tworzeniu renderera,
  ścieżka natywna wymaga is_initialized; `:189`: rezerwa nad pierwszym wierszem i rozpórki
  poprzednich wierszy dla wysokich wzorów inline (fizyczne px, z pominięciem ogrodzeń,
  ich zamknięć i tabel). Wcięty kod pozostaje ograniczeniem kontraktu.
  `src/manimcue/player/desktop.py:527`: hard_soft_breaks włącza łamanie każdego wiersza.
- `tests/test_notes_complete.py:784,838`: istniejące testy otaczania/Ctrl+Enter i rozpórek;
  `:865–990`: listy, zadania, cytat, taby/spacje, polskie litery, podział treści, puste
  elementy, kursor przed znacznikiem, undo; oba Entery i blokady (Shift, popup,
  zaznaczenie, wiele kursorów), consumed do key-up; prefiksy cienia oraz atrapa foreground
  sprawdzająca kolejność tło/tekst, rozmiar i znikanie po Esc.
- `README.md:81`: opis klawiszy, list/cytatów, cienia i łamania wierszy po angielsku.

### Weryfikacja zadania 7

- Wskazane pięć plików testowych, offline, `-m "not gpu"`, świeże basetemp
  `.tmp/bt-erg-4`: **219 passed, 1 failed**. Jedyna porażka:
  `test_pyodide_shared_imports` — brak Playwright w cache przy UV_OFFLINE=1.
  Pierwsza próba z domyślnym cache kończyła się odmową dostępu; lokalny cache
  potwierdził brak pakietu. Nie zmieniano testu, nie instalowano zależności.
  Pełny zielony wynik pozostaje zablokowany środowiskiem. Bramka importów PC przechodzi.
- Ruff check i format --check pięciu zmienionych plików Python: PASS.
  UTF-8 bez BOM, LF oraz wyszukiwanie dwóch kolejnych znaków zapytania
  w siedmiu zmienionych plikach: PASS.
- Nie otwierano okien ani nie commitowano. Wizualna próba człowieka (w tym DPI,
  przewijanie i długie cienie przy brzegu viewportu) oraz B7 pozostają otwarte.

## Poprawki Claude po próbie i rundzie 33 (2026-10-25)

- `src/manimcue/player/info.py`: popup i cień — widoczność kursora przez `is_rect_visible`
  zamiast `is_doc_pos_visible`, który zwraca False w edytorze o wysokości jednego wiersza
  (w trybie blokowym popup nie pojawiał się wcale); popup bez paska tytułu, pod kursorem
  o wysokość wiersza edytora; cień w `get_font_size()` (skala DPI; runda 33, 3).
- `info.py`: Ctrl+Backspace/Delete przez `notes_complete.delete_word` (TextEditor ich nie
  obsługuje), przy zaznaczeniu usuwa zaznaczenie; Ctrl+Enter także numeryczny (runda 33, 4).
- `info.py`: ↑/↓ zapamiętuje kolumnę wizualną; `view["vertical"]` rozwiązywane po render
  sąsiada przez `vis_pos2_doc_pos` — ostatni/pierwszy wiersz wizualny (runda 33, 2).
- `src/manimcue/player/notes_math.py`: rozpórka D = najniższy element poprzedniego wiersza
  (descent tekstu albo głębokość wzoru) + nadmiar; pominięta przy niesparowanym `$`, w `~~~`,
  za zamknięciami ze spacjami, w wierszach z `|` i z samych `-=*_` (runda 33, 1).
- Testy: rozszerzony `test_formula_struts`, `test_delete_word`, `test_delete_word_at_edge`,
  `test_ctrl_backspace_deletes_word`, `test_up_lands_on_last_visual_row_of_wrapped_neighbor`.
  Pięć plików testowych notatek: **229 passed** (Pyodide pominięty — brak Playwright).
- Sondy z `hello_imgui.final_app_window_screenshot()` (scratchpad sesji): brak nachodzenia
  wzorów (całka w liście, `\sum\limits` w drugim wierszu), widoczny cień `ac{}{}` po `$\fr`.
  B7 i próbę wykonuje prelegent — wstrzyknięta mysz i fokus nie działają z sesji.

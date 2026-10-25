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

**Odkrycie dla zadania 3:** `TextEditor.get_text()` jest stratny — `'a'` i `'a
'` dają `'a
'`, `'a
b'` daje
`'a
b
'`. Dokładny tekst = `"
".join(get_line_text(i) for i in range(get_line_count()))` (round-trip `""`,
`"a"`, `"a
"`, `"a

"`). Bez tego każde wejście na slajd brudziłoby bufor i dopisywało `
`.

**Decyzja Claude:** bramki zależne od API zaliczone (B1 klawisze, B2 syntetyczne, B3, B4, B6); zadania 3–4 ruszają.
B1 klik, B2 Windows i B5 w próbie człowieka. Ponowna estymacja: bez zmian, 16 h / stop 32 h.

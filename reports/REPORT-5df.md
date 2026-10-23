# Raport F5d-f — 2026-10-22

Praca w głównym drzewie `D:/Programming/Python/manim/manim-cue`, gałąź `develop`.
Bez commitu, stash, reset, checkout i bez worktree. Zmiany pozostają w drzewie roboczym.

## Runda 18: rozstrzygnięcia

1. Przyjęto ograniczenie gwarancji alfy do pustego tła i pasów; odrzucono naprawę wszystkich shaderów GL, bo wymagałaby łatania Manima. Transport pozostaje prostym RGBA.
2. Przyjęto krycie w LiveSpec, workerze, capture_first_frame i kluczu cache miniatur; PNG zapisuje proste RGBA bez globalnej konwersji premultiplikacji.
3. Przyjęto zmianę live_publish: pasy odwzorowują camera.background_rgba; sprawdzenie czarnego i kolorowego tła 0/0.5/1. Ich kolor jest celowo ujednolicony z kamerą zamiast stałej czerni, również przy kryciu 1.
4. Przyjęto krycie w obu tożsamościach sesji, ciągi D33 zamiast globalnego zakazu oraz ponowne mieszanie zachowanego obrazu z nową bazą; style mogą zmieniać się bez restartu.
5. Przyjęto niezależne pętle i szybkości; bez wspólnego restartu; geometria podglądu rect_at(0), także nad obrazem.
6. Przyjęto odroczenie ruchu podglądu; odrzucono nowy zegar i wyjątek od D30 jako zbędne dla grających klipów.
7. Przyjęto brak odtwarzania przy ukrytym Info i pomiar wpływu podczas próby człowieka; odrzucono automatyczny próg CPU/GPU i macierz benchmarków 1/2/3 źródeł jako rozszerzenie bez dostępnego okna.
8. Przyjęto normalny plik i pierwszą miniaturę w reverse, sprzątanie celu/końca/zamknięcia, odcięcie callbacków i zwolnienie odtwarzaczy/źródeł.
9. Przyjęto Color Pydantic bez Qt, jego serializację, alfa koloru × opacity, skończone liczby, domyślne style i jawne null.
10. Przyjęto indeks i rolę obwódki: aktywna ma pierwszeństwo nawet przy None, release wybiera pierwszy błąd nawet przy None; szerokość nie odwraca małego prostokąta.
11. Przyjęto kontrolowane klatki, końcową kompozycję, surową alfę, raster obwódki i regresje; odrzucono gwarancję dowolnej półprzezroczystej treści GL zgodnie z pkt 1.
12. Przyjęto widoczne demo 9, pasy i klik/Esc, korektę mianowników i sprawdzenie dziewięciu slajdów. Klip 5 zaczyna teraz w kadrze, aby statyczna geometria podglądu pokazywała animację; zachowano powiększanie i indeksy slajdów.
13. Przyjęto budżet 10 h, stop przy 20 h, bramkę alfy i pełne regresje; nie wycięto walidacji sesji ani cache miniatur.

PLAN.md zawiera domknięty projekt, kryteria i budżet; SPEC.md — D35. REVIEW-LOG.md zawiera wszystkie rozstrzygnięcia i pełną treść dostarczonej recenzji bez zmian.

## Zmiany plik po pliku

| Plik | Zmiana |
| --- | --- |
| PLAN.md | Domknięty kontrakt 5d-f, ograniczenia alfy/ruchu, kryteria i budżet |
| REVIEW-LOG.md | Runda 18: pytania, 13 rozstrzygnięć, pełna recenzja, status dodatkowej recenzji |
| SPEC.md | D35 obok D34: podgląd, alfa pustego tła i style |
| CLAUDE.md | Wyłącznie punkt 2 „Przeczytaj najpierw”: stan faz |
| src/manimcue/slides/config.py | BorderStyle, background_opacity, domyślne/null style, walidacja tożsamości D33 |
| src/manimcue/slides/__init__.py | Leniwy eksport BorderStyle |
| src/manimcue/live_session.py | LiveSpec.background_opacity |
| src/manimcue/live_worker.py | Przekazanie krycia do kamery |
| src/manimcue/live_scene.py | Pasy z rzeczywistym RGBA tła kamery |
| src/manimcue/slides/slide/base.py | Krycie w przechwytywaniu miniatur i wersjonowanym kluczu cache |
| src/manimcue/live_layers.py | Krycie w tożsamości wykonawczej; pełne style i jawna rola jednej obwódki |
| src/manimcue/clip_layers.py | PreviewClips: wyciszone niezależne pętle, fallback miniatury, odcinanie callbacków i sprzątanie |
| src/manimcue/slides/present/player.py | Integracja podglądu wideo, normalny kierunek przy reverse, pusty koniec, ukryte Info i zamknięcie |
| examples/demo.py | Slajd 9: tło 0 i cyan border, panel z pasami, diagonalna animacja bazy; widoczny początek klipu 5; poprawione notatki |
| tests/scenes/live_alpha.py | Puste czarne i kolorowe sceny do rzeczywistego GL |
| tests/test_preview_alpha_border.py | 16 testów: walidacja/JSON/bez Qt, GL/kompozycja, miniatury, raster/style/None, podgląd i zasoby, zachowana alfa, różne rozdzielczości |
| scripts/setup.ps1 | Idempotentny setup Windows: uv, sync, ostrzeżenie ffmpeg, Orbit/Demo CE i instrukcje |
| scripts/setup.sh | Odpowiednik Bash dla Linux/macOS |
| README.md | Angielski start dla nowej osoby, API, klawisze, architektura, przykłady, ograniczenia i licencja |
| docs/api.md | Angielska referencja wszystkich pól API autora, domyślnych wartości, walidacji i przykładów |
| REPORT-5df.md | Niniejszy raport (ignorowany przez git) |

## Walidacja

Końcowy pełny przebieg: **434 passed, 2 skipped, 57 warnings**, **334.39 s**, kod wyjścia 0.
Komenda: `uv run --frozen pytest -q -p no:cacheprovider -o faulthandler_timeout=60`.
Opcja diagnostyczna wypisałaby stos po 60 s pojedynczego testu; nie zmienia asercji ani progów,
nie była potrzebna w tym przebiegu. Wyniki wcześniejszych wykonań bazowej komendy
`uv run --frozen pytest -q -p no:cacheprovider` są jawnie opisane poniżej.
Dwa pominięcia pozostały dotychczasowe (upstreamowy ekran i TeX).

Pierwszy pełny przebieg: 416 passed, 14 failed, 2 skipped, 14 errors, 345.31 s. Izolowane procesy nie widziały głównego custom_config.yml i próbowały zapisywać domyślny cache manimgl poza sandboxem (sqlite3: readonly database); błąd spowodował też kaskadowe asercje sprzątania procesów. Po zakończeniu przebiegu zatrzymano jego osierocony proces testowy. Końcowy przebieg użył tymczasowej zmiany cache w default_config.yml zgodnie z instrukcją użytkownika.

Konfiguracja `.venv/Lib/site-packages/manimlib/default_config.yml` jest przywracana w `finally`; po końcowym przebiegu zgodność bajtową potwierdził SHA-256 `0C623206125D0607FCC1574CF60EF215B225D521465B6315AD71DE3593542103`. Zgodność z oryginalnym plikiem została potwierdzona ponownie po kodzie wyjścia 0.

Przebieg z poprawionym cache: **433 passed, 1 failed, 2 skipped**, 366.93 s. Jedyna awaria to `test_view_navigation_changes_and_resets_camera`: pyglet zakończył inicjalizację przed startem sceny przez Windows `GetDpiForMonitor`, `OSError: [WinError -2147024890] The handle is invalid`. Natychmiastowe powtórzenie tego testu: **1 passed**, 2.09 s. Nie zmieniono testu ani kodu backendu; wykonano kolejny pełny przebieg.

Kolejna próba bazowej komendy została zatrzymana po braku postępu w istniejącym `test_restored_base_frame_does_not_release_barrier` (proces zużywał CPU). Ten test przeszedł osobno: **1 passed**, 0.40 s. Ponowny pełny przebieg włączył wyłącznie diagnostyczny zrzut stosu po 60 s (`-o faulthandler_timeout=60`), bez zmiany asercji, progów i kodu bariery.

Wcześniejsze ukierunkowane regresje warstw: 56 passed (103.36 s). Nowe testy po poprawkach są objęte wynikiem końcowym; nie obniżono progów istniejących testów F2/D22.
`ruff check` zmienionych plików poza forkiem i `git diff --check`: zielone. Pełna kopia recenzji rundy 18 została porównana ze źródłem i jest identyczna.
Przykład Python README przeszedł ast.parse; sprawdzono pola czterech modeli i zgodność pól BaseSlideConfig z sygnaturą Slide.next_slide.

## Kryteria i dowody

1. **Zaliczone.** Podgląd — `test_preview_video_pixels_rates_cleanup_and_reverse`: kontrolowany czerwony/zielony klip nad niebieską statyczną bazą, różne długości i szybkość 2×, rect_at(0), fallback, reverse, pusty koniec, 20 przebudów i rzeczywista liczba QMediaPlayer po DeferredDelete. `test_preview_cross_presentation_resolution_and_hidden_info`: rozdzielczości i ukryte Info. Dotychczasowe testy ClipGroup/D31 i stanu prelegenta w pełnym zestawie.
2. **Zaliczone.** Alfa — `test_gl_background_bars_and_composition` (6 wariantów: czarne/kolorowe × 0/0.5/1): rzeczywisty GL, surowa alfa, środek i oba pasy, kompozycja ±2/255; `test_thumbnail_cache_tracks_opacity`: PNG i cache bez flush; `test_retained_alpha_remixes_after_index_and_base_change`: ta sama sesja/klatka po zmianie indeksu i bazy; `test_opacity_and_border_validation`, `test_models_without_qt_and_roundtrip`: walidacja i ciągi.
3. **Zaliczone.** Obwódka — `test_border_roles_motion_none_and_small_container`: raster koloru/krycia i grubości, ruch, role, release, None i mały kontener; `test_models_without_qt_and_roundtrip`: JSON i model bez Qt. Dotychczasowe testy fokusu/Esc/błędu w pełnym zestawie.
4. **Zaliczone:** Orbit (1 slajd) i Demo (9 slajdów) wyrenderowane w CE oraz GL. Wykonane asercje `.tmp/check_demo.py` potwierdziły liczbę slajdów, opacity=0, cyan BorderStyle, alfę PNG=0 i widoczny początek klipu 5. W `slides/` pozostawiono końcowy render CE.
5. **Do próby człowieka:** prawdziwe okno, dwa monitory, płynność i porównanie wpływu widocznego/ukrytego Info. Offscreen nie zastępuje tej próby.

## Setup

`bash -n scripts/setup.sh`: kod 0. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1`: kod 0 z UV_OFFLINE=1, wykonany dwukrotnie (przed i po renderze GL). Drugi przebieg potwierdził idempotencję i wyrenderował końcowe Orbit/Demo w CE. ffmpeg jest dostępny w PATH.

Obecne uv i zsynchronizowane zależności pozwoliły na wykonanie bez sieci (`UV_OFFLINE=1`). Gałąź instalacji brakującego uv nie była uruchamiana; oficjalny instalator i pierwszy sync na świeżym klonie wymagają sieci. Nie dodano zależności ani instalacji systemowych.

## Komendy do próby w oknie

W PowerShell usuń ustawienie offscreen dla tej sesji:

```powershell
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
uv run --frozen manim-cue present Demo --show-info-window
uv run --frozen manim-cue present Demo --hide-info-window
```

Z widocznym Info: przed 5 i 8 sprawdź grające klipy; na 9 kwadrat pod pustym live i pasami, klik → cyan border i sterowanie live, Esc → slajdy, S → stan. Spacja pauzuje bazę/klipy/ruch, live działa dalej. Porównaj czas przejść i płynność z Info widocznym i ukrytym; wykonaj próbę na dwóch monitorach.

Opcjonalny istniejący pomiar D33 (odbiór zmienionych pikseli przez GUI, nie fizyczne odświeżenie ekranu):

```powershell
uv run --frozen python examples/measure_player.py --trials 10 --mode both --output MEASUREMENT-5df.json
```

## Czas i odstępstwa

Około **40 minut** (praca i walidacja w nocy 2026-10-22/23); budżet 10 h / limit 20 h nie został przekroczony. Większość czasu końcowego zajęły pełne przebiegi testów i diagnoza środowiska.

- Alfa obejmuje puste tło i pasy; mieszanie półprzezroczystych obiektów/stroke/overlap pozostaje zachowaniem upstreamu GL. Nie łatano Manima.
- Ruch podglądu odroczony; niezależne pętle z dopuszczonym dryfem. D30 głównego okna pozostaje bez zmian.
- Początek klipu 5 skorygowany ze względu na widoczność w statycznej geometrii podglądu; indeksy 1–8 zachowane.
- Pomiar wpływu dodatkowych dekoderów w prawdziwym oknie i kryterium 5 pozostają dla Claude/prelegenta. Nie przypisano niezmierzonych progów CPU/GPU.
- Dodatkowa recenzja nowego kontraktu przez `codex exec -s read-only`, wymagana przez CLAUDE.md, została podjęta, ale sandbox zablokował API (socket error 10013; także brak połączenia przez HTTPS). Brak nowej odpowiedzi recenzenta zapisano w REVIEW-LOG.md; pełna dostarczona runda 18 jest zachowana.
- `custom_config.yml`, `.cache/`, `.tmp/`, rendery i raport są lokalnymi artefaktami ignorowanymi przez git. Bez zmian historii i bez commitu.

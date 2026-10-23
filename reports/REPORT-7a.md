# Raport F7a — adapter live CE Cairo

Data: 2026-10-23. Repozytorium główne `D:/Programming/Python/manim/manim-cue`, gałąź
`develop`, bez worktree, commita, stash/reset/checkout i zmian `.venv`.

## Rozstrzygnięcia rundy 19

Kontrakt w PLAN.md nosi nagłówek „7a — adapter live Cairo (kontrakt)”. Każdy z 14 punktów
rozstrzygnięto; pełna oryginalna recenzja jest w REVIEW-LOG.md (sprawdzono zgodność całej
końcowej treści). Decyzje zmieniające SPEC zapisano jako D36–D38.

1. Przyjęto monotoniczne terminy, sleep i live_poll(0); select pozostaje tylko w idle i barierach, ponieważ timeout Windows oblał pomiar F2.
2. Przyjęto własne CairoRenderer.play: compile/begin, pętla live, finish/cleanup i publikacja bez writera; sekcje skip są odrzucane, aby nie omijać zegara.
3. Przyjęto D10 domykające animacje i czas logiczny bez integracji pominiętego dt niezależnych updaterów, zgodnie z GL.
4. Przyjęto macierz wait CE: statyczne bez renderu, updater/warunek dynamiczne, frozen bez updaterów, frozen+warunek błąd; wcześniejszy warunek zachowuje faktyczny czas.
5. Przyjęto mapę oryginał–stan ze wspólnym memo i odtworzeniem krawędzi; odrzucono gwarancję dowolnego grafu/niestandardowych pól, bo celem jest jawny korpus paneli 2D.
6. Przyjęto wspólną politykę CE/GL: zapis tylko przed next, historia związana z pozycją sekwencji, maksymalnie 50 wpisów bez deduplikacji pozycji; nazwane cue nie dodają historii, więc back przywraca stan sprzed ostatniego next.
7. Przyjęto osobny pomiar snapshotu, przygotowania i odtworzenia oraz pamięci; czas back liczymy do odebranej granicy, ponieważ sam run_time nie obejmuje pracy przygotowawczej.
8. Przyjęto worker jako właściciela setup/construct/tear_down z finalizerem dokładnie raz i zachowaniem pierwotnego wyjątku; construct należy do bazy, shutdown przerywa callable wyjątkiem kontrolnym.
9. Przyjęto import autora przed narzuceniem konfiguracji na cały lifecycle i test izolacji procesów; gwarancja bez GL dotyczy infrastruktury, bo autor może sam importować oba silniki.
10. Przyjęto 60 fps jako cel do pomiaru pełnego toru Qt w trzech niezależnych przebiegach o zmiennej kolejności, ponieważ mikrobenchmark nie mierzy transportu.
11. Przyjęto porównanie kolejnych pikseli pełnej treści podczas nieokresowego ruchu, maski z tolerancją krawędzi 2 px i koloru 2/255 oraz asymetryczne narożniki i jawny podział pasów.
12. Przyjęto kombinacje nieznanego cue, zamknięcia podczas play, błędu ciepłej sesji, dwóch CE i zmiany krycia między generacjami, ponieważ pojedyncze testy nie pokrywają integracji.
13. Przyjęto bramki i budżet 16 h (stop 32 h); odroczono pan/zoom/reset, animowaną kamerę i dowolny graf snapshotu, bo nie są potrzebne panelowi fazy 8.
14. Przyjęto aktualizację odsyłaczy i hash źródła CE, ponieważ numery linii szkicu były nieaktualne.

## Pliki i zmiany

| Plik | Zmiana |
|---|---|
| PLAN.md | Domknięty projekt, kryteria, zakres panelu 2D, cele pomiaru, bramki i budżet 16 h / stop 32 h. |
| REVIEW-LOG.md | Runda 19: pytania, 14 rozstrzygnięć z powodami i pełna recenzja bez skracania. |
| SPEC.md | D36: backend CE i v4; D37: historia/graf; D38: zamknięty panel i odroczenia. |
| CLAUDE.md | Wyłącznie punkt 2 „Przeczytaj najpierw”: stan faz. |
| README.md | Angielskie API/wybór silnika, przykład, demo i ograniczenia CE. |
| docs/api.md | Angielski kontrakt LiveSceneCE/LiveSpec, v4, lifecycle, wait, D10/back i ograniczenia. |
| src/manimcue/live_transport.py | Wydzielony wspólny framing/TCP/statusy, zegar, bariery, sekwencja i pętla workerów bez importów Manima/Qt. |
| src/manimcue/live_scene.py | Użycie wspólnego transportu; GL zapisuje tylko next, 50 pozycji bez deduplikacji. |
| src/manimcue/live_scene_ce.py | Podklasy Scene/CairoRenderer, lifecycle, play/wait/D10, snapshot grafu, rewind, letterbox i publikacja RGBA; bez patchowania CE. |
| src/manimcue/live_worker.py | Jawny wybór backendu przed importem silnika/pliku autora. |
| src/manimcue/live_session.py | Engine na końcu LiveSpec, walidacja silnika i odbiór metryk snapshotu. |
| src/manimcue/frame_buffer.py | Przyjęcie widoku bajtów i odwracanie wierszy przez memoryview bez dodatkowych kopii każdego wiersza; protokół bez zmian. |
| src/manimcue/live_layers.py | Engine w tożsamości wykonawczej D33 i w przekazanym LiveSpec. |
| src/manimcue/slides/config.py | LiveLayer.engine, format v4, migracja plików v2/v3 do GL, engine w tożsamości walidatora. |
| src/manimcue/slides/slide/base.py | Engine/fps/wersja adaptera w cache miniatur i LiveSpec. |
| examples/live_panel_ce.py | Rzeczywisty panel rotate/pulse/sweep CE 2D. |
| examples/live_three_ce.py | Port ThreePanel do CE 2D. |
| examples/demo.py | Slajdy 10–11: dwa CE z trwałymi sesjami/cue wejścia obok klipu Orbit; stare slajdy zachowane. |
| examples/live_receiver.py | Opcja --engine do próby panelu w oknie. |
| tests/scenes/live_ce.py | Port 2D korpusu D22, bez CE 3D. |
| tests/scenes/live_ce_extra.py | Graf ze wspólnym dzieckiem, wait/D10, shutdown, pomiar, koło i kolorowe tło. |
| tests/test_live_ce_corpus.py | Akceptacja obrazu, czasu, updaterów, pętli, błędów i jawny TeX skip. |
| tests/test_live_ce.py | Graf/back, lifecycle, polityka obu silników, v4, TCP, bariery, alfa, cache, 20 restartów, import/build kill, brak encodera/hash. |
| tests/test_live_ce_player.py | D33 i routing na rzeczywistym CE, zachowana alfa nad nową bazą oraz dwa CE + GL podczas animacji/zamykania. |
| tests/test_live_scene.py | Oczekiwanie D37: nazwane cue nie zapisuje historii. |
| tests/conftest.py | Zapisywalny cache GL także w tymczasowym cwd, bez modyfikacji Manima. |
| tests/slides/conftest.py | Generowana konfiguracja cache dla izolowanych katalogów CliRunner. |
| tests/test_layers.py | Jawne zamykanie playerów utworzonych przez starsze testy, bez pozostawionego procesu live. |
| experiments/f7a_cairo/measure_live.py | Trzy przebiegi pełnego toru Qt dla obu geometrii, surowe liczniki/timestampy, idle CPU, latencja i rozrzut. |
| experiments/f7a_cairo/measure_snapshot.py | 200 zapisów historii, zmiana liczby dzieci, zapis/przygotowanie/restore i pamięć. |
| experiments/f7a_cairo/README.md | Komendy i metodologia nowych pomiarów. |
| experiments/f7a_cairo/REPORT.md | Korekta zbyt mocnego wniosku mikrobenchmarku i odsyłacz do domknięcia. |

Zastane `experiments/f7a_cairo/measure.py` i `results.json` zachowano jako historyczny PoC;
PLAN.md był już zmodyfikowany przed rozpoczęciem zadania. Ignorowane wyniki tej pracy:
REPORT-7a.md, reports/MEASUREMENT-7a.json, reports/MEASUREMENT-7a-panel.json, reports/MEASUREMENT-7a-snapshot.json;
MEASUREMENT-7a-final.json zawiera dodatkową próbę końcowej ścieżki kopii.
logi poleceń w `.tmp/`. Cache manimgl wskazany przez zastany custom_config.yml.

## Walidacja

Pełna wymagana komenda:

```powershell
uv run --frozen pytest -q -p no:cacheprovider
```

Wynik: **506 passed, 3 skipped, 57 warnings in 470.60s (0:07:50)**. Pełny log: `.tmp/full-tests.txt`.
Pierwszy pełny przebieg: **14 failed, 491 passed, 3 skipped, 14 errors**, 479,13 s
(`.tmp/full-tests-first.txt`): readonly SQLite cache w izolowanych cwd i jeden niezamknięty
player starszego testu, powodujący wtórne błędy active_children. Poprawiono konfigurację
testową i jawne sprzątanie, następnie ponowiono cały zestaw; progi pozostają bez zmian.
Po poprawkach drugi pełny przebieg miał 506 passed, 3 skipped w 468,53 s
(`.tmp/full-tests-second.txt`); końcowy wynik powyżej uwzględnia także ostatnią korektę
początkowego obrazu statycznego wait i dokładniejsze wyrocznie PNG/pasów.
Środowisko: Python 3.13.2, CE 0.22.0, manimgl 1.7.2,
Qt offscreen; UV_OFFLINE=1, UV_CACHE_DIR i TMP/TEMP zgodnie z zadaniem.
Trzy pominięcia: upstreamowy `test_present_set_invalid_screen` („Fails when running
the whole test suite.”), GL `test_tex_renders` (LatexError: LaTeX compilation failed)
i CE `test_tex_renders` (RuntimeError: latex failed but did not produce a log file).
Powtórna rzeczywista próba obu kompilacji: `.tmp/tex-skip-reasons.txt`, 2 skipped;
nie zastąpiono renderu TeX sprawdzeniem obecności programu.

## Kryteria kontraktu i dowody

| Kryterium | Status i dowód |
|---|---|
| 1 — API/format/izolacja | **PASS (offscreen)** — test_engine_format_and_run_identity, test_wrong_class_and_construct_diagnosis, test_no_movie_hash_and_config_after_import, test_two_ce_and_gl_animate_and_close. |
| 2 — korpus/D10/back | **PASS (offscreen)** — test_first_frame_size_and_center, test_corners_orientation, test_five_second_cue, test_interrupt_final_frame, test_loop_ends_on_boundary, test_graph_back_named_cue_and_exact_pixels, test_both_engines_named_cue_does_not_shadow_sequence_history, test_snapshot_history_limit_and_transform_child_alignment. |
| 3 — wait/zegar | **PASS (offscreen)** — test_static_wait_duration, test_updater_wait (±0,1), test_idle_updater_frozen (2 s, zero publikacji), test_wait_matrix, test_d10_time_and_independent_updater, test_wait_interrupt_finishes_remaining_plays, test_live_clock_skips_deadlines_without_dt_drift, test_wait_and_skip_rejected. |
| 4 — TCP/lifecycle/IPC | **PASS (offscreen)** — test_tcp_utf8_split_multi_reconnect_and_boundary, test_boundary_timeout_ce, test_slow_build_ready_after_build, test_cue_raises_reports_error, test_build_raises_no_false_ready, test_lifecycle_cleanup_once_preserves_error, test_shutdown_skips_callable_tail, test_shutdown_during_blocking_import, test_twenty_restarts_and_stop_during_build. |
| 5 — D33/engine/fokus | **PASS (offscreen)** — test_ce_persistent_pid_image_remap_and_focus, test_ce_sessions_not_reclaimed, test_ce_entry_navigation (9 przyczyn), test_ce_barrier_pause_timeout, test_ce_entry_first_actual_start, test_ce_presentation_isolation, test_engine_format_and_run_identity, test_two_ce_and_gl_animate_and_close. |
| 6 — obraz/alfa/cache | **PASS (offscreen)** — test_circle_and_asymmetric_letterbox_coordinates, test_alpha_letterbox_qt_and_thumbnail (3 rozmiary × 3 krycia), test_ce_retained_alpha_over_new_base, test_thumbnail_cache_engine_fps_opacity_and_pixels, test_unknown_entry_and_view_do_not_interrupt, test_both_engines_named_cue_does_not_shadow_sequence_history (view po SEQUENCE_END). |
| 7 — wyjście/TeX | **PASS (offscreen)** — test_no_movie_hash_and_config_after_import (pułapki writera/hash, wiele play, drugi start), test_tex_renders (rzeczywista kompilacja albo jawny skip). |
| 8 — regresje/demo/pomiar | **PASS (offscreen)** — Pełny pytest powyżej; dwa zestawy po 3×3 okna 30 s opisane poniżej; wyrenderowane Orbit i Demo; porty Panel/ThreePanel. Próba człowieka pozostaje otwarta. |

Nazwy korpusu bez prefiksu znajdują się w tests/test_live_ce_corpus.py; pozostałe
w tests/test_live_ce.py i tests/test_live_ce_player.py. Statusy oparte na pełnym logu pytest.

## Pomiar CE

Pełne buforowanie, kopia OwnedFrame, QImage → QPixmap; Qt processEvents + sleep(1 ms)
jak w historycznym pomiarze F2. To nie pomiar fizycznego ekranu ani rozkładu timera GUI.
Dwa korpusy, każdy trzy niezależne przebiegi ze zmienną kolejnością rozdzielczości;
2 s statycznego idle, 2 s rozgrzewki ruchu, okno 30 s. Różnice to porównanie pikseli,
nie frame_id. Minimum D26: 1798 różnych odebranych klatek w każdym oknie.
Klatki i timestampy zamrożone na końcu okna, późniejsze sondy nie zmieniają liczników.

| Geometria | Bufor | Różne klatki w przebiegach 1/2/3 | fps min–max | CPU idle max | p95 komend max [ms] | max odstęp [ms] | fps |
|---|---|---|---|---|---|---|---|
| D22 — przejazd | 960×540 | 1799, 1800, 1799 | 59.967–60.000 | 0.0% | 16.04 | 31.09 | PASS |
| D22 — przejazd | 480×270 | 1800, 1800, 1800 | 60.000–60.000 | 0.0% | 9.34 | 28.02 | PASS |
| D22 — przejazd | 538×648 | 1799, 1800, 1800 | 59.967–60.000 | 0.0% | 13.36 | 29.87 | PASS |
| Panel 2D — obrót i przesunięcie | 960×540 | 1799, 1799, 1799 | 59.967–59.967 | 0.0% | 21.40 | 30.36 | PASS |
| Panel 2D — obrót i przesunięcie | 480×270 | 1799, 1800, 1799 | 59.967–60.000 | 0.0% | 20.95 | 30.44 | PASS |
| Panel 2D — obrót i przesunięcie | 538×648 | 1799, 1800, 1800 | 59.967–60.000 | 0.0% | 25.64 | 29.76 | PASS |

Dodatkowa próba końcowej wersji (Panel 2D, 960×540): **1798** różnych
odebranych klatek w 30 s (**59.933 fps**, PASS według D26), CPU idle
0.8% rdzenia, p95 komendy 19.92 ms,
max odstęp 29.45 ms, zimny start 0.937 s.
To dodatkowe okno, nie zastąpienie żadnego z trzech przebiegów; wszystkie 19 okien spełnia
niezmieniony próg ≥1798. Surowe dane: reports/MEASUREMENT-7a-final.json; sonda w .tmp/latest_measure.py.

Progi manimgl F2 (960×540 60, 1920×1080 30, CPU <5%, p95 <100 ms) pozostają bez zmian;
nie wykonano nowego pełnego benchmarku GL. CE 1080p nie ma deklarowanego progu w F7a.
W JSON zapisano także wszystkie odstępy i liczbę >25 ms — sporadyczny jitter pozostaje
widoczny mimo spełnienia progu okna, a próba projektora pozostaje konieczna.

| Geometria | Bufor | Update średnia [ms] | Render średnia | Kopia/pasy średnia | Publish średnia | Odbiór p95 max | Qt p95 max |
|---|---|---|---|---|---|---|---|
| D22 — przejazd | 960×540 | 0.232 | 1.113 | 1.464 | 0.448 | 5.102 | 4.169 |
| D22 — przejazd | 480×270 | 0.241 | 0.779 | 0.122 | 0.132 | 0.758 | 0.741 |
| D22 — przejazd | 538×648 | 0.231 | 0.807 | 1.173 | 0.333 | 3.949 | 2.965 |
| Panel 2D — obrót i przesunięcie | 960×540 | 0.999 | 3.527 | 1.644 | 0.545 | 5.421 | 5.113 |
| Panel 2D — obrót i przesunięcie | 480×270 | 0.935 | 2.071 | 0.143 | 0.128 | 0.757 | 0.744 |
| Panel 2D — obrót i przesunięcie | 538×648 | 0.876 | 2.056 | 1.111 | 0.340 | 3.971 | 2.961 |

Etapy workera są średnimi dla całej sesji (ruch i sondy), odbiór/Qt to p95 okna 30 s;
nie sumujemy p95. Normalizacja alfy: 0 ms — nie wymaga jej objęte gwarancją puste tło/pasy.
Zimny start osobno: 1.120–1.259 s.
Odrzucone przebiegi diagnostyczne: ~37,5 fps (ujemny stride .tobytes i zbędny canvas),
~56,2 fps (dodatkowa kopia QImage i timer Qt offscreen). Naprawiono kopie i zastosowano
ten sam odbiornik/pompowanie co F2; progów nie zmieniano. Surowe logi diagnostyczne w .tmp.

## Koszt historii

200 zapisów, limit 50 stanów, wspólne dziecko, zmiana liczby dzieci, z aktywnym tracemalloc.
Zapis mediana/p95: 0.293/0.364 ms;
przygotowanie Animation: 0.558/0.691 ms;
odtworzenie: 0.293/0.344 ms.
Pamięć bieżąca po 50/100/200 zapisach: 1018993, 1077285, 1108617 B,
szczyt 1143806 B. Historia ma stale 50 wpisów; wynik jest dla korpusu panelu,
nie dowolnej sceny. Back od komendy do odebranej granicy sprawdza test z progiem 0,5–0,7 s,
klatką pośrednią i identycznym końcowym obrazem; nie przenosimy pomiarów GL na CE.

## Rendery i próba w oknie

Wykonano kolejno (logi `.tmp/render-orbit.txt`, `.tmp/render-demo.txt`):

```powershell
uv run --frozen manim-cue render examples/orbit.py Orbit
uv run --frozen manim-cue render examples/demo.py Demo
```

Do ręcznej próby usunąć offscreen z bieżącego terminala, pozostawiając pozostałe zmienne:

```powershell
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
uv run --frozen manim-cue present Demo --show-info-window
uv run --frozen python examples/live_receiver.py examples/live_panel_ce.py Panel --engine ce-cairo
```

Na slajdach 10–11 sprawdzić dwa panele CE i Orbit, ciągłość obrazu/PID, cue wejścia,
klik/strzałki/back/Esc, pauzę bazy i klipu z nadal pracującym live, notatki i podgląd
na drugim monitorze. CE view jest no-op. Slajd 9 pokazuje wcześniejszy panel GL z alfą.

## Czas, ograniczenia i odstępstwa

Zakończenie raportu: 2026-10-23T02:01:36+02:00. Pierwszy zapisany znacznik czasu
tej pracy: 01:01:28 CEST; wcześniejsze czytanie plików zajęło kilka minut.
Mierzony czas od tego znacznika: 60.1 min, plus początkowe czytanie plików. Budżet 16 h /
stop 32 h nie został zbliżony do limitu. Brak rzeczywistego okna w tym środowisku.
Próba człowieka (projektor, dwa monitory, fizyczny fokus/płynność) niezaliczona zgodnie
z zadaniem. TeX wymaga działającego lokalnego środowiska; przy braku kompilacji jawny skip.

Odroczenia kontraktowe D38: D28 CE, animowana kamera, 3D i dowolny stan Pythona;
nie są cichym obcięciem implementacji. Snapshot interpoluje zgodne węzły raz zamiast
nakładać Transform rodzica i dziecka; zmieniona struktura zostaje dokładnie przywrócona
na granicy. Nie naprawia dowolnej półprzezroczystej treści upstreamu. Nowej niezależnej
rundy recenzji nie wykonywano; domknięcie opiera się na dostarczonej rundzie 19.

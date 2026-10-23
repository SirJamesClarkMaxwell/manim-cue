# Raport F5g — checkpointy wejść live

Data: 2026-10-23. Główne drzewo `D:/Programming/Python/manim/manim-cue`, gałąź `develop`,
bez worktree, commita, stash/reset/checkout i zmian `.venv`. Zastaną modyfikację PLAN.md
zachowano i rozwinięto. Raport zapisano również jako wyjściowy `REPORT-5g.md` w korzeniu;
PLAN.md odsyła wyłącznie do śledzonego katalogu `reports/`.

## Wynik

Kontrakt F5g domknięty po rundzie 20, D39–D41 dopisane do SPEC. Wdrożone checkpointy
GL/CE, animowane restore, replay, bariera i stan prelegenta. README i docs/api są po angielsku.
Wykonano wszystkie kryteria offscreen; próba człowieka w oknie i na dwóch monitorach pozostaje.

Pełna wymagana komenda, bez selekcji testów:

```powershell
uv run --frozen pytest -q -p no:cacheprovider
```

**558 passed, 2 skipped, 57 warnings in 638.91s (0:10:38)**

Ustawienia: `UV_OFFLINE=1`, UV_CACHE_DIR w `.cache/uv`, TMP/TEMP w `.tmp`,
`QT_QPA_PLATFORM=offscreen`. Python 3.13, CE 0.22.0, ManimGL 1.7.2; jeden wątek kodu
aplikacji na proces. `custom_config.yml` pozostaje lokalnym wskazaniem cache GL.
Nie forkowano ani nie łatano Manima, nie dodano zależności i nie obniżono żadnego progu F2/7a.
Pominięcia: upstream test_present_set_invalid_screen (znane pominięcie pełnego zestawu)
oraz GL test_tex_renders (rzeczywista kompilacja zakończona LatexError); CE test_tex_renders
przechodzi. Sprawdzono też osobnym przebiegiem z `-rs`: 1 passed, 2 skipped.

## Rozstrzygnięcia rundy 20

Pełna treść recenzji znajduje się bez zmian w REVIEW-LOG.md; porównano całą treść
z podanym plikiem źródłowym (z normalizacją końców linii). Rozstrzygnięto wszystkie 12 punktów:

1. Przyjęto osobny adapter grafu GL i bramkę updatera, współdzielenia i tożsamości dziecka, ponieważ get_state/undo nie zapewniają tej gwarancji.
2. Przyjęto rezerwację od zamówienia przygotowania do przyjęcia enter/release przez worker, także w pauzie, ponieważ ręczne cue i view nie mogą zmienić zapisanego początku.
3. Przyjęto jawny ACK po kompozycji aktualnej granicy oraz odbiór i ACK bez kompozycji granic anulowanych, ponieważ odrzucenie ACK blokuje worker.
4. Przyjęto rozdzielenie generacji i przyczyny: zimne next/auto_next/skip_all zapisują build i grają cue celu, initial i zimne previous/V tylko zapisują build, a replay lokalnego początku gra cue celu, ponieważ pominiętych slajdów nie rekonstruujemy.
5. Przyjęto stos wejść, natychmiastowe odłączenie przyszłości po cofnięciu i trwałą degradację po fallbacku, ponieważ pozycja nawigacji nie dowodzi odtworzenia sceny.
6. Przyjęto konkretne limity i korelację generacja/wejście/żądanie; odrzucono retransmisje i cache wyników duplikatów, ponieważ jeden niezawodny strumień TCP nie wymaga ponownego wysyłania cue.
7. Przyjęto jawny korpus i zasady autorstwa zamiast wykrywania zależności zamknięć i pól sceny, ponieważ ich semantyki nie da się automatycznie rozpoznać.
8. Przyjęto blokadę view podczas rezerwacji oraz home po potwierdzonym checkpoint/restore, ponieważ gesty nie mogą przeplatać operacji stanu.
9. Przyjęto rachunek aktywnej historii, checkpointów i rezerwy kopii roboczych na obsługiwanych typach; odrzucono gwarancję RSS i dowolnego deepcopy, ponieważ kod autora może alokować poza grafem.
10. Przyjęto zastąpienie ścieżki replay wspólną barierą oraz osobną barierę live przy reverse, ponieważ baza nie może grać podczas restore.
11. Przyjęto osobne komunikaty początku/pozostawionego stanu, niewysłania/przerwania/nieznanego wyniku i trwałą degradację nad READY, ponieważ gotowość transportu nie dowodzi zgodności panelu.
12. Przyjęto macierz oczekiwanych operacji i rozdzielenie semantyki/pikseli/czasu, minimum 30 prób pomiarowych oraz budżet 24 h (stop 48 h) po bramce, ponieważ integracja wymaga osobnego pokrycia wyścigów.

## Rozstrzygnięcia rundy 19 — zachowane

Zgodnie z żądaniem raport obejmuje też ustalenia rundy 19, stanowiące podstawę D36–D38;
F5g nie otwiera ponownie zegara, silników, alfy ani progów pomiarowych.

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

## Zmiany plik po pliku

| Plik | Zmiana |
|---|---|
| PLAN.md | Nagłówek kontraktu F5g, rozstrzygnięcia, semantyka zimnych wejść, ACK/rezerwacja, jawny korpus i rezerwa pamięci, kryteria i budżet 24 h / stop 48 h; odsyłacze starszych faz do D39–D41. |
| REVIEW-LOG.md | Runda 20: pytania, każde rozstrzygnięcie z powodem, pełna oryginalna recenzja. |
| SPEC.md | D39: wejścia/checkpointy; D40: graf, pamięć i fallback; D41: rezerwacja, korelacja i bariera; oznaczenie zastąpionych odroczeń. |
| CLAUDE.md | Wyłącznie punkt 2 „Przeczytaj najpierw”: stan F5g i odsyłacz do tego raportu. |
| README.md | Angielski opis ←/V/R, procesu przygotowania, komunikatów, limitów i ograniczeń obu silników; aktualizacja demo. |
| docs/api.md | Angielskie API sesji/checkpointów/replay, lifecycle, bariera, statusy i przykład z prawdziwym LiveLayer/next_slide. |
| examples/demo.py | Instrukcje próby GL na slajdach 7–8 i CE na 10–11. |
| src/manimcue/live_checkpoint.py | PanelSnapshot: wspólne memo oryginałów, krawędzie, updatery, czas; zgodna interpolacja; odbudowa grup renderera GL przez API; CheckpointStore z limitami i rezerwą przed kopią. |
| src/manimcue/live_entry.py | Historia generacji/wejść/żądań, odłączenie przyszłości, korelacja granic i stan trwałej degradacji; stare wyniki nie zmieniają bieżącego komunikatu. |
| src/manimcue/live_transport.py | Wspólny protokół checkpoint/restore/enter/drop/release, rosnące ID, walidacja przed abort, ograniczenia linii/kolejki, rezerwacja cue/view, granice BOUNDARY, D9/D10 i metryki. |
| src/manimcue/live_layers.py | Integracja historii z sesją i mapowaniem warstw, kompozycja przed ACK, ACK starych granic bez wyświetlania, deadline 5 s, blokada ręcznych komend, zachowanie poprawnego obrazu przy błędzie. |
| src/manimcue/live_scene.py | PanelSnapshot dla zarządzanej historii GL, restore bez undo/get_state i identyfikacja granic; okienny tryb standalone zachowany. |
| src/manimcue/live_scene_ce.py | PanelSnapshot dla historii CE, metryki przygotowania/restore, status granic, pominięcie pustych węzłów bez interpolacji i zwalnianie zakończonych animacji po cleanup; dotychczasowy SceneSnapshot zachowany dla istniejących odbiorców. |
| src/manimcue/live_session.py | Jawne sterowanie ACK przez kontroler, zachowany domyślny odbiór standalone; ograniczona lista metryk checkpointów. |
| src/manimcue/clip_layers.py | Bariera także bez enter_cue i dla reverse; zachowanie końcowych klatek/pozycji klipów reverse. |
| src/manimcue/slides/present/player.py | Replay przez wspólne przygotowanie, osłona callbacków starego odtwarzania podczas bariery, wspólny opis operacji/degradacji Info i nakładki. |
| tests/test_live_checkpoint.py | Testy obu backendów: piksele/graf/kursor/historia, nawigacja, pauza/fokus, szybkie przejścia, TCP/ACK, błędy/limity, lifecycle i 30 prób czasu na silnik. |
| tests/scenes/checkpoint_panel.py | Wspólny deterministyczny panel, graf współdzielonych dzieci, D9/D10 i kontrolowane błędy. |
| tests/scenes/checkpoint_gl.py | Klasy korpusu GL. |
| tests/scenes/checkpoint_ce.py | Klasy korpusu CE. |
| tests/test_persistent_live.py | Oczekiwanie na przyjęcie release, skorelowane enter, replay i zatrzymanie niepewnej sesji po timeout. |
| tests/test_live_ce_player.py | Oczekiwanie na właściwe przygotowanie, nawigacja ciepłych dwóch CE i GL w jednym decku. |
| tests/test_clip_layers.py | Zastąpienie niehashowalnej atrapy sesji prawdziwym, nieuruchomionym LiveSession. |
| tests/test_presenter_state.py | Taka sama poprawka atrapy sesji; oczekiwania komunikatów zachowane. |
| reports/f5g-metrics.json | Surowe 30 prób GL i 30 CE, osobne metryki workera oraz wynik trzech źródeł; plik nieignorowany. |
| reports/REPORT-5g.md | Ten raport; kopia wyjściowa w korzeniu REPORT-5g.md. |

## Kryteria i dowody

| Kryterium F5g | Status i testy |
|---|---|
| 1 — callbacki/nawigacja | PASS: test_player_previous_reverse_replay_pixels_and_branch; test_multiple_previous_new_branch_replay_reverse_and_no_cue; test_automatic_callback_from_reverse_preserves_live; test_entry_cue_navigation_callbacks i test_ce_entry_navigation. Initial/brak cue/anulowanie/powrót/pętla nie grają cue; udane forward/replay grają raz. |
| 2 — stan, graf, kursor i historia | PASS: test_checkpoint_graph_updater_identity_and_repeat; test_wire_graph_topology_styles_and_updater_references; test_wire_checkpoint_restores_cursor_and_full_manual_history; test_player_previous_reverse_replay_pixels_and_branch. Porównanie całych buforów pikseli (silniejsze niż tolerancja wnętrza), osobno tożsamości, wspólne dziecko, style, updatery i czas. |
| 3 — TCP, korelacja i ACK | PASS: test_protocol_validation_fifo_stale_generation_duplicates_and_invalidated_entry; test_history_status_without_frame_stale_operation_and_fallback; test_wire_reservation_unknown_cue_stale_generation_drop_and_disconnect; test_checkpoint_boundary_waits_for_ack_before_restore; istniejące test_boundary_timeout i test_boundary_is_preserved_before_queued_cue oraz CE test_tcp_utf8_split_multi_reconnect_and_boundary. |
| 4 — bariera, pauza, D9/D10 | PASS: test_replay_pause_reserves_keyboard_and_view (także R, →, ← z fokusem live); test_video_and_clip_replay_prime_beginning_behind_restore; test_entry_waits_until_first_actual_start / test_ce_entry_first_actual_start; test_live_only_static_barrier_pause_and_timeout / test_ce_barrier_pause_timeout; test_state_command_finishes_callable_and_loop_iteration; test_wire_gl_camera_checkpoint_restore_reset. |
| 5 — szybka nawigacja i generacje | PASS: test_rapid_twenty_roundtrips_keep_current_boundary (20 na każdy silnik, ze zmianą indeksu); test_two_ce_and_gl_animate_and_close; test_sessions_not_reclaimed i odpowiednik CE; test_navigation_boundaries_and_presentation_isolation; test_shutdown_during_restore_reaps_worker_and_shm. |
| 6 — limity i fallback | PASS: test_checkpoint_memory_100_entries_history_sharing_and_preallocation (oba silniki, 100 zapisów, 51. wpis/eksmisje, wspólne historie liczone raz, limit bajtów przed konstruktorem kopii); test_snapshot_retained_removed_originals_reserve_before_copy (wzrost obiektu poza sceną i rezerwa jego kopii); test_player_fallback_preserves_image_status_and_generation (missing/unsupported/limit/restore_failed, oba silniki); test_partial_restore_failure_is_fatal_and_protects_target. Drop i zwolnienie historii dają zero rozliczonych bajtów; zamknięcie odbiera proces/SHM. |
| 7 — animacja i pomiar | PASS: test_thirty_restore_trials_boundary_latency_and_gui_poll (30 na silnik, różne klatki pośrednie, każda odebrana granica w 0,6 ±0,1 s, poll/read <50 ms); osobne wyniki poniżej. test_three_scene_one_click_ten_trials i oddzielny pomiar trzech źródeł. |
| 8 — regresje, docs i demo | PASS offscreen: pełny pytest powyżej, ruff dla zmienionego kodu/testów i git diff --check; oba wymagane rendery CE zakończone kodem 0. Progi F2 i kod pomiarów 7a zachowane. Próba człowieka: OTWARTA. |

## Pomiary F5g

Panel testowy 160×90, 60 fps, Qt offscreen. Od żądania replay do odebranej granicy restore
w GUI (przed nowym cue), 30 prób na silnik; p95 to nearest rank, próbka 29 z 30.
Nie jest to czas fizycznego wyświetlenia ani odwrócenie oryginalnego cue.

| Silnik | p50 [ms] | p95 [ms] | max [ms] | max poll / read [ms] |
|---|---|---|---|---|
| manimgl | 651.42 | 657.38 | 658.56 | 1.389 / 0.684 |
| ce-cairo | 637.10 | 653.16 | 656.26 | 1.356 / 0.642 |

Osobne koszty CPU workera, bez mieszania ich z czasem animacji 0,6 s:

| Silnik | Liczba zapisów; max zapis [ms] | max budowa animacji [ms] | max dokładny restore [ms] | max rozliczone snapshoty/historia/oryginały [B] |
|---|---|---|---|---|
| manimgl | 2; 2.241 | 1.043 | 3.238 | 73709 |
| ce-cairo | 2; 1.866 | 0.407 | 0.616 | 48638 |

Pamięć to rozliczone snapshoty, historia i utrzymywane oryginały, także usunięte ze sceny,
ze współdzieleniem; przed kopią/restore dodatkowo sprawdzana jest rezerwa 4× największego
z grafu sceny, docelowego grafu i bieżących danych oryginałów, z narzutem na otoczki.
To nie pomiar ani gwarancja RSS Manima. Węzły własnych klas, zasoby i tablice object są
poza korpusem bezpiecznego rachunku; zależności updaterów od zamknięć/pól sceny nie są wykrywane.
Zapis po rozbieżności nie udaje odzyskania zgodności; wymagany poprawny wcześniejszy restore
albo nowa generacja. Rachunek i odmowę przed alokacją sprawdzono w teście 100 zapisów.

Izolowany pomiar `tracemalloc` obejmuje przygotowanie, begin/interpolację/finish animacji
i dokładny restore; nie obejmuje renderera i transferu klatek, które nie są kopiami snapshotu.
GL: szczyt zapisu 27435 B,
kopii roboczych 27961 B,
rezerwa 96196 B.
CE: szczyt zapisu 19650 B,
kopii roboczych 18821 B,
rezerwa 67064 B.
Dowód: test_snapshot_working_copy_peak_fits_reserved_graph, oba silniki.

Trzy źródła, osobno od restore: `examples/measure_player.py --trials 10 --mode session_id`.
Mediana żądanie→pierwsze zmienione piksele GUI: baza 154.06 ms,
klip 188.33 ms, live 156.96 ms;
rozrzut mediana 43.39 ms, max 49.11 ms.
Zimny READY 2.117 s. PID pozostaje ten sam w każdej próbie.
Brak wymogu ±1 klatka i brak obietnicy frame-lock. Pełne dane w `reports/f5g-metrics.json`.
Nie zmieniano ani nie zastępowano historycznych pomiarów 7a z poprzedniej fazy.

## Rendery i próba człowieka

Wykonano dokładnie (CE 0.22, kody wyjścia 0):

```powershell
uv run --frozen manim-cue render examples/orbit.py Orbit
uv run --frozen manim-cue render examples/demo.py Demo
```

Wynik Demo: 11 slajdów, deck `slides/Demo.json`; zachowano cache prawidłowych renderów CE.
Komendy do wykonania ręcznie w prawdziwym oknie (nie wykonywano tutaj):

```powershell
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
uv run --frozen manim-cue present Demo --show-info-window --start-at 0,6
uv run --frozen manim-cue present Demo --show-info-window --start-at 0,9
```

Na 7→8 (GL) i 10→11 (CE): ręczne cue na pierwszym, Esc, →, dalsze ręczne cue,
Esc, ← i V; sprawdzić stan pozostawiony na pierwszym. R dwukrotnie powinno dać to samo
wejście na deterministycznym panelu. R w reverse gra live do przodu; → z reverse
nie powtarza cue. W czasie przywracania spacja zmienia zamiar startu; ręczne strzałki
przy fokusie live są blokowane. S i Info powinny podawać ten sam stan i przyczynę degradacji.
Przenieść Info na drugi monitor i ocenić czytelność w trakcie szybkiej nawigacji.

## Przebieg, czas i odstępstwa

Wstępny pełny przebieg: 501 passed, 14 failed, 2 skipped, 749,74 s.
Naprawiono: oczekiwania starego protokołu/READY zamiast zakończenia rezerwacji,
niehashowalne atrapy, rzeczywistą regresję renderowania GL po add/remove oraz interpolację
niezgodnej topologii. Zachowano wyrocznie i progi F2; test_back_add_remove pozostaje bez zmian.
Po zielonym przebiegu 544 passed, 2 skipped dodano jeszcze bezpośrednie kombinacje wideo/reverse,
pomiar kopii roboczych oraz regresję rosnących oryginałów poza sceną i komunikatów bez cue.
Następne przebiegi celowane i końcowy pełny zestaw potwierdzają naprawy.

Czas aktywnej pracy: około 1,5 h w dwóch częściach; przerwy limitu użycia nie wliczono.
Budżet kontraktu 24 h, zatrzymanie po 48 h: nie przekroczono. Czas ścienny między pierwszymi
plikami a raportem obejmuje wielogodzinną przerwę limitu, nie jest czasem implementacji.

Odroczenia są jawnie przyjętą częścią kontraktu: retransmisje/cache duplikatów, dowolne
klasy autora, efekty I/O/RNG/zamknięć i kamera/3D CE. Standalone bez session_id zachowuje D27.
Dodano procentowe kodowanie nazw cue i status BOUNDARY jako konkrety protokołu niezbędne
do zachowania nazw oraz prawidłowej obsługi status/klatka w różnej kolejności.
Nie wykonywano próby prawdziwego okna, dwóch monitorów ani ponownej pełnej kampanii pomiarów
7a; ich wcześniejszych wyników i progów nie zmieniono. Logi robocze są w `.tmp`, lecz wszystkie
wyniki potrzebne do przeglądu są w tym raporcie i nieignorowanym `reports/f5g-metrics.json`.

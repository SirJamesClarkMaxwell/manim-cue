# manim-cue — log recenzji adwersaryjnych

Rundy 1-5 (faza 0): `PLAN-REVIEW-LOG.md` w repo seminarium `group-theory`.

---

## Runda 6 — codex, 2026-10-22: plan po zmianie kierunku (D13-D19)

Recenzent: `codex exec -s read-only` (codex-cli 0.160.0). Zakres: `CLAUDE.md`, `SPEC.md` D13-D19,
`PLAN.md` fazy 1-8; twierdzenia weryfikowane w kodzie forka, manimgl 1.7.2 i Manim CE w `.venv`.
Odpowiedź poniżej bez zmian. Co z niej weszło do planu: `SPEC.md`, sekcja „Ustalenia rundy 6”,
i `PLAN.md`, sekcja „Do decyzji przed fazą 2”.

1. **[KRYTYCZNE] Headless usuwa zegar animacji — dowód:** `.venv/Lib/site-packages/manimlib/scene/scene.py:252` ogranicza tempo przez `sleep()` wyłącznie przy istniejącym oknie; również inicjalizacja zegarów przed `play()` jest warunkowana oknem (`:522`). `src/manimcue/live_scene.py:291` wykonuje kolejne kroki animacji bez własnego ograniczania tempa. **Konsekwencja:** sekundowe cue zostanie policzone tak szybko, jak pozwoli GPU; odbiornik Qt zobaczy tylko część klatek, a animacja skończy się przed czasem. Timeout `select` tego nie naprawia: podczas animacji jest równy zero (`live_scene.py:300`). **Poprawka planu:** faza 2 musi obejmować zegar oparty na `time.monotonic()`, terminy publikacji klatek oraz obsługę komend podczas oczekiwania. Kryterium: cue o czasie 5 s trwa około 5 s także bez okna, z określoną tolerancją.

2. **[KRYTYCZNE] Zmienna środowiskowa w scenie nie wystarczy do wyłączenia okna launchera — dowód:** `manimlib/__main__.py:29` tworzy `Window` **przed** załadowaniem scen; `manimlib/config.py:323` ustawia `show_in_window=not args.write_file`. Z kolei `-w` włącza zapis filmu (`config.py:270`), a `Scene.run()` uruchamia writer przed `construct()` (`scene.py:151`). Obecny `LiveScene.construct()` odrzuca brak okna (`live_scene.py:99`). **Konsekwencja:** samo usunięcie tego wyjątku albo sprawdzenie zmiennej w `construct()` daje okno lub niechciany proces FFmpeg. **Poprawka planu:** ustalić osobny punkt startowy procesu live, który przed konstrukcją sceny wybiera `window=None`, `skip_animations=False`, wyłącza zapis filmu i ostatniego obrazu oraz presenter mode. Nie używać zwykłego `manim-cue render --GL`: ten zawsze dodaje `-w` (`slides/render.py:54`).

   Sam fundament offscreen istnieje: `Camera.init_context()` tworzy standalone ModernGL (`camera.py:72`), a `init_fbo()` wybiera własne FBO (`:81`). `Scene.__init__(window=None)` nie zawiera bezwarunkowego odwołania do okna.

3. **[WAŻNE] Headless traci zakończenie i oszczędzanie renderowania w bezczynności — dowód:** `manimlib/scene/scene.py:719` zwraca przy braku okna `None`, nawet gdy `quit_interaction=True`. `LiveScene.next_command()` polega na tej metodzie (`live_scene.py:149`). Optymalizacja pomijająca niezmienione klatki również wymaga okna (`scene.py:244`); `poll_once()` zawsze wywołuje render (`live_scene.py:165`). **Konsekwencja:** dotychczasowy sygnał zamknięcia przestaje działać, a nieruchoma scena jest niepotrzebnie rysowana kilkadziesiąt razy na sekundę. `on_key_press()` nie otrzyma zdarzeń bez okna. **Poprawka planu:** dodać jawne zakończenie przez transport, osobny warunek zatrzymania i publikację po zmianie obrazu. Określić zachowanie updaterów podczas bezczynności: obecne `dt=0` nie przesuwa ich czasu. Testować zamknięcie także podczas `play()` i `wait()`.

4. **[WAŻNE] Publikowanie tylko w `emit_frame()` zgubi pierwszą i końcową klatkę — dowód:** początkowy obraz powstaje przez `update_frame(force_draw=True)` (`live_scene.py:389`), bez `emit_frame()`. Przy przerwaniu animacja wychodzi z pętli (`:301`), po czym bazowe `finish_animations()` domyka stan mobjectów (`manimlib/scene/scene.py:561`), ale nie renderuje go. **Konsekwencja:** odbiornik może nie dostać obrazu startowego albo pozostać na klatce sprzed skoku do końca. **Poprawka planu:** określić jeden punkt publikacji oraz wymusić render i publikację po inicjalizacji, domknięciu/przerwaniu cue i cofnięciu. Dodać te przypadki do akceptacji fazy 2.

5. **[KRYTYCZNE] „Licznik albo podwójny bufor” nie stanowi protokołu synchronizacji — dowód:** `PLAN.md:76` dopuszcza te rozwiązania zamiennie. Tymczasem stdlib `multiprocessing/shared_memory.py:185` udostępnia zwykły `memoryview`, a `:207` zwraca go bez blokady. **Konsekwencja:** producent może po dwóch publikacjach ponownie zapisywać bufor, który Qt nadal kopiuje lub maluje. Sam numer klatki nie zapewnia atomowego odczytu obrazu ani uporządkowania zapisów.

   **Poprawka planu:** najprostszy wariant dla procesu uruchamianego przez player to `multiprocessing.Process` i przekazana blokada. Producent renderuje poza blokadą, pod blokadą kopiuje gotowe bajty; `QTimer` próbuje `acquire(False)`, kopiuje obraz do własnej pamięci i zwalnia blokadę przed malowaniem. Pominięcie zajętej klatki wystarcza — kolejka nie jest potrzebna. Dla niezależnie uruchomionego procesu trzeba osobno rozwiązać przekazanie synchronizacji albo własność buforów przez komunikaty TCP.

   `SharedMemory` **już jest stdlib**. Na Windows korzysta z nazwanego `mmap` (`shared_memory.py:182`); przejście bezpośrednio na `mmap` nie usuwa problemu synchronizacji. Odbiornik nie może czekać na blokadę w GUI ani bez końca ponawiać odczytu licznika po śmierci producenta.

6. **[WAŻNE] Kryterium wydajności pomija kopie i format obrazu — dowód:** `camera.py:141` wykonuje blit oraz odczyt FBO do `bytes`; `get_image()` dodatkowo tworzy obraz i odwraca pion (`:149`). `get_pixel_array()` czyta kanały jako `f4`, a potem konwertuje do bajtów (`:157`). **Konsekwencja:** wybór wygodnej metody może zwielokrotnić transfer i koszt konwersji. Surowe RGBA wymaga też jawnej orientacji, stride i interpretacji alfy.

   **Pomiar w tej sesji:** standalone ModernGL, RTX 4060, blit między FBO i odczyt RGBA, 30 próbek po rozgrzewce:

   | Rozdzielczość | Bajty/klatkę | Mediana | Maksimum |
   |---|---:|---:|---:|
   | 1920×1080 | 8 294 400 | 1,819 ms | 2,127 ms |
   | 960×540 | 2 073 600 | 0,623 ms | 0,734 ms |

   To **nie jest pomiar całego manimgl → Qt**. Pełna próba zatrzymała się na zapisie cache SQLite podczas importu, zabronionym w tej sesji. Przy 1080p60 sam payload wynosi około **498 MB/s**, przed kolejnymi kopiami.

   **Poprawka planu:** mierzyć osobno render, odczyt GPU, publikację, kopię odbiornika i prezentację; ustalić minimalne fps, opóźnienie oraz limit CPU. Użyć `get_raw_fbo_data('f1')`, jeżeli protokół wymaga RGBA8.

7. **[WAŻNE] Wymiana widgetu nie zachowa kompozycji w oknie Info — dowód:** `player.py:664` przechwytuje klatki jednego sinka, zatrzymuje ostatnią poprawną i przesyła ją do `Info` (`:685–690`). Ładowanie obrazów osobno przełącza widgety obu okien (`:477–487`). **Konsekwencja:** po dodaniu warstw podgląd bieżącego slajdu nadal pokaże pojedyncze wideo albo obraz; może też zniknąć ochrona przed czarną klatką między klipami.

   **Poprawka planu:** przed fazą 3 ustalić powierzchnię kompozycji współdzielącą model warstw z Info oraz sposób zachowania ostatnich klatek. `QGraphicsVideoItem` ma `videoSink()`, więc dotychczasowy mechanizm można przenieść per warstwa; jeden player ma jednak jedno wyjście wideo. [Dokumentacja Qt](https://doc.qt.io/qt-6/qgraphicsvideoitem.html). Do akceptacji: resize, proporcje, nakładanie warstw, przejście między slajdami i zgodny obraz w Info.

8. **[WAŻNE] D17 nie zapewnia wspólnego startu nawet przed pojawieniem się dryfu — dowód:** lokalny PySide6 to 6.12.0 (`PySide6/_config.py:8`). W backendzie FFmpeg `setMedia()` ładuje asynchronicznie (`qffmpegmediaplayer.cpp:192`); `play()` podczas ładowania tylko zapisuje żądanie (`:262`), realizowane po zakończeniu ładowania danego pliku (`:253`). **Konsekwencja:** pętla `setSource(); play()` uruchamia warstwy w różnych chwilach zależnych od dekodowania. Akceptacja dryfu długich klipów nie rozstrzyga przesunięcia początkowego. [Kod Qt 6.12](https://raw.githubusercontent.com/qt/qtmultimedia/6.12/src/plugins/multimedia/ffmpeg/qffmpegmediaplayer.cpp).

   **Poprawka planu:** najpierw załadować wszystkie źródła, poczekać na gotowość i dopiero wydać wspólne polecenie startu. Określić tolerancję widocznego startu i pauzy oraz zachowanie przy błędzie jednej warstwy. Zweryfikować na Windowsie z docelowymi kodekami. Kod potwierdza możliwość sterowania kilkoma playerami, ale nie gwarantuje równoczesnego pokazania pierwszych klatek.

9. **[WAŻNE] Warstwy wymagają decyzji o końcu slajdu, reverse i replay — dowód:** obecny `Player` ma jeden stan odtwarzania (`player.py:639`), jeden licznik pętli (`:496`), jeden replay (`:630`) i wybiera gotowy `rev_file` (`:491`). Prędkość jest ustawiana na pojedynczym playerze (`:462`). **Konsekwencja:** mechaniczne zastąpienie go listą pozostawia nierozstrzygnięte: która warstwa kończy slajd, kiedy działa `auto_next`, co robi krótszy klip i jak odwraca się animowany ruch warstw. Reverse upstreamu odtwarza przygotowany plik, nie ujemny playback rate.

   **Poprawka planu:** przed implementacją fazy 4 zapisać semantykę tych operacji. Minimalnie można wymagać równych długości, ustalić jeden warunek zakończenia i jawnie ograniczyć reverse dla animowanej kompozycji. Dodać testy replay, loop, auto-next i różnych playback rate.

10. **[KRYTYCZNE] D18 myli dostęp do pikseli z działającą pętlą live CE — dowód:** Cairo `get_frame()` tylko kopiuje aktualną tablicę kamery (`cairo_renderer.py:186`); renderowanie odbywa się wcześniej w `update_frame()` (`:139`). `play()` może pominąć obliczanie klatek po trafieniu w cache (`:104`), a statyczne `wait()` idzie przez `freeze_current_frame()` (`:128`), zapisując powtórzenia jednego obrazu (`:221`). Pętla `Scene.play_internal()` jest synchroniczna (`scene.py:1384`). OpenGL tworzy standalone context (`opengl_renderer.py:610`), ale ogranicza tempo tylko przy oknie (`:970`).

   **Konsekwencja:** odczyt po `play()` pokaże wynik końcowy; publikacja w zwykłej pętli oczekiwania nie pokaże animacji. Cache i frozen wait mogą całkowicie ominąć planowany hook klatkowy.

   **Poprawka planu:** faza 6 potrzebuje osobnych adapterów Cairo/OpenGL: aktualizacja obrazu, publikacja podczas `play()`, zegar, odczyt komend, przerwanie, obsługa `wait()` i wyłączenie zapisu plików bez włączania skippingu. Wyłączyć cache animacji dla live. PoC Cairo powinien poprzedzić obietnicę obsługi CE w API `SceneView`.

11. **[KRYTYCZNE] Faza 5 nie definiuje krokowania sceny podrzędnej — dowód:** CE `Scene.play_internal()` sam przechodzi całą animację (`scene.py:1401`), analogicznie GL `Scene.play()` wywołuje całą pętlę (`manimlib/scene/scene.py:584`). CE ma już `ImageMobjectFromCamera`, ale pobiera on tylko aktualne piksele kamery (`image_mobject.py:316,335`); nie wykonuje sceny. **Konsekwencja:** wywołanie podrzędnego `play()` z updatera gospodarza blokuje jego klatkę na całą animację. Sam obraz kamery nie daje obiecanej sceny uruchamianej wewnątrz innej sceny.

   **Poprawka planu:** rozdzielić dwa zakresy: odtwarzanie wcześniej przygotowanych klatek oraz krokowaną animację podrzędną. Dla drugiego najpierw PoC dwóch równoległych animacji gospodarza i dziecka, z deterministycznym czasem i bez rekurencyjnego `play()`. Dopiero po nim oszacować fazę 5; obecne 3 h nie mają potwierdzonej podstawy technicznej.

12. **[WAŻNE] Nowy typ live wymaga zmiany modelu danych przed playerem — dowód:** `slides/config.py:317` wymaga istniejących `file` i `rev_file`. Walidator odrzuca slajd bez źródła i bez animacji (`:291`). Zapis slajdów zakłada listę plików do łączenia (`slide/base.py:638`), a player rozwiązuje istniejącą ścieżkę przed rozgałęzieniem typu (`player.py:451`). Podgląd następnego slajdu również wymaga pliku (`:557`). **Konsekwencja:** dodanie wartości `Live` do enum nie wystarczy; deklaracja live nie przejdzie dotychczasowej ścieżki render → JSON → player. Pierwsza klatka procesu uruchamianego dopiero przy wejściu na slajd nie będzie też dostępna jako wcześniejszy podgląd.

   **Poprawka planu:** przed fazą 3 ustalić schemat live i warstw, migrację starych JSON, deklarację autorską, miniaturę dostępną przed wejściem oraz wyjście z ostatniego cue do kolejnego slajdu. Politykę `convert` określić już dla live: obraz zastępczy albo jawny błąd.

13. **[WAŻNE] D13 nie izoluje wyboru silnika i importów — dowód:** `slide/__init__.py:43` daje już zaimportowanemu `manim` pierwszeństwo przed `MANIM_API`, chyba że ustawiono `FORCE_MANIM_API`. Import `manimlib` inicjalizuje konfigurację z `sys.argv` (`manimlib/config.py:33,395`), przez `parse_args()` (`:226`). **Konsekwencja:** po imporcie CE samo `MANIM_API=manimgl` nie przełączy `Slide`; import backendu GL w procesie playera może zakończyć program na argumentach CLI Qt/forka. **Poprawka planu:** backendy importować w oddzielnych procesach z kontrolowanym `argv` i środowiskiem. Dodać do fazy 1 testy obu kolejności importów, wymuszenia API i uruchamiania CLI z argumentami.

14. **[DROBNE] Pozostały współdzielone nazwy konfiguracji i loggera — dowód:** `slides/defaults.py:4` nadal wskazuje `.manim-slides.toml`; `logger.py:40,52` używa loggera `manim-slides` i dodaje handler przy imporcie. **Konsekwencja:** fork i oryginał w jednym procesie współdzielą logger, potencjalnie dublując komunikaty; w jednym katalogu współdzielą konfigurację. **Poprawka planu:** zachowanie starego TOML określić jako świadomą kompatybilność, a logger nazwać osobno. Samo pozostawienie napisów upstreamu w komentarzach czy dokumentacji nie jest błędem wykonania.

15. **[WAŻNE] „Jeden wątek na proces” jest dosłownie sprzeczne z wybranym Qt — dowód:** `CLAUDE.md:23` i D15 ustanawiają ten wymóg bez wyjątku. Backend FFmpeg uruchamia ładowanie przez `QtConcurrent::run` (`qffmpegmediaplayer.cpp:193`), a sam fork opisuje obsługę sinków w różnych wątkach (`player.py:668`). **Konsekwencja:** architektura nie spełnia literalnego wymagania już przy zwykłym wideo. **Poprawka planu:** zapisać „jeden wątek kodu aplikacji na proces; wewnętrzne wątki Qt/sterowników dozwolone”. `QTimer` wystarcza do odbioru klatek bez dodatkowego wątku aplikacji.

16. **[WAŻNE] Fazy 3–6 nie mają warunków ukończenia — dowód:** `PLAN.md:87–127` podaje cele i część budżetów, ale bez kryteriów akceptacji; faza 6 nie ma nawet budżetu. Faza 2 wymaga „zmierzonej płynności”, bez wartości progowej (`:80`). **Konsekwencja:** dowolny wynik fps może formalnie zaliczyć fazę, a nierozstrzygnięte kwestie procesu i schematu wymuszą przebudowę odbiornika po jego implementacji. **Poprawka planu:** przed fazą 2 ustalić własność procesu i pamięci, handshake gotowości, zatrzymanie/restart, format pikseli oraz próg wydajności. Następnie przenieść minimalną powierzchnię kompozycji przed slajd live; PoC krokowania CE wykonać przed fazą 5. Dla każdej fazy dopisać konkretne scenariusze zaliczenia i budżet.

**Werdykt: plan nie jest gotowy do implementacji fazy 2.** Najpierw poprawić punkty **1–5** i kontrakt procesu/pamięci. Potem wykonać pełny pomiar **manimgl → shared memory → Qt** na Windowsie. Przed fazami 4–6 rozstrzygnąć semantykę warstw i zweryfikować krokowanie sceny podrzędnej.

Nie zweryfikowałem wykonawczo pełnego `Scene` ani wieloklipowego odtwarzania Qt na Windowsie. Pomiar dotyczy wyłącznie standalone ModernGL; ustalenia o Qt opierają się na kodzie backendu 6.12. Plików nie modyfikowałem.
---

## Runda 7 — codex, 2026-10-22: D20, spawn na Windows, kolejność faz, korpus scen, kontrakt F2

Pytania: `codex-round7-prompt` (D20 jako interpretacja odpowiedzi prelegenta „może użytkownik jak
kliknie na dane okno?”, spawn vs seqlock, kolejność F2-F9, korpus scen z xfail, podział pracy).
Pomiar wejściowy: import manimlib 1,31-1,46 s, `Scene(window=None)` 0,03 s, pierwsza klatka
1080p 5 ms. Co weszło: `SPEC.md` D20-D22, `PLAN.md` nowa kolejność i kontrakt F2.

**Werdykt: F2 można przekazać wykonawcy po przyjęciu poniższego kontraktu.** Zostawiłbym `multiprocessing.Process + Lock`. D20 zmieniłbym na: **proces przygotowuje się przy wejściu na slajd, kliknięcie aktywuje sterowanie**. Zaproponowana kolejność faz wymaga jednego dodatkowego cięcia: gotowe klatki `SceneView` i krokowanie sceny podrzędnej muszą mieć oddzielne kryteria ukończenia.

Nie modyfikowałem plików. Podane przez Ciebie czasy importu i pierwszej klatki traktuję jako pomiary wejściowe; nie powtarzałem renderowania.

**A. D20: oddzielić przygotowanie procesu od aktywacji**

**Stanowisko.** Start dopiero po kliknięciu jest technicznie dopuszczalny, ale słaby jako domyślne zachowanie prezentacji. Z podanych pomiarów wynika już około 1,4 s samego importu, do czego dochodzą spawn i `build_objects()`. Miniatura zakrywa oczekiwanie, lecz go nie usuwa.

Rekomenduję:

| Zdarzenie | Zachowanie |
|---|---|
| Wejście na slajd | Player uruchamia proces i przygotowuje scenę do pierwszej klatki. |
| Pierwsza klatka gotowa | Miniatura zostaje zastąpiona obrazem live; cue jeszcze nie biegnie. |
| Kliknięcie warstwy | Warstwa przejmuje klawiaturę; samo kliknięcie nie wykonuje `next`. |
| Kliknięcie podczas przygotowania | Zapamiętana aktywna warstwa, widoczny stan ładowania; brak kolejkowania wielu cue. |
| Esc / klik poza warstwą / zmiana slajdu | Klawiatura wraca do playera. |
| Wyjście ze slajdu | Proces zostaje zatrzymany; ponowne wejście tworzy nową sesję. |

„Kliknięcie uruchamia pierwsze cue” byłoby osobną decyzją. Przy obecnym API naturalne jest: klik wybiera odbiorcę, strzałka wyzwala cue.

Nie uruchamiałbym wszystkich scen przy starcie playera. `Scene.__init__` od razu tworzy kamerę, a kamera headless własny kontekst GL i FBO: `manimlib/scene/scene.py:106`, `manimlib/camera/camera.py:72`, `:81`. Start całej prezentacji oznaczałby przygotowywanie także nieużywanych scen i ich zasobów.

**Dowody dotyczące klawiatury.**

- Player bezwarunkowo wywołuje swój dispatcher: `src/manimcue/slides/present/player.py:695`.
- Domyślne `Right` i `Left` oznaczają przejście slajdu, a spacja pauzę: `src/manimcue/slides/config.py:89`.
- Te sygnały są podłączone do metod playera w `player.py:295`.
- Okno Info przekazuje klawisze do tej samej metody: `player.py:183`, `:289`.
- Live rozpoznaje transportowe `next` i `back`: `src/manimcue/live_scene.py:46`.

**Kolizja jest więc konkretna:** strzałka skierowana do live, która następnie trafi do obecnego `Player.keyPressEvent`, przesunie również prezentację. Sam fokus elementu graficznego nie jest wystarczającym kontraktem routingu.

**Rekomendacja.** Jeden router przed `self.dispatch`:

1. Esc zwalnia aktywną warstwę i konsumuje zdarzenie.
2. Przy aktywnym live skonfigurowane `NEXT`/`PREVIOUS` wysyłają `next`/`back` i konsumują zdarzenie.
3. Pozostałe skróty playera zachowują znaczenie; nie wysyłamy ich do Manima.
4. Bez aktywnego live działa dotychczasowy dispatcher.
5. Routing obejmuje zarówno widok prezentacji, jak i zdarzenia przekazywane z Info. Utrata aktywności okna powinna zwalniać aktywację live, aby po powrocie nie pozostał ukryty odbiorca klawiszy.

W ten sposób `Space`, `R`, `V`, `F`, `H`, `Q` nie otrzymują przypadkowo nowego znaczenia. Obsługa dowolnych klawiszy sceny wykracza poza obecny protokół dwóch komend.

**Kliknięcie.** W podklasie `QGraphicsView.mousePressEvent` użyć:

```python
item = self.itemAt(event.position().toPoint())
```

Następnie znaleźć właściciela warstwy, także gdy trafiony element jest jej dzieckiem. `itemAt` przyjmuje współrzędne viewportu i zwraca najwyższy element; lokalne sygnatury są w `PySide6/QtWidgets.pyi:3455`, `:3500`. Zachowanie potwierdza [dokumentacja Qt](https://doc.qt.io/qt-6/qgraphicsview.html#itemAt).

Dla live ustalić prostokątny obszar trafienia. Inaczej przezroczyste piksele miniatury mogą zmieniać klikalność. Zwykła warstwa zasłaniająca live powinna blokować klik; techniczna obwódka aktywacji powinna być pomijana podczas identyfikacji właściciela.

Fullscreen i ukrywanie kursora **nie wyłączają myszy w obecnym kodzie**: pierwsze zmienia stan okna, drugie wyłącznie `BlankCursor` (`player.py:239`, `:248`, `:649`, `:658`). Ukryty kursor utrudnia jednak wskazanie warstwy. Aktywna warstwa potrzebuje widocznej obwódki, niezależnej od kursora.

D20 pozostaje interpretacją odpowiedzi prelegenta, nie potwierdzoną dosłowną decyzją. Technicznie rekomenduję powyższą wersję.

**B. Windows spawn: lokalny wrapper nie uzasadnia porzucenia `Process + Lock`**

**Stanowisko.** Poprzednią rekomendację podtrzymuję, ale dopisuję warunki importowania workera. Samo rozszerzenie `.exe` nie powoduje awarii spawn.

W podanej stdlib:

- `multiprocessing/spawn.py:33`: `WINEXE = getattr(sys, 'frozen', False)`. To nie jest test rozszerzenia launchera.
- `spawn.py:192`: pierwszeństwo ma `__main__.__spec__.name`.
- Dopiero bez nazwy modułu wybierane jest `init_main_from_path`: `spawn.py:196`.
- `_fixup_main_from_name` pomija nazwę `__main__` i nazwy kończące się `.__main__`: `spawn.py:250`.
- Ścieżkowy fallback używa `runpy.run_path`: `spawn.py:297`. Sam `run_path` obsługuje również archiwa ZIP, nie tylko pliki źródłowe: `Lib/runpy.py:262`, `:280`.

**Sprawdziłem lokalny `.venv/Scripts/manim-cue.exe`.** Zawiera ZIP z `__main__.py`; kod wrappera importuje `cli`, a wywołuje je pod strażnikiem `if __name__ == "__main__"`.

Próba wykonania tego wrappera przez `runpy`, z zastąpioną funkcją CLI, dała:

```text
MAIN .venv\Scripts\manim-cue.exe\__main__.py __main__
PREP {'init_main_from_name': '__main__'}
CHILD_LOCK <Lock(owner=None)>
EXIT 0
```

To potwierdza przygotowanie spawn i przekazanie blokady dla tego wrappera. **Nie jest to jeszcze test rzeczywistego `manim-cue present → worker`**, którego obecnie nie ma.

Przekazywanie `Lock` na Windows ma jawną implementację: `multiprocessing/synchronize.py:100` duplikuje uchwyt dla dziecka, a `:114` odtwarza `SemLock`.

**Najważniejsza pułapka pozostaje przy importach.** Spawn odtwarza argumenty rodzica (`spawn.py:184`). `manimlib` oblicza konfigurację przy imporcie (`manimlib/config.py:395`) i wtedy parsuje argumenty (`:33`).

Dlatego:

- target procesu musi być funkcją modułową, np. `manimcue.live_worker.run_worker`;
- moduł workera nie może importować `manimlib` ani `live_scene` na poziomie modułu;
- wewnątrz targetu najpierw ustawić kontrolowane `sys.argv`, dopiero potem importować backend i scenę użytkownika;
- przekazywać opis sceny i ustawienia, nie klasę sceny, instancję Qt ani kontekst GL;
- tworzyć proces i blokadę z jednego `mp.get_context("spawn")`.

**Seqlock z pytania: odrzucam jako opis wystarczającego protokołu.**

`SharedMemory.buf` jest zwykłym `memoryview`, bez operacji atomowych i barier: `multiprocessing/shared_memory.py:185`, `:207`. Opis nie określa nawet sposobu zapisu licznika. Zapis przez `struct.pack_into` albo przypisanie wycinka nie daje kontraktu atomowej operacji z wymaganym porządkiem pamięci.

Windows gwarantuje atomowość odpowiednio wyrównanych prostych operacji 64-bitowych na 64-bitowym systemie, ale odróżnia ją od synchronizacji i porządku pamięci. Są do tego operacje Interlocked i bariery; zob. [Microsoft: Interlocked Variable Access](https://learn.microsoft.com/en-us/windows/win32/sync/interlocked-variable-access).

Nie twierdzę, że każdy taki eksperyment na x86-64 musi wykazywać rwanie. Twierdzę, że **„CPython + x86-64 + licznik przed i po” nie specyfikuje gwarancji**, na których można oprzeć poprawność projektu. GIL nie synchronizuje dwóch procesów.

**Rekomendacja:** `Process + przekazany Lock + nazwana SharedMemory`. `Popen -m` ma sens przy potrzebie niezależnego uruchamiania backendu; wtedy trzeba dodać rzeczywistą synchronizację albo przekazywanie własności buforów. Tu oznaczałoby to więcej pracy bez rozwiązania potrzebnego problemu.

**C. Kolejność faz: przyjąć z trzema doprecyzowaniami**

**Stanowisko.** F2 → F3 → F4 → F5 jest właściwe. F2 powinno pozostać niezależne od playera.

**Dowody.**

- Obecny model wymaga plików: `src/manimcue/slides/config.py:317`.
- Player już w konstruktorze pobiera `current_slide_config.file`: `player.py:225`.
- Powierzchnia to stos `QVideoWidget` i `QLabel`: `player.py:255`.
- Zachowanie ostatniej poprawnej klatki i przekazanie do Info znajduje się w `player.py:664`.
- Obecne testy `HeadlessScene` zastępują render licznikiem, `emit_frame` pustą metodą, a cofanie licznikiem wywołań: `tests/test_live_scene.py:92`, `:108`, `:114`, `:120`. Nie dowodzą działania strumienia obrazu.

**Rekomendowane cięcia:**

| Faza | Warunek zakończenia |
|---|---|
| F2 | Osobny proces GL → pamięć → minimalny Qt; poprawny czas, klatki graniczne i zamykanie. |
| F3 | Wersjonowany model, migracja, miniatura, polityka `convert`; minimalna kompozycja zachowuje obraz i Info. |
| F4 | Live w playerze, przygotowanie przy wejściu, routing fokusu, błędy i ponowne wejście. |
| F5 | Pełne transformacje warstw oraz gotowość, wspólny start i pauza. |
| F6a | `SceneView` odtwarzający gotowe klatki. |
| F6b | Osobny PoC krokowania gospodarza i dziecka; wynik może zamknąć ten kierunek. |
| F7 | Najpierw live CE Cairo; OpenGL jako oddzielny adapter i zestaw testów. |
| F8 | Integracja seminarium po zgodności CE 0.22 i próbie na dwóch monitorach. |
| F9 | GX wyłącznie po spełnieniu dotychczasowego warunku wejścia. |

Trzy doprecyzowania:

1. **F4 nie powinna utrwalać „klik = spawn”.** Powinna wdrażać rozdzielenie przygotowania i aktywacji.
2. **F6a nie zależy od działającego live CE.** Może konsumować wcześniej przygotowane klatki. F6b nie powinno obiecywać ogólnego `child.play()` z updatera: GL wykonuje całą animację synchronicznie (`manimlib/scene/scene.py:584`).
3. **CE 0.22:** zapis „najpóźniej przed fazą 7” wymaga aktualizacji numeracji po dodaniu fazy. Najmniej ryzykownie sprawdzić zgodność przed implementacją adapterów CE, a bezwzględnie przed integracją seminarium. Obecny fork nadal ustawia `config["write_to_movie"]` (`slides/slide/manim.py:48`), a zależność wyklucza 0.22 (`pyproject.toml:27`).

Przy warstwach o równych długościach „długość” należy rozumieć jako efektywny czas odtwarzania, po `playback_rate`. Live sterowane cue nie ma deklarowanej długości — D6 (`SPEC.md:252`). Na początek live nie powinno sterować automatycznym końcem slajdu. Kończy go wskazana warstwa plikowa albo prelegent po zwolnieniu fokusu live.

**Automatyzacja F2.** Tak, większość poprawności można sprawdzić automatycznie:

- bez GPU: protokół bufora, blokada, parser, timeouty, awarie i zegar ze sztucznym czasem;
- Qt offscreen: odbiór, własność obrazu, orientacja, responsywność timera i obsługa śmierci producenta;
- rzeczywisty GL bez okna: start, render, TCP, czas `play()`/`wait()`, klatki graniczne i cofanie.

Projekt już ustawia `QT_QPA_PLATFORM=offscreen`, lecz **tylko w poddrzewie testów slides**: `tests/slides/conftest.py:12`. Nowe testy potrzebują tego ustawienia przed inicjalizacją Qt również poza tym katalogiem.

`QT_QPA_PLATFORM=offscreen` nie zapewnia kontekstu ModernGL. Ten powstaje osobno przez `moderngl.create_standalone_context()` (`camera.py:74`). Testy rzeczywistego GL potrzebują działającego sterownika i osobnego znacznika, np. `gpu`.

Offscreen nie zalicza płynności na projektorze, systemowego fokusu ani dwóch monitorów. Tych kryteriów nie zastępować zielonym `pytest-qt`.

**D. Korpus scen: tak; `xfail(strict)` tylko dla konkretnych braków**

**Stanowisko.** Korpus powinien rozróżniać:

- sceny poprawne, które docelowo mają działać;
- sceny celowo błędne, dla których sukcesem testu jest czytelna diagnoza;
- testy infrastruktury, które nie potrzebują sceny Manima.

Poniżej konkretna lista. Nazwy oznaczają małe klasy scen lub odpowiadające im fixture’y.

| Scena | Faza | Co sprawdza | Kryterium sukcesu |
|---|---:|---|---|
| `PrerenderCETwoSlides` | F1 | CE, dwa cue, notatki, reverse | JSON ma dwa slajdy; oba klipy dają się zdekodować; oczekiwane kolory/pozycje w próbkach. |
| `PrerenderGLTwoSlides` | F1 | Ten sam kontrakt dla GL | Jak wyżej, w osobnym procesie. |
| `LiveGLFirstFrame` | F2 | Inicjalizacja bez cue | Pierwsza klatka ma właściwy rozmiar i niepuste obszary obiektów. |
| `LiveGLCorners` | F2 | Format i orientacja | Cztery różne narożniki trafiają we właściwe miejsca; kanały nie są zamienione. |
| `LiveGLMoveFiveSeconds` | F2 | Zegar headless | Cue trwa 5 s z tolerancją; środek obiektu zmienia się w klatkach pośrednich; koniec jest dokładny. |
| `LiveGLInterruptTwoPlays` | F2 | Przerwanie wieloetapowego cue | Komenda podczas pierwszego `play()` domyka oba etapy bez odegrania drugiego w pełnym czasie. |
| `LiveGLAddRemoveBack` | F2 | Cofanie zmian listy obiektów | Po `back` wracają obecność, geometria i kolory obiektów sprzed cue. |
| `LiveGLUpdaterWait` | F2 | Updater w `wait()` | Ruch odpowiada sumie `dt`; `shutdown` przerywa oczekiwanie. |
| `LiveGLStaticWait` | F2 | Statyczne `wait()` | Trwa zadany czas, reaguje na transport, nie produkuje niepotrzebnie identycznych obrazów. |
| `LiveGLIdleUpdater` | F2 | Jawna polityka bezczynności | Przy rekomendowanym zamrożeniu obiekt między cue pozostaje nieruchomy. |
| `LiveGLLoopBoundary` | F2 | D9 kontra D10 | Zwykła komenda kończy pętlę na granicy powtórzenia; `shutdown` działa natychmiast. |
| `LiveGLThreeD` | F2 | Kamera 3D i odczyt FBO | Zmiana orientacji daje zmianę projekcji i oczekiwaną widoczność obiektów. |
| `LiveGLTex` | F2 | Budowanie tekstu matematycznego | READY dopiero po zbudowaniu; niepusty obszar wzoru. Osobno środowisko z TeX. |
| `LiveGLSlowBuild` | F2/F4 | Długi `build_objects()` | Qt pozostaje responsywne; READY nie pojawia się przed końcem budowania; zamknięcie działa przez nadzorcę. |
| `LiveGLCueRaises` — negatywna | F2 | Wyjątek w cue | Błąd zawiera scenę, cue i wyjątek; sesja kończy się; odbiornik żyje. |
| `LiveGLBuildRaises` — negatywna | F2 | Wyjątek inicjalizacji | Brak fałszywego READY; czytelny błąd; posprzątane zasoby. |
| `LiveLayerFocus` | F4 | Routing klawiatury | Klik + Right zmienia cue, nie slajd; po Esc Right zmienia slajd. |
| `LayerComposition` | F3/F5 | Obraz, wideo, live, transformacje | Wybrane piksele kompozycji odpowiadają z-order, pozycji i skali; Info pokazuje zgodny obraz. |
| `LayerStartPause` | F5 | Gotowość i wspólne sterowanie | Nic nie startuje przed gotowością wszystkich; start/pauza mieszczą się w ustalonej tolerancji. |
| `LayerUnequalDuration` — negatywna | F5 | Ograniczenie MVP | Walidacja odrzuca nierówne efektywne długości z nazwami warstw. |
| `SceneViewFrames` | F6a | Gotowe klatki w gospodarzu | Przy zadanych czasach gospodarz pokazuje właściwe klatki; jego transformacje nadal działają. |
| `SceneViewStepping` | F6b | PoC krokowania | Gospodarz i dziecko postępują równolegle przez zadany czas; brak zablokowania gospodarza na całe cue. |
| `LiveCECairo` | F7 | Adapter Cairo | Klatki pośrednie, zegar, wait, przerwanie, brak plików filmu. |
| `LiveCEOpenGL` | F7 | Adapter OpenGL | Ten sam kontrakt, wykonany niezależnie od Cairo. |

Nie używałbym pełnego hasha obrazu jako podstawowego kryterium renderów GPU i tekstu. Lepsze są pozycje, maski kolorów, tolerancja pikselowa i stan obiektów. Hash nadaje się do **syntetycznych bajtów transportu**, gdzie wynik ma być identyczny.

Istniejące cofanie odtwarza stan mobjectów przez `SceneState.restore_scene` (`manimlib/scene/scene.py:906`), ale nie należy z tego wyprowadzać przywracania dowolnych pól Pythona, plików czy efektów ubocznych cue. Test `AddRemoveBack` powinien sprawdzać właśnie gwarantowany zakres.

Do tego osobne testy infrastruktury: śmierć pisarza pod blokadą, wolny czytelnik, restart, uszkodzony nagłówek, nieznana komenda i fragmentacja TCP. Nie tworzyć dla każdego z nich klasy sceny.

**`xfail(strict=True)` jest dobry, ale nie sam.** Lokalny pytest:

- bez `raises=` traktuje dowolny wyjątek jako oczekiwaną porażkę: `_pytest/skipping.py:289`;
- zamienia przejście testu strict w błąd: `:305`.

Zatem:

- dla konkretnego działającego testu przyszłej funkcji: `xfail(strict=True, raises=..., reason="F6b: …")`;
- import brakującego modułu wykonywać wewnątrz testu, aby nie wywrócić kolekcji;
- dla samej zapowiedzi bez ustalonego API wystarczy manifest korpusu z fazą; pusty test `assert False` niczego nie mierzy;
- sceny negatywne mają zwykłe zielone testy z `pytest.raises` albo asercjami komunikatu i exit code — **bez xfail**;
- brak GPU lub TeX to osobny jawny skip środowiskowy, nie oczekiwana wada implementacji.

Przejście jednego testu wymusza zdjęcie znacznika z tego testu; nie dowodzi ukończenia całej funkcji.

**E. Najbardziej ryzykowne części F2**

**Stanowisko.** Najmocniejszy wykonawca powinien dostać integrację pętli sceny z zegarem i protokołem. Haiku może przygotować proste sceny, receiver i testy według zamkniętego kontraktu.

| Kawałek | Dlaczego wymaga dokładnej specyfikacji |
|---|---|
| Zegar + `play()` + `wait()` + przerwanie | Są dwie pętle wykonania; samo poprawienie `progress_through_animations` nie obejmuje `wait()`. Dowód: `live_scene.py:271`, `manimlib/scene/scene.py:590`. |
| Rozróżnienie komendy, przerwania i shutdown | Obecnie każda kompletna linia oznacza żądanie przerwania: `live_scene.py:267`. Błędna komenda może więc przerwać cue. |
| Pętla cue zapętlonego | Kod sprawdza przerwanie podczas każdego `play()`, również wewnątrz pętli: `live_scene.py:253`, `:264`, `:301`. Sam opis D9 nie gwarantuje granicy powtórzenia. |
| Publikacja stanów granicznych | Start omija `emit_frame`, a `finish_animations` nie renderuje wyniku: `live_scene.py:389`, `manimlib/scene/scene.py:561`. |
| Śmierć procesu i własność obrazu | Qt musi dostać własną kopię; po śmierci pisarza sesji i blokady nie wolno używać ponownie. |
| Bootstrap i czyste importy | Konfiguracja GL powstaje przy pierwszym imporcie; target nie może sprowadzić backendu przed oczyszczeniem argv. |
| Sprzątanie po wyjątkach | Bazowe `Scene.run()` nie ma `finally` obejmującego dowolny wyjątek użytkownika: `manimlib/scene/scene.py:148`. Worker potrzebuje własnego nadzoru. |

Nie dzieliłbym tych zależnych fragmentów między kilku wykonawców bez jednego właściciela integracji. Największe ryzyko to lokalnie poprawne kawałki z różną definicją „gotowy”, „przerwany” i „ostatnia klatka”.

**Specyfikacja F2 do przekazania wykonawcy**

Poniższe nazwy i wartości są propozycją kontraktu implementacyjnego, nie opisem istniejącego API.

**Zakres i pliki**

- `src/manimcue/live_worker.py` — importowalny target spawn, bootstrap, konfiguracja i nadzór sceny. Bez importów Manima/Qt na poziomie modułu.
- `src/manimcue/frame_buffer.py` — format bloku, walidacja i kopiowanie pod przekazaną blokadą. Bez Manima i Qt.
- `src/manimcue/live_session.py` — właściciel procesu, pamięci i połączenia; API asynchroniczne względem GUI.
- `src/manimcue/live_scene.py` — jawny tryb headless, zegar, publikacja, shutdown oraz obsługa `wait()`. Zachować dotychczasowy tryb okna.
- `examples/live_receiver.py` — minimalny `QLabel`, uruchamiający `LiveSession`; bez modyfikacji playera.
- `tests/scenes/live_gl.py`, `tests/test_frame_buffer.py`, `tests/test_live_session.py`, `tests/test_live_rendering.py`.

Bez modelu slajdów, zmian `Player`, CE, `SceneView` i pełnych warstw.

**API**

```python
@dataclass(frozen=True)
class LiveSpec:
    scene_file: str       # absolutna ścieżka
    scene_name: str
    width: int
    height: int
    fps: int

def run_worker(spec, shm_name, frame_lock, bootstrap_sender) -> None: ...

class LiveSession:
    def start(self, spec: LiveSpec) -> None: ...
    def poll(self) -> SessionUpdate: ...
    def send(self, command: str) -> None: ...
    def try_read_frame(self) -> OwnedFrame | None: ...
    def request_stop(self) -> None: ...
```

`start`, `poll`, `send`, `try_read_frame` i `request_stop` nie mogą wykonywać blokującego oczekiwania w GUI. `poll()` realizuje również timeout zatrzymania i wykrywa exit code. `OwnedFrame` zawiera własne bajty oraz metadane, bez widoku na SharedMemory.

**Proces i bootstrap**

1. Rodzic tworzy SharedMemory, `ctx.Lock()` i `ctx.Process` przez kontekst `"spawn"`.
2. Target otrzymuje wyłącznie dane i obiekty IPC.
3. W targetcie ustawić `sys.argv=[argv0]` przed pierwszym importem Manima, również przed importem pliku sceny.
4. Utworzyć scenę z `window=None`, `skip_animations=False`, `presenter_mode=False`.
5. Jawnie wyłączyć `write_to_movie`, `save_last_frame` i `subdivide_output`, niezależnie od konfiguracji użytkownika. Writer przyjmuje te opcje w `scene_file_writer.py:29`.
6. Listener wiąże `127.0.0.1:0`. Mały kanał bootstrap, np. `multiprocessing.Pipe`, przekazuje endpoint albo błąd. W GUI używać `poll(0)`, nie `select` na uchwycie potoku.
7. Diagnostyka trafia na odziedziczony stderr. Nie zostawiać nieopróżnianych `stdout=PIPE`/`stderr=PIPE`.
8. READY oznacza ukończenie `build_objects()` i opublikowanie pierwszej klatki. Sam otwarty port nie oznacza gotowej sceny.

**Protokół pamięci**

Jeden blok, jeden pisarz, jeden czytelnik, stały rozmiar podczas sesji.

Nagłówek wersji 1: magic, wersja, szerokość, wysokość, stride, rozmiar payloadu, format, orientacja, `frame_id`, znacznik czasu monotonicznego. Metadane zmienne i payload są chronione **tą samą blokadą**.

- Payload: RGBA8, `stride=4*width`, `size=stride*height`.
- Orientacja przesyłana jawnie jako bottom-up, zgodnie z odwróceniem stosowanym przez `Camera.get_image()` (`camera.py:149`).
- F2 wymusza nieprzezroczyste tło; przezroczysta kompozycja nie jest kryterium tej fazy.
- Render i `get_raw_fbo_data(dtype="f1")` odbywają się poza blokadą.
- Pisarz kopiuje payload i aktualizuje nagłówek pod blokadą.
- Czytelnik wykonuje `acquire(False)`. Jeśli zajęta — pomija próbę.
- Pod blokadą czytelnik kopiuje nową klatkę do własnej pamięci; zwalnia ją przed konwersją Qt, odwróceniem pionowym i malowaniem.
- Numer klatki wykrywa nowość; nie pełni funkcji synchronizacji.
- Brak kolejki zwykłych klatek: wolny odbiornik widzi najnowszą dostępną.

**Ważne:** pojedynczy bufor nie gwarantuje odebrania każdego stanu granicznego, jeśli następne cue natychmiast go nadpisze. Dla pierwszej klatki, końca cue i cofnięcia wprowadzić potwierdzenie odbioru `frame_seen <id>`. Przed kolejnym cue worker czeka na potwierdzenie skopiowania tej klatki, nadal obsługując shutdown. Timeout 2 s kończy sesję jako błąd odbiornika. Zwykłe klatki nie wymagają potwierdzeń.

To ograniczona bariera na granicach cue, nie kolejka obrazów.

**Transport i semantyka**

Zachować UTF-8 i framing po `\n`. Dodać zarezerwowane komunikaty sterujące oraz odpowiedzi statusowe:

- `next`, `back`, istniejące nazwy presetów;
- `shutdown` — priorytetowe zakończenie;
- `frame_seen <id>` — potwierdzenie klatki granicznej;
- odpowiedzi READY, zakończenie cue, koniec sekwencji i ERROR.

Parser rozróżnia te kategorie przed wyznaczeniem `interrupt_requested`. Nieznana komenda i potwierdzenie obrazu nie przerywają animacji. Zachować zwykłe EOF klienta jako rozłączenie, zgodnie z dotychczasowym transportem; rodzic odpowiada za zakończenie zarządzanej sesji.

**Zegar i publikacja**

- Terminy oparte na `time.monotonic()`; oczekiwanie przez `select` pozwala obsługiwać komendy.
- Nie sumować `sleep(1/fps)` po renderze — prowadziłoby to do dodawania kosztu renderu do czasu cue.
- Jeden mechanizm publikacji dla animacji i wymuszonych stanów granicznych.
- Publikować po inicjalizacji, klatkach animacji, domknięciu cue, przerwaniu i `undo()`.
- `wait()` zachowuje czas i `stop_condition`, ale obsługuje również transport i shutdown.
- Między cue updatery są zamrożone. W `play()` i `wait()` otrzymują właściwe `dt`.
- Statyczna bezczynność nie renderuje co 1/60 s.
- Zwykłe cue: sterowanie może przerwać animację zgodnie z D10.
- Cue zapętlone: zwykłe sterowanie kończy bieżące powtórzenie zgodnie z D9; shutdown nie czeka na jego koniec.
- Zdefiniować i testować przeciążenie; nie wykonywać serii spóźnionych publikacji tylko po to, aby „nadrobić fps”.

**Zamykanie i błędy**

- `shutdown` w idle, `play()` i `wait()` ma zatrzymać proces kooperacyjnie.
- Po 2 s nadzorca wymusza zakończenie, następnie odbiera exit code.
- Dotyczy to również zawieszonego importu lub `build_objects()`: synchronicznego kodu użytkownika nie da się w tym modelu obsłużyć komendą w jego środku.
- Śmierć procesu zachowuje ostatni własny obraz odbiornika i pokazuje błąd.
- Po wymuszonym zakończeniu nie używać ponownie starej blokady ani pamięci. Restart tworzy nową sesję.
- Rodzic jest właścicielem zasobów; obie strony zamykają własne uchwyty. Worker ma `finally` obejmujące błędy inicjalizacji i cue.

**Kryteria jako testy**

1. `test_spawn_from_console_entrypoint` — rzeczywisty launcher i uruchomienie przez `python -m`; brak ponownego wywołania CLI w dziecku, Lock działa.
2. `test_backend_import_uses_clean_argv` — argumenty playera nie trafiają do argparse Manima.
3. `test_first_frame_and_orientation` — rozmiar, kanały i cztery narożniki.
4. `test_no_torn_synthetic_frames` — szybki pisarz, opóźniony czytelnik; każda odebrana klatka ma spójny wzorzec i numer.
5. `test_reader_owns_pixels` — zapis następnej klatki nie zmienia już odebranego obrazu.
6. `test_five_second_cue` — na referencyjnej maszynie 4,9–5,2 s od rozpoczęcia cue do końcowej publikacji, bez czasu inicjalizacji.
7. `test_interrupt_final_frame` oraz `test_back_add_remove` — dokładny stan końcowy i odebrana klatka graniczna.
8. `test_wait_and_loop_shutdown` — zatrzymanie podczas obu pętli; poprawna semantyka D9.
9. `test_unknown_command_does_not_interrupt` — ostrzeżenie bez zmiany bieżącego cue.
10. `test_worker_dies_holding_lock` — GUI nadal tyka; brak blokującej próby naprawy blokady.
11. `test_build_and_cue_errors` — czytelny błąd, brak fałszywego READY, brak pozostawionego procesu.
12. `test_restart_uses_fresh_resources` — stara sesja nie wpływa na nową.
13. `test_no_movie_output` — brak filmu i uruchomionego writera FFmpeg.

Pomiar akceptacyjny na Windowsie, po rozgrzewce, przez 30 s prostej animacji:

- 960×540: ≥60 **różnych odebranych klatek/s** średnio;
- 1920×1080: ≥30;
- statyczna bezczynność: CPU procesu live <5% jednego rdzenia;
- ciepła sesja: p95 komenda → odebrana zmieniona klatka <100 ms;
- osobne czasy renderu, readbacku GPU, publikacji, kopii odbiornika i przekazania do wyświetlenia;
- zimny start raportowany osobno, razem z `build_objects()`.

Nie liczyć wywołań timera jako fps. Pomiar Qt offscreen oznacza dostarczenie obrazu do odbiornika, nie fizyczne pokazanie go na ekranie.

**Werdykt końcowy:** przyjąć kolejność faz z rozdzieleniem F6a/F6b; wybrać `spawn + Lock`; D20 oprzeć na przygotowaniu przy wejściu i aktywacji kliknięciem. F2 jest gotowa do wykonania według powyższego kontraktu. Budżet 3 h pozostaje hipotezą; zgodnie z `CLAUDE.md` po 6 h wykonawca powinien zgłosić stan i pozostałe blokady.

---

## Runda 8 — codex, 2026-10-22: domknięcie F2 (D26), kontrakt F3 (D23-D25)

Pytania: `codex-round8-prompt` (próg fps, skip TeX, model `layers`, miniatura w renderze przez
spawn, kompozycja na wspólnej `QGraphicsScene`, kryteria i budżet F3, granica F3/F4).
Recenzja statyczna, codex-cli 0.160.0, `-s read-only`.

**Co weszło:**
- D26 przepisane: pomiar zamraża liczniki z końcem okna i zapisuje surowe liczby
  (`examples/measure_live.py`); próg to „≥ fps·T − 2 klatki” zamiast 97%. Ponowny pomiar:
  960×540 — 1800 opublikowanych, 1800 odebranych, 1799 różnych obrazów; 1080p — 1796/1796/1795.
  Strat nie ma; 59,96 było granicą okna (p. 1-2).
- Wynik F2 podaje TeX osobno jako skip (p. 3).
- Kontrakt ścieżek: autorskie `scene_file` względem CWD renderu, zapisane względem
  `path.parent.parent`, test z innego CWD; eksport `LiveLayer` (p. 4).
- `copy_to` i walidator `Converter` odrzucają warstwy live, wspólna funkcja
  `check_no_live_layers` (p. 5).
- `rect`: skończone liczby, minimum 1 px, „w kadrze” jako ograniczenie układu F3 (p. 6).
- Kryterium 3: render CE i GL (p. 7). Generator miniatur: timeout startu, pompowanie sesji do
  odebrania procesu w `finally`, PNG po sukcesie, test zawieszonego budowania (p. 8).
- Klucz cache: ścieżka, bajty pliku, klasa, rozmiar, wersja generatora; zależności przez
  `--flush-cache`; generowanie po filtrach `skip_animations` i offsetu (p. 9). Autorski
  `cache_key` odłożony — bez potrzeby w korpusie.
- `frame_changed` nie wstawia pustej klatki, gdy poprzednia też jest pusta; bez kopii do Info
  (p. 10). Jedna kompozycja na całą prezentację, więc ostatnia klatka nie ginie między slajdami.
- Kryteria F3 rozszerzone o obraz `src=`, przejście między prezentacjami o różnych
  rozdzielczościach, `hide_mouse` na viewport (p. 11). GIF w podglądzie zostaje jak upstream
  (pierwsza klatka).
- `set_layer_image(index, QImage)` jako interfejs dla F4; sesje i fokus zostają w F4 (p. 12).
- Budżet F3: ~6 h, raport przy 12 h (p. 13).

**Odpowiedź codex (bez zmian):**

**F3 można implementować po poprawkach planu.** D24 i D25 mają poprawny fundament, ale obecne kryteria nie domykają ścieżek zasobów, cyklu życia miniatury i przełączania kompozycji. D26 wymaga poprawienia metodologii pomiaru przed zmianą progu.

Poniżej nowe ustalenia; nie traktuję rozstrzygnięć D1–D22 jako ponownie otwartych problemów. To recenzja statyczna: nie uruchamiałem renderów ani testów zapisujących pliki.

1. **[WAŻNE] A: 59,96 nie dowodzi rzeczywistej straty; 97% jest zbyt szeroką korektą uzasadnianą tym wynikiem.**

   **Dowód:** licznik „różnych klatek” porównuje pełne bajty obrazu z poprzednim odebranym obrazem — nie numery publikacji (`examples/measure_live.py:90–104`). Zerowanie liczników następuje dopiero po ticku, który odebrał `CUE_START`, a ten sam tick mógł już odebrać pierwszą klatkę (`examples/measure_live.py:85–105`, `:148–156`). Raport dla 540p odpowiada dokładnie **1799 zmianom / 30,0010164 s**, również dla 1080p wychodzi 1799 zmian (`live-measurement.json:9–10`, `:27–28`).

   **Konsekwencja:** wynik jest zgodny z efektem granic okna i wyzerowania już odebranej pierwszej klatki. Nie pozwala rozstrzygnąć, czy dodatkowo wystąpiły opuszczone publikacje. Producent pomija spóźnione terminy, więc takie straty są możliwe (`src/manimcue/live_scene.py:523–524`). Zdanie, że skończona średnia „nie przekroczy 60”, też jest zbyt mocne: zależy od sposobu zaliczania końców okna (`PLAN.md:180–181`).

   **Poprawka planu:** rozdzielić:
   - tempo publikacji producenta;
   - udział odebranych numerów klatek;
   - częstość zmian pikseli.

   Zapisywać `frame_id`, timestamp publikacji i czas odbioru w jednym ustalonym oknie. Dla dotychczasowego licznika dopuścić błąd granic **do dwóch klatek na 30 s**, zamiast od razu 54 klatek wynikających z 97%. Próg 97% można przyjąć jako świadomy budżet strat, ale nie jako naprawę kwantyzacji. Zachować też osobno wymaganie 1080p ≥30 — „97% żądanego” przy żądanych 60 zmieniłoby je na 58,2 (`examples/measure_live.py:139`, `PLAN.md:521`).

2. **[WAŻNE] A: pomocnicze `received_fps` jest liczone z innego okresu niż mianownik.**

   **Dowód:** `elapsed` zostaje zamrożony po 30 s (`examples/measure_live.py:153–156`), lecz potem odbiornik zbiera dalsze klatki do końca animacji oraz podczas 40 prób opóźnienia (`:159–180`). Dopiero na końcu oblicza `receiver.received / elapsed` (`:187`). Stąd raportowane około 63,4 odebranych klatek/s przy żądanych 60 (`live-measurement.json:11`, `:29`).

   **Konsekwencja:** tej wartości nie można użyć do wyjaśnienia różnicy między publikacjami, odbiorem i zmianami obrazu.

   **Poprawka planu:** zamrozić wszystkie liczniki oraz próbki pomiarowe razem z końcem okna. Zapisać surowe liczby, nie tylko ilorazy. To powinno poprzedzić formalne zamknięcie pomiaru F2.

3. **[DROBNE] A: skip TeX jest zgodny z D22, ale wynik F2 trzeba opisać jako częściowo niesprawdzony środowiskowo.**

   **Dowód:** test sonduje rzeczywistą kompilację przed uruchomieniem sceny i pomija ją po `LatexError` lub `OSError`; błędy późniejszego renderu sceny pozostają porażką (`tests/test_live_corpus.py:357–376`). Manimgl rzeczywiście przekazuje `-no-pdf` i zamienia niezerowy kod kompilatora w `LatexError` (`.venv/Lib/site-packages/manimlib/utils/tex_file_writing.py:108–130`). Jawny skip środowiskowy przewiduje `SPEC.md:493–494`.

   **Konsekwencja:** to poprawne pominięcie niedziałającego toolchainu. Jednak ogólne „14 scen korpusu zielone” zaciera brak wykonania sceny TeX (`PLAN.md:168–169`). Sam kod potwierdza przekazywaną opcję; nie potwierdza konkretnej diagnozy MiKTeX bez logu kompilatora.

   **Poprawka planu:** podać osobno passed/skipped, zachować diagnozę sondy i wymagać wykonania testu na przynajmniej jednym działającym środowisku TeX przed deklaracją pełnego pokrycia tej sceny.

4. **[WAŻNE] B: D24 automatyzuje pola modeli, ale nie cały kontrakt ścieżek.**

   **Dowód:** wrapper pobiera pola przez `model_fields`, tworzy model i rozszerza sygnaturę (`src/manimcue/slides/config.py:217–238`). `PreSlideConfig` dziedziczy bazę i dostaje jej `model_dump()` (`:254–270`), analogicznie `SlideConfig` (`:314–324`); zapis używa `model_dump_json()` (`:350–353`). To potwierdza automatyczny przepływ **zadeklarowanego pola**. Natomiast `from_file` przepisuje wyłącznie `file` i `rev_file`, przed walidacją (`:338–348`).

   **Konsekwencja:** względne `scene_file` i `thumbnail` wymagają jawnego przejścia po `layers` przed `model_validate`; inaczej `FilePath` sprawdzi je względem katalogu roboczego. Równie ważny jest moment deklaracji: `cls(**kwargs)` waliduje `scene_file` już podczas `next_slide`, przed zapisem JSON (`:222`).

   **Poprawka planu:** określić dwa niezależne kontrakty:
   - autorskie `scene_file` — względem CWD renderu albo pliku decku; wybrać jedno;
   - zapisane ścieżki — względem `path.parent.parent`, z normalizacją przed walidacją.

   Miniatura może być `None` przed generowaniem; dla prezentacji wczytywanej do F3 trzeba wymagać istniejącej miniatury albo jawnego błędu. Dodać round-trip wykonywany z innego CWD. Dopisać też eksport `LiveLayer`: obecne publiczne API eksportuje tylko klasy slajdów i wersję (`src/manimcue/slides/__init__.py:13–22`).

5. **[WAŻNE] B: największym problemem zgodności jest kopiowanie zasobów, nie iterowanie po polach ani domyślna wersja.**

   **Dowód:** `copy_to` kopiuje wyłącznie `file` oraz opcjonalnie `rev_file` (`src/manimcue/slides/config.py:363–374`); korzysta z niego eksport HTML (`src/manimcue/slides/convert.py:659–660`). Wizard iteruje po **klawiszach**, nie po polach slajdu (`src/manimcue/slides/wizard/wizard.py:69`). Testy konfiguracji wykonują walidację i serializację bez porównania ze sztywnym słownikiem prezentacji (`tests/slides/test_config.py:23–29`); test renderu porównuje wybrane właściwości (`tests/slides/test_slide.py:78–92`).

   **Konsekwencja:** nie znalazłem podstaw do twierdzenia, że samo `version=2` złamie te testy. Dodanie `layers` również nie zmienia liczby klawiszy wizarda. Za to `copy_to` po cichu zgubi nowe zasoby, jeśli pozostanie dostępne dla warstw.

   **Poprawka planu:** w F3 najprościej jawnie odrzucać warstwy również w `copy_to`, dopóki nie powstanie kontrakt pakowania scen i zależności. D23 egzekwować we wspólnej walidacji konwerterów, aby obejmował także bezpośrednie użycie ich API (`src/manimcue/slides/convert.py:145–158`), przed tworzeniem plików wyjściowych. Komunikat powinien identyfikować prezentację, slajd i scenę.

   Dla wersji dodać walidację obsługiwanego zakresu; sama wartość domyślna nie odrzuci wersji 3. Nie ma potrzeby przepisywania starych fixture’ów tylko po to, by dodać domyślne pole.

6. **[WAŻNE] B: `rect` jest dobrym formatem, ale brakuje rozdzielenia geometrii i rozdzielczości renderowania.**

   **Dowód:** plan uzależnia rozdzielczość procesu od `rect × resolution` (`PLAN.md:217–219`), podczas gdy `LiveSession` tworzy bufor o rozmiarze ustalonym przy starcie (`src/manimcue/live_session.py:50–58`), a czytelnik wymaga dokładnie tych wymiarów (`src/manimcue/frame_buffer.py:83–94`).

   **Konsekwencja:** animowanie skali w F5 nie powinno oznaczać ciągłego restartowania procesu i zmiany bufora. Ponadto dodatni, ale bardzo mały ułamek może po zaokrągleniu dać wymiar zero, odrzucany przez bufor (`src/manimcue/frame_buffer.py:33–36`).

   **Poprawka planu:** zachować ułamki jako początkową geometrię; ustalać rozmiar renderu raz przy starcie sesji, z jawnym zaokrągleniem i minimum jednego piksela. W F5 przesuwać i skalować element graficzny. Walidować skończoność liczb. Ograniczenie „całość w kadrze” określić jako ograniczenie początkowego układu F3, aby nie zamknąć późniejszej animacji wejścia/wyjścia poza kadr.

7. **[WAŻNE] C: spawn z obu wskazanych launcherów jest poprawny; gwarancja wymaga testu obu ścieżek.**

   **Dowód:** render uruchamia `python -m manim render` albo `python -m manimlib -w` (`src/manimcue/slides/render.py:52–59`). Stdlib przekazuje nazwę modułu głównego z `__spec__` (`C:/Users/Franek/AppData/Roaming/uv/python/cpython-3.13.2-windows-x86_64-none/Lib/multiprocessing/spawn.py:192–195`), a dla nazw kończących się `.__main__` **pomija ponowne wykonanie modułu** (`:250–257`). Przygotowanie poprzedza odtworzenie obiektu procesu (`:126–135`). Worker czyści argv przed importem backendu (`src/manimcue/live_worker.py:10–16`).

   **Konsekwencja:** w tych dwóch przypadkach dziecko nie powtórzy renderu ani importów z `manim.__main__`/`manimlib.__main__`. Nie ma podstaw, by oczekiwać przeniesienia zaimportowanego CE z pamięci rodzica. Dziedziczone są jednak `sys.path`, argv i CWD (`spawn.py:181–187`, `:228–235`), a plik sceny zostaje wykonany od nowa (`src/manimcue/live_worker.py:18–23`); jego importy mogą więc ponownie sprowadzić CE.

   **Poprawka planu:** rozszerzyć kryterium 3 o launcher GL i sprawdzenie importów w dziecku. Nie obiecywać ogólnej izolacji każdego możliwego launchera: uruchomienie skryptu po ścieżce powoduje jego wykonanie jako `__mp_main__`, zanim target oczyści argv (`spawn.py:275–300`).

8. **[KRYTYCZNE] C: blokujący generator miniatury potrzebuje timeoutu startu i bezwarunkowego doprowadzenia sesji do końca.**

   **Dowód:** `LiveSession` nie zależy od Qt; wykonuje obsługę IPC w `poll()` (`src/manimcue/live_session.py:3–12`, `:104–152`). `request_stop()` jedynie ustawia termin i kolejkuje shutdown (`:172–175`); zabicie procesu oraz sprzątanie następują dopiero w kolejnych `poll()` (`:131–150`, `:177–187`). Brak timeoutu samego startu. `build_objects()` wykonuje się przed READY (`src/manimcue/live_scene.py:402–404`).

   **Konsekwencja:** pętla „czekaj na READY” może zawiesić render bez końca. Samo `request_stop()` w `finally` pozostawi proces i zasoby, jeżeli rodzic przestanie pompować sesję.

   **Poprawka planu:** generator bez Qt ma:
   - pompować `poll()` i `try_read_frame()` aż dostanie READY **oraz** własną pierwszą klatkę;
   - mieć osobny, konfigurowalny timeout inicjalizacji;
   - w `finally` wywołać `request_stop()` i dalej pompować do odebrania zakończenia;
   - zapisywać PNG i aktualizować metadane dopiero po sukcesie.

   Samo API nadaje się do takiej pętli. Dodać test zawieszonego budowania oraz błędu zapisu PNG, sprawdzający brak pozostawionego workera.

9. **[WAŻNE] C: hash jednego pliku nie identyfikuje pierwszej klatki sceny.**

   **Dowód:** cache ma obejmować bajty pliku, klasę i rozmiar (`PLAN.md:224–227`). Worker dodaje katalog sceny do ścieżki importów i wykonuje moduł (`src/manimcue/live_worker.py:18–23`), a pierwsza klatka powstaje po dowolnym kodzie `build_objects()` (`src/manimcue/live_scene.py:402–403`).

   **Konsekwencja:** zmiana importowanego modułu, tekstury albo danych może pozostawić starą miniaturę bez zmiany klucza. Również identyczne pliki scen w różnych katalogach mogą importować różne zależności.

   **Poprawka planu:** bez budowania automatycznego grafu importów dodać jawne zależności cache lub autorski `cache_key`, uwzględnić tożsamość ścieżki i wersję generatora. Zapewnić wymuszenie regeneracji. Generowanie umieścić po filtrach offsetu i `skip_animations`, aby pomijane slajdy nie uruchamiały scen live (`src/manimcue/slides/slide/base.py:617–637`).

10. **[WAŻNE] D: D25 jest wykonalne, ale przeniesienie `frame_changed` nie jest mechaniczną zmianą nazwy sinka.**

   **Dowód:** lokalne API udostępnia `QGraphicsVideoItem.videoSink()`, `setSize()` i `setAspectRatioMode()` (`.venv/Lib/site-packages/PySide6/QtMultimediaWidgets.pyi:22–39`). Scena udostępnia listę widoków, a widok przyjmuje scenę (`.venv/Lib/site-packages/PySide6/QtWidgets.pyi:3132`, `:3529`). Dotychczasowy callback zachowuje ostatnią klatkę i przesyła ją do drugiego sinka (`src/manimcue/slides/present/player.py:685–690`).

   **Konsekwencja:** dwa widoki jednej sceny są właściwą konstrukcją; nie należy tworzyć drugiego wyjścia dekodera dla Info. Same `.pyi` nie gwarantują jednak zachowania konkretnego backendu GPU na dwóch monitorach. Ponadto przy nowej scenie na każdy slajd ostatnia klatka starego sinka sama nie przejdzie do nowej sceny.

   **Poprawka planu:** usuwać przekazywanie do `Info.video_sink`; oba widoki mają oglądać ten sam element. Ochronę przechowywać przy odpowiednim sinku, z warunkiem, że poprzednia klatka jest poprawna. Przetestować początkową niepoprawną klatkę, aby ponowne ustawienie pustej klatki nie tworzyło rekurencji sygnału. Osobno określić przejście między kompozycjami — zachować poprzedni obraz do gotowości nowego. Kryterium 5 nie zastępuje tego testu przejścia.

11. **[WAŻNE] D/E: obecne osiem kryteriów nie zabezpiecza najważniejszych rozgałęzień playera.**

   **Dowód:** obraz i wideo mają osobne widgety oraz osobne ścieżki ładowania (`src/manimcue/slides/present/player.py:268–278`, `:450–487`). GIF jest w bieżącym widoku traktowany jako wideo (`:452–455`), ale preview rozgałęzia wyłącznie po `SlideType.Video` (`:555–570`). Podgląd może przejść do innej prezentacji (`:424–427`), a jego obecna ścieżka obrazu bierze rozdzielczość prezentacji bieżącej (`:567`). Testy upstreamu sprawdzają głównie zakończenie CLI, także dla fullscreen, kursora i proporcji (`tests/slides/test_present.py:47–85`).

   **Konsekwencja:** pozostawienie stosu „obraz/wideo” może ukrywać całą warstwę przy bazie `src=`. Zielone stare testy nie potwierdzą poprawnych pikseli, geometrii ani zachowania kursora.

   **Poprawka planu:** zastąpić stos jednym widokiem kompozycji; przełączać widoczność bazowych elementów obrazu/wideo. Dodać do istniejących kryteriów:
   - `src=PNG` z warstwą oraz GIF w obu podglądach;
   - przejście między prezentacjami o różnych rozdzielczościach i kolorach tła, również start bezpośrednio na dalszym slajdzie;
   - `keep` i `ignore` dla **całej kompozycji**, bez dodatkowego niespójnego letterboxingu bazy;
   - fullscreen → okno → resize oraz `hide_mouse` nad viewportem;
   - reverse/replay i pętlę slajdu z nieruchomą miniaturą; F3 powinno jawnie pozostawiać ją niezmienioną (`player.py:489–499`, `:625–635`);
   - pomijanie slajdu z warstwą przez `skip_animations`.

   Żadne z ośmiu kryteriów nie jest zbędne. Kryterium 4 można uściślić przez próbki pikseli zamiast pełnego zrzutu; kryteria 5 i 8 sprawdzają różne rzeczy. Rozszerzyć kryterium 3 o awarie, cache i GL, zamiast mnożyć puste kryteria.

12. **[WAŻNE] F: kompozycja powinna przyjmować obrazy, ale nie zarządzać `LiveSession`; współdzielony fokus wymaga rozdzielenia widoków.**

   **Dowód:** `OwnedFrame` zawiera własne bajty RGBA i wymiary (`src/manimcue/frame_buffer.py:15–24`, `:103–109`); element pixmapy przyjmuje również `QImage` (`.venv/Lib/site-packages/PySide6/QtWidgets.pyi:2856`). Fokus elementu jest właściwością sceny (`:3108–3109`), natomiast obecny player od razu wywołuje `dispatch` dla każdego klawisza (`src/manimcue/slides/present/player.py:695–698`). Sygnały zmiany indeksu są emitowane przed późniejszym ładowaniem medium (`:402`, `:523–535`).

   **Konsekwencja:** związanie sesji z elementem graficznym utrudni osobny preview i wymianę miniatury na live. Automatyczny fokus elementów wspólnej sceny może też niechcący aktywować sterowanie przez Info. Podpięcie startu workera do każdego sygnału zmiany indeksu może uruchamiać sesję dla stanu przejściowego.

   **Poprawka planu:** w F3 zapewnić prostą operację aktualizacji obrazu konkretnej warstwy, np. `set_layer_image(index, QImage)`, z zachowaniem geometrii i własności pikseli. Konwersję `OwnedFrame` oraz sesje pozostawić kontrolerowi playera w F4. Aktywację identyfikować kliknięciem w uprawnionym widoku; Info domyślnie uczynić podglądem. Start/stop sesji powiązać z jedną zatwierdzoną zmianą bieżącego slajdu, nie samym setterem indeksu. To przygotowanie interfejsu, bez implementowania F4 w F3.

13. **[DROBNE] E: ~3 h jest budżetem prototypu, nie wiarygodnym szacunkiem całej akceptacji.**

   **Dowód:** zakres obejmuje jednocześnie model i ścieżki, proces miniatury, cache, zastąpienie powierzchni wyświetlania oraz próbę wizualną (`PLAN.md:216–257`). Dotyka niezależnych ścieżek zapisu, bieżącego medium i preview (`src/manimcue/slides/slide/base.py:591`, `src/manimcue/slides/present/player.py:450`, `:555`).

   **Konsekwencja:** pomyślny prototyp dwóch widoków nie zamyka integracji ani regresji.

   **Poprawka planu:** oszacować osobno model/miniaturę i player/akceptację. Roboczo przyjąłbym **6–10 h**, z raportem nadal po 6 h zgodnie z obecną regułą. To szacunek recenzencki, nie wynik pomiaru pracy.

**Werdykt: tak, F3 można implementować po poprawkach**, przede wszystkim po dopisaniu kontraktu ścieżek, timeoutu i sprzątania generatora miniatur, unieważniania cache oraz pełnego przełączania kompozycji. F2 można domknąć z jawnym skipem TeX; zmianę progu fps należy poprzedzić naprawą i doprecyzowaniem pomiaru.

---

## Runda 9 — codex, 2026-10-22: kontrakt F4 (warstwa live w playerze)

Pytania: `codex-round9-prompt` (cykl życia sesji, pompowanie i zamykanie, fokus i klawisze,
koszt obrazu, błędy i stany brzegowe, granica F4/F5). codex-cli 0.160.0, `-s read-only`,
z małymi próbami Qt offscreen.

**Co weszło:**
- Sesje usuwane po `not running`, niezależnie od `state` (p. 1).
- Zamykanie: `begin_shutdown()` w `Player.close()` (asynchronicznie, idempotentnie),
  końcowe `shutdown()` z blokującym odbiorem w `finally` wokół `app.exec()` — po wyjściu
  z pętli Qt (D27, p. 2).
- `set_layers` pomija tę samą listę warstw — replay i reverse → normalny kierunek nie
  przywracają miniatury nad obraz live (p. 3).
- „Ten sam slajd” = klucz (prezentacja, indeks), nie tożsamość obiektu; reverse dotyczy bazy,
  live startuje od początku przy wejściu (D27, p. 4).
- Sesje zatrzymywane pompowane tylko do odbioru, bez klatek i błędów dla bieżącego slajdu;
  test A → B → A (p. 5).
- Router: strzałki przy aktywnej, niegotowej warstwie konsumowane bez wysłania; autorepeat
  konsumowany bez wysłania; kody bez modyfikatorów jak `dispatch` (p. 6).
- Aktywność: oba okna to wspólny obszar — zwolnienie przy `applicationStateChanged`, nie przy
  przejściu główne ↔ Info (D27, p. 7).
- Timeout przygotowania w GUI (60 s), błąd dotyczy tylko swojej warstwy, testy błędu przed
  READY i w cue (p. 8). Zewnętrzne zabicie procesu i dwie warstwy na slajdzie — bez osobnych
  testów: ta sama ścieżka `ERROR` z `LiveSession` (F2, `test_worker_dies_holding_lock`).
- Pomiar ścieżki GUI: test przepustowości ≥ 80% z 60 fps przez 5 s cue (p. 9).
- `set_layer_image` bierze prostokąt z `set_layers`, nie z obrysu (p. 10).
- Obwódka w scenie (widoczna na projektorze) zaakceptowana na F4; do oceny prelegenta (p. 11).

**Odpowiedź codex (bez zmian):**

**F4 można implementować po poprawkach planu.** Najpoważniejsze luki dotyczą zakończenia aplikacji, rozróżnienia stanu sesji od zakończenia procesu oraz zachowania obrazu przy ponownym ładowaniu tego samego slajdu.

Przegląd read-only. Wykonałem małe próby Qt offscreen; nie wykonywałem testu prezentacji na dwóch ekranach. Poniżej nowe ustalenia, bez ponownego otwierania rozstrzygnięć rund 6–8.

1. **[KRYTYCZNE] B: „aż do STOPPED” musi oznaczać zdarzenie lub `running == False`, nie stan sesji.**

   **Dowód:** po błędzie `poll()` sprząta zasoby i emituje `"STOPPED"`, ale pozostawia `state == "error"` (`src/manimcue/live_session.py:138–150`). To zachowanie jest jawnie sprawdzane w `tests/test_live_session.py:319–325`. Właściwość `running` oznacza proces jeszcze nieodebrany (`src/manimcue/live_session.py:177–180`).

   **Konsekwencja:** kontroler oczekujący `state == "stopped"` nigdy nie usunie błędnej sesji; zamykanie może wisieć bez końca. Samo wywołanie `kill()` też nie kończy odbioru: Windows ustala kod zakończenia dopiero po potwierdzeniu zakończenia procesu (`C:/Users/Franek/AppData/Roaming/uv/python/cpython-3.13.2-windows-x86_64-none/Lib/multiprocessing/popen_spawn_win32.py:105–144`).

   **Poprawka planu:** usuwać sesję po `not session.running`; zachowywać osobno diagnozę błędu. Po wymuszeniu zakończenia nadal pompować. Jeden timer wystarczy, dopóki działa pętla zdarzeń i kontroler pozostaje właścicielem wszystkich kończących się sesji.

2. **[KRYTYCZNE] A/B: zamknięcie potrzebuje osobnego, idempotentnego protokołu i zabezpieczenia po `app.exec()`.**

   **Dowód:** `Player.close()` zamyka Info i okno główne, `Player.closeEvent()` ponownie woła `close()`, a Info przekazuje swój `closeEvent` do playera (`src/manimcue/slides/present/player.py:268–269`, `:578–581`, `:672–673`, `:165–166`). CLI kończy przez `sys.exit(app.exec())`, bez końcowego odbioru sesji (`src/manimcue/slides/present/__init__.py:360–363`). Termin wymuszenia jest wykonywany wyłącznie przez `poll()` (`src/manimcue/live_session.py:131–150`).

   **Konsekwencja:** dopisanie jedynie `request_stop()` do `close()` nie wystarczy. Po zakończeniu pętli Qt timer nie wykona wymuszenia. Przy normalnym końcu interpretera multiprocessing wykonuje `join()` aktywnych dzieci, więc objawem może być wiszący proces rodzica; przy gwałtownym zakończeniu rodzica pozostaje ryzyko osieroconego workera (`C:/Users/Franek/AppData/Roaming/uv/python/cpython-3.13.2-windows-x86_64-none/Lib/multiprocessing/util.py:342–349`).

   Na Windows `SharedMemory.unlink()` niczego nie usuwa: konieczne jest zamknięcie wszystkich uchwytów (`C:/Users/Franek/AppData/Roaming/uv/python/cpython-3.13.2-windows-x86_64-none/Lib/multiprocessing/shared_memory.py:225–249`).

   **Poprawka planu:** wspólne, odporne na ponowne wejście `begin_shutdown()` dla obu okien i `exit_after_last_slide`. Podczas zwykłego zamykania zatrzymać sesje asynchronicznie, pozostawiając pętlę Qt do ich odebrania. Dodać `finally` wokół `app.exec()` z końcowym pompowaniem bez Qt. Blokujące oczekiwanie w aktywnym GUI łamałoby zasadę nieblokowania; końcowe sprzątanie po wyjściu z pętli jest inną fazą działania i należy zapisać ten wyjątek jawnie.

3. **[WAŻNE] A/D: zachowanie sesji dla tego samego slajdu nie zachowuje jego elementów graficznych.**

   **Dowód:** `load_current_media()` zawsze wykonuje `composition.set_layers()` (`src/manimcue/slides/present/player.py:430–435`), które usuwa wszystkie elementy i tworzy je ponownie z miniatur (`src/manimcue/composition.py:67–84`). Powrót z reverse do kierunku normalnego zachowuje indeks slajdu i wywołuje ponowne ładowanie (`src/manimcue/slides/present/player.py:493–509`). Odbiornik nie zwraca ponownie niezmienionej klatki (`src/manimcue/frame_buffer.py:101–109`).

   **Konsekwencja:** kontroler zachowa działającą sesję, lecz obraz może wrócić do miniatury i pozostać taki do następnej publikacji. Referencje do starych elementów i obwódki również przestaną odpowiadać kompozycji.

   **Poprawka planu:** nie przebudowywać warstw przy zachowaniu tej samej sesji albo po przebudowie obowiązkowo przywrócić ostatnią posiadaną klatkę i stan aktywacji. Dodać test statycznego live podczas reverse → odtwarzanie normalne.

4. **[WAŻNE] A: tożsamość obiektu nie definiuje całej semantyki reverse ani „tego samego slajdu”.**

   **Dowód:** `reverse()` ustawia flagę reverse i przechodzi do poprzedniego slajdu; na pierwszym slajdzie przejście wraca bez ładowania (`src/manimcue/slides/present/player.py:481–491`, `:605–607`). Zwykłe ładowanie wybiera `rev_file` według tej flagi (`:463–468`). Rozdzielczość warstw zależy od prezentacji, nie tylko konfiguracji slajdu (`src/manimcue/composition.py:95–99`).

   **Konsekwencja:** wejście reverse na poprzedni slajd z warstwą uruchomi świeżą, początkową scenę live nad cofanym filmem. Samo porównanie `is` tego nie rozstrzyga. Pomija też kontekst prezentacji, jeśli ten sam obiekt konfiguracji zostanie użyty ponownie.

   **Poprawka planu:** klucz bieżącego miejsca określić jako prezentacja + indeks slajdu; kierunek traktować jako osobny stan. Dla F4 przyjąć jawnie np. „reverse dotyczy bazy; live pozostaje niezależny i zaczyna od początku przy wejściu”. Sprawdzić reverse na pierwszym slajdzie oraz reverse → next. Nie obiecywać cofania kompozycji.

5. **[WAŻNE] A/E: sesje zatrzymywane muszą utracić prawo aktualizacji bieżącego slajdu.**

   **Dowód:** zatrzymanie tylko kolejkuje `shutdown` i ustawia termin (`src/manimcue/live_session.py:172–175`); do odebrania procesu sesja nadal może dostarczać zdarzenia i klatki (`:104–152`, `:160–170`). Aktualizacja kompozycji wskazuje warstwę samym indeksem (`src/manimcue/composition.py:86–93`).

   **Konsekwencja:** przy szybkim przejściu A → B spóźniona klatka warstwy 0 z A może zastąpić warstwę 0 w B. Spóźniony błąd A może zwolnić aktywację B albo zmienić tytuł Info.

   **Poprawka planu:** rozdzielić sesje bieżące i odbierane po zatrzymaniu. Drugie pompować wyłącznie dla zakończenia i diagnostyki; nie kierować ich obrazu ani stanu aktywacji do aktualnej kompozycji. Dodać test A → B → A przed zakończeniem pierwszego workera.

6. **[WAŻNE] C: router potrzebuje jawnej polityki autorepeat, modyfikatorów i klawiszy podczas startu.**

   **Dowód:** obecny dispatcher otrzymuje wyłącznie `event.key()` (`src/manimcue/slides/present/player.py:675–678`), a konfiguracja dopasowuje sam kod klawisza (`src/manimcue/slides/config.py:70–76`, `:134–143`). PySide6 udostępnia `isAutoRepeat()` i `modifiers()` (`.venv/Lib/site-packages/PySide6/QtGui.pyi:3561–3565`). Worker kolejkuje kolejne `next`/`back`; nadejście komendy podczas cue może je przerwać (`src/manimcue/live_scene.py:468–469`, `:515–516`).

   **Konsekwencja:** przytrzymana strzałka może szybko przerywać i przewijać cue. Niejasne pozostaje również, czy strzałka przy aktywnej, ale jeszcze niegotowej warstwie zostaje skonsumowana, czy przesuwa prezentację.

   **Poprawka planu:** podczas startu konsumować `NEXT/PREVIOUS`, bez wysyłania i bez przejścia slajdu. Dla live ignorować autorepeat albo jawnie zaakceptować jego skutki. Modyfikatory obsługiwać zgodnie z dotychczasowym dopasowaniem kodów lub świadomie zmienić kontrakt. Testować również niestandardowe przypisania i zdarzenia przekazane przez Info.

7. **[WAŻNE] C: plan zmienia „utratę aktywności okna” na „utratę aktywności aplikacji”; trzeba to nazwać decyzją.**

   **Dowód:** D20 mówi o oknie (`SPEC.md:468–469`), plan o `applicationStateChanged` (`PLAN.md:287–290`). Lokalne API rozróżnia ten sygnał i `focusWindowChanged` (`.venv/Lib/site-packages/PySide6/QtGui.pyi:2514–2517`). Windows Qt próbuje przekazać bezpośrednio następne własne okno zamiast pośredniego braku fokusu; jest to warunkowe zachowanie backendu, nie gwarancja kolejności wszystkich zdarzeń ([Qt, `qwindowscontext.cpp`, linie 1123–1159](https://raw.githubusercontent.com/qt/qtbase/6.12/src/plugins/platforms/windows/qwindowscontext.cpp)).

   **Konsekwencja:** przejście główne → Info powinno zachować aktywację, jeżeli ma działać kryterium sterowania live z Info. Dosłowne zwalnianie przy dezaktywacji każdego okna przeczyłoby temu.

   **Poprawka planu:** przyjąć jawnie „oba okna tworzą wspólny obszar aktywności”. Dodać próbę Windows: główne → Info → główne oraz Alt-Tab na zewnątrz, także z przytrzymaną strzałką.

   Sam mechanizm kliknięcia jest poprawny: lokalne sygnatury są w `.venv/Lib/site-packages/PySide6/QtWidgets.pyi:3455–3457`, `:3500`; współrzędne viewportu potwierdza [dokumentacja Qt](https://doc.qt.io/qt-6/qgraphicsview.html#itemAt). Próba offscreen potwierdziła kliknięcie przy ustawionym tutaj `NoFocus` (`src/manimcue/composition.py:127–129`). `NoFocus` nie dowodzi natomiast kolejności natywnych zdarzeń aktywacji Windows.

8. **[WAŻNE] E: kryteria nie obejmują pełnego błędu przygotowania ani niezależności dwóch warstw.**

   **Dowód:** brak klasy sceny trafia do raportowania błędu workera (`src/manimcue/live_worker.py:24–26`, `:46–50`), a `build_objects()` poprzedza READY (`src/manimcue/live_scene.py:402–404`). W GUI nie ma obecnie limitu czasu startu w `LiveSession`; termin jest ustawiany dopiero przez `request_stop()` (`src/manimcue/live_session.py:45–68`, `:172–175`). Model dopuszcza listę warstw (`src/manimcue/slides/config.py:220`), natomiast kryterium błędu F4 dotyczy wyjątku w cue (`PLAN.md:307–308`).

   **Konsekwencja:** wiszące budowanie może pozostawić wiecznie „ładującą się” warstwę. Błąd nieaktywnej warstwy może niepotrzebnie odebrać sterowanie drugiej.

   **Poprawka planu:** dopisać timeout przygotowania GUI oraz testy: nieistniejąca klasa, wyjątek przed READY, zewnętrzne zabicie procesu, dwie sesje z jedną aktywną i błąd każdej z nich osobno. Zwolnienie aktywacji powinno dotyczyć sesji, która ją posiada. Dodać start bezpośrednio na slajdzie z warstwą, `src=`, `start_paused` i zamknięcie przed READY.

9. **[WAŻNE] D: brakuje mierzalnej akceptacji całej ścieżki GUI; nie ma dowodu, że konwersja będzie wąskim gardłem.**

   **Dowód:** odbiornik kopiuje payload i następnie odwraca wiersze do kolejnego `bytes` (`src/manimcue/frame_buffer.py:103–109`); kompozycja wykonuje `QPixmap.fromImage()` (`src/manimcue/composition.py:86–93`). Konstruktor nad `bytes` jest dostępny lokalnie (`.venv/Lib/site-packages/PySide6/QtGui.pyi:3018–3020`). Wspólną scenę oglądają dwa widoki (`src/manimcue/slides/present/player.py:250`, `:265`, `:57`).

   **Konsekwencja:** sam payload przy 60 fps to około **61 MB/s dla 672×378** albo **498 MB/s dla 1080p**, przed dodatkowymi kopiami i rysowaniem. Wspólna scena pozwala konwertować raz; dwa widoki nadal wymagają osobnego rysowania. Istotności kosztu nie da się ustalić ze statycznego przeglądu.

   **Poprawka planu:** zmierzyć czas odczytu, konwersji, opóźnienie timera i responsywność klawiatury z Info widocznym oraz ukrytym. Pompować statusy wszystkich sesji przed kosztownymi aktualizacjami obrazu.

   `OwnedFrame` trzymany lokalnie do zakończenia synchronicznego `fromImage()` zapewnia życie wejściowych bajtów; nie potrzeba profilaktycznej dodatkowej kopii `QImage`. Nie uzasadniać tego jednak uniwersalną obietnicą „`fromImage` zawsze kopiuje”: Qt opisuje konwersję i współdzielenie zależne od wariantu ([QImage](https://doc.qt.io/qt-6/qimage.html#QImage-3), [QPixmap](https://doc.qt.io/qt-6/qpixmap.html#fromImage)).

10. **[WAŻNE] D/F: aktualizacja obrazu nie powinna ustalać geometrii na podstawie aktualnego obrysu sceny.**

    **Dowód:** `set_layer_image()` pobiera `sceneBoundingRect()`, po czym ustawia pozycję i zastępuje transformację skalowaniem (`src/manimcue/composition.py:91–108`). Istniejący test sprawdza jedną aktualizację bez obrotu (`tests/test_layers.py:184–196`).

    **Konsekwencja:** dla obecnej dodatniej skali nie wykazałem narastania błędu — również po 10 000 aktualizacji. Natomiast w F5 obrys po obrocie nie jest pierwotnym prostokątem: aktualizacja obrazu wyzeruje obrót i użyje powiększonej obwiedni.

    **Poprawka planu:** zachowywać lokalny prostokąt obrazu niezależnie od transformacji elementu lub jego rodzica. Aktualizacja pikseli nie może zmieniać pozycji, skali animowanej ani z-order. F4 nie musi implementować wspólnego startu i pauzy F5; powinno jedynie pozostawić przygotowanie sesji oddzielone od wysyłania cue, zgodnie z obecnym READY przed pętlą komend (`src/manimcue/live_scene.py:402–409`).

11. **[DROBNE] F: obwódka na projektorze jest wyborem interfejsu zgodnym z wcześniejszym kierunkiem D20.**

    **Dowód:** plan świadomie umieszcza ją we wspólnej scenie (`PLAN.md:288–289`); widoczna aktywacja była już rekomendacją rundy 7 (`REVIEW-LOG.md:142`). Nie jest to nowa wada architektury.

    **Konsekwencja:** publiczność zobaczy stan sterowania, a obwódka błędu może zostać zinterpretowana jako treść prezentacji.

    **Poprawka planu:** jawnie zaakceptować ten efekt albo rysować oznaczenia osobno dla widoków. To preferencja produktu, nie blokada F4.

**Werdykt: tak, F4 można implementować po poprawkach.** Wywołanie `show()` po zatwierdzonym ładowaniu i osobno w konstruktorze jest właściwym punktem integracji: normalne przejścia, przejścia między prezentacjami i automatyczne przejścia zbiegają się w `load_current_slide()`; replay i wznowienie pauzy go nie wymagają (`src/manimcue/slides/present/player.py:293–326`, `:481–509`, `:584–615`). Warunkiem jest domknięcie ustaleń 1–8, szczególnie zamykania oraz ponownego użycia sesji po przebudowie kompozycji.

---

## Runda 10 — codex, 2026-10-22: D28 (nawigacja kamerą) i przegląd kodu F4

Pytania: `codex-round10-prompt` (spójność D28 z D3/D9/D10/D21, poprawność `live_layers.py`,
zmian w kompozycji, playerze i scenie, jakość testów F4). Przegląd statyczny, `-s read-only`.

**Co weszło:**
- Bariera czeka na id ostatniej klatki **granicznej** (`live_boundary_id`), potwierdzenie
  porównywane z nim; regresja „koniec sekwencji → klatka nawigacji → next” — sprawdzona, że
  pada bez poprawki (p. 1).
- D28 poprawione: kamera **należy** do `SceneState` (manimgl dodaje ją do `mobjects`), więc
  `back` przywraca też widok sprzed cue, a nawigacja w trakcie cue animującego kamerę przegrywa
  z animacją. Osobna transformacja widoku prelegenta — odrzucona jako niepotrzebna na F4 (p. 2).
- Pan liczony jak w manimgl: wektor ekranu w stałym kadrze przez
  `from_fixed_frame_point(..., relative=True)`, więc idzie po płaszczyźnie obróconej kamery (p. 3).
- Zmiana slajdu i zamykanie zerują aktywację, przeciąganie i błędy bez odtwarzania starej
  obwódki; test dwóch warstw (błędna + aktywna) → slajd bez warstw (p. 4).
- Test przepustowości liczy aktualizacje w stałym oknie zegara w środku cue (p. 5).
- Testy: asercja aktywacji po kliknięciu przed READY; nawigacja przez surowe zdarzenia
  viewportu (press → move z lewym przyciskiem → release, dwuklik) (p. 6).
- Reset opisany dosłownie: kadr zastany na ostatniej klatce granicznej (p. 7).

**Odpowiedź codex (bez zmian):**

**F4 nie jest jeszcze gotowa do zamknięcia samą próbą prelegenta.** Najpoważniejsze nowe problemy dotyczą bariery po nawigacji oraz nieprawdziwego założenia, że kamera pozostaje poza historią. Przegląd był statyczny i read-only; nie uruchamiałem testów ani prezentacji.

1. **[KRYTYCZNE] Nawigacja w bezczynności może zakończyć poprawną sesję błędem bariery.**

   **Dowód:** publikacja widoku zwiększa wspólny `live_frame_id` (`src/manimcue/live_scene.py:413–415`, `:531–532`), ale odbiornik potwierdza wyłącznie klatki `boundary` (`src/manimcue/live_session.py:168–169`). Gdy `next` dochodzi do końca sekwencji, gałąź `SEQUENCE_END` wraca bez publikacji granicznej (`src/manimcue/live_scene.py:423–427`), po czym bariera czeka na aktualny identyfikator i po dwóch sekundach rzuca wyjątek (`:410`, `:516–522`).

   **Konsekwencja:** po ostatnim cue wystarczy obrócić kamerę, a potem nacisnąć →. Bariera czeka na potwierdzenie zwykłej klatki, którego sesja nigdy nie wysyła.

   **Poprawka:** przechowywać osobno identyfikator ostatniej klatki granicznej i oczekiwać potwierdzenia właśnie jego. Dodać regresję: koniec sekwencji → `view` → `next`, bez błędu po dwóch sekundach.

2. **[WAŻNE] D28 opiera się na błędnym założeniu: kamera należy do `SceneState`, więc `back` cofa widok.**

   **Dowód:** manimgl inicjalizuje `mobjects` kamerą (`.venv/Lib/site-packages/manimlib/scene/scene.py:111–116`), a `SceneState` kopiuje wszystkie `scene.mobjects` (`:875–887`). Live zapisuje ten stan przed cue (`src/manimcue/live_scene.py:429`), a cofanie tworzy transformacje zapisanych obiektów i wywołuje `undo()` (`:327–337`). Przeczy to komentarzowi „kadr kamery nie należy do SceneState” (`:490–491`).

   **Konsekwencja:** cue → ręczny obrót → `back` przywróci również wcześniejszą kamerę. Ponadto nawigacja podczas animacji kamery konkuruje z jej `interpolate()` wykonywanym po odczytaniu komend (`src/manimcue/live_scene.py:556`, `:575–577`).

   **Poprawka:** rozstrzygnąć osobno kamerę autora i nawigację prelegenta. Jeśli utrzymać D28, nakładać nawigację jako niezależną transformację widoku; samo wykluczenie kamery z historii zepsułoby cofanie autorskich cue kamery, takich jak `LiveGLThreeD.cue_orbit` (`tests/scenes/live_gl.py:198–200`).

3. **[WAŻNE] Pan przesuwa po osiach świata, a nie po płaszczyźnie ekranu obróconej kamery.**

   **Dowód:** obecne przesunięcie używa bezpośrednio `LEFT` i `UP` (`src/manimcue/live_scene.py:501–503`). Manimgl najpierw przelicza ruch przez `from_fixed_frame_point(..., relative=True)` (`.venv/Lib/site-packages/manimlib/window.py:129–137`), następnie przesuwa kamerę o `-d_point` (`.venv/Lib/site-packages/manimlib/scene/scene.py:751–752`).

   **Konsekwencja:** Shift+drag po obrocie sceny 3D nie podąża za kursorem; przy odpowiedniej orientacji ruch trafia częściowo w głąb sceny.

   **Poprawka:** przeliczać wektor ekranowy przez odwrotną macierz widoku. Sam wzór orbity ma właściwe znaki i skalę: manimgl przelicza ten wektor z powrotem do stałego kadru przed zmianą theta/phi (`.venv/Lib/site-packages/manimlib/scene/scene.py:745–749`).

4. **[WAŻNE] Zmiana slajdu może użyć indeksu błędnej warstwy w nowej, krótszej liście.**

   **Dowód:** player najpierw przebudowuje warstwy kompozycji, następnie woła `live.show()` (`src/manimcue/slides/present/player.py:448–454`). `show()` wykonuje `release()` przed wyczyszczeniem `failed` (`src/manimcue/live_layers.py:66–68`). `release()` przy aktywnej warstwie odtwarza obwódkę dla starego `min(failed)` (`:171–178`), indeksując już nowe `layer_rects` (`:186`).

   **Konsekwencja:** slajd ma dwie warstwy: jedna błędna, druga aktywna. Przejście na slajd bez warstw powoduje `IndexError` podczas ładowania.

   **Poprawka:** przy zmianie slajdu wyzerować aktywację, przeciąganie i błędy bez odtwarzania starej obwódki. Dodać test tego konkretnego przejścia.

5. **[WAŻNE] Test przepustowości może wisieć aż do timeoutu mimo poprawnych 60 fps.**

   **Dowód:** warunek zakończenia wymaga aktualizacji ponad `MOVE_RUN_TIME + 0.5` od pierwszej aktualizacji (`tests/test_live_layers.py:314`). Cue wykonuje tylko pięciosekundowy ruch (`tests/scenes/live_gl.py:88–93`), a po klatce granicznej bezczynność publikuje ponownie wyłącznie przy `live_view_dirty` (`src/manimcue/live_scene.py:440`, `:411–415`).

   **Konsekwencja:** po ostatniej klatce nie przychodzi aktualizacja potrzebna do zakończenia pomiaru. Test nie daje wiarygodnego dowodu kryterium wydajności.

   **Poprawka:** kończyć pomiar zdarzeniem `CUE_DONE` albo niezależnym zegarem; liczyć aktualizacje w ustalonym oknie cue.

6. **[WAŻNE] Test przed READY może przejść bez trafienia kliknięciem w warstwę, a test D28 omija obsługę ruchu myszy.**

   **Dowód:** test przed READY nie sprawdza `active == 0`; sprawdza tylko niezmieniony indeks i brak wysłania `next` (`tests/test_live_layers.py:212–218`). Na ostatnim slajdzie? Nie — pozostaje indeks 1, lecz błędny klik może też wynikać z niedopasowanego widoku; wymagana jest bezpośrednia asercja aktywacji. Test D28 wywołuje `player.live.drag()` i `double_click()` bez zdarzeń viewportu (`:281–289`).

   **Konsekwencja:** brak dowodu, że rzeczywisty drag i dwuklik docierają przez `SlideView.mouseMoveEvent`/`mouseDoubleClickEvent` (`src/manimcue/composition.py:166–174`).

   **Poprawka:** po kliknięciu sprawdzać aktywację; D28 testować przez press → move z lewym przyciskiem → release oraz dwuklik viewportu. `recorded_sends` przechwytuje właściwy obiekt sesji w obecnych testach, bo podmienia metodę konkretnej instancji (`tests/test_live_layers.py:132–140`, `:213`, `:226`).

7. **[DROBNE] Reset utrwala nawigację prelegenta jako nowy punkt powrotu.**

   **Dowód:** każda klatka graniczna bezwarunkowo kopiuje aktualną kamerę (`src/manimcue/live_scene.py:533–534`), a reset odtwarza tę kopię (`:507–508`). Zatem orbit → cue bez ruchu kamery → reset zachowuje orbitę.

   **Konsekwencja:** komentarz „widok autora” (`src/manimcue/live_scene.py:488`) obiecuje więcej niż implementacja. Reset oznacza faktycznie widok zastany na ostatniej granicy.

   **Poprawka:** nazwać tę semantykę dosłownie albo przechowywać osobno widok autora. Samo `become()` odtwarza punkty i uniforms (`.venv/Lib/site-packages/manimlib/mobject/mobject.py:727–729`), czyli centrum, rozmiar, orientację i ogniskową wynikającą z `fovy` (`.venv/Lib/site-packages/manimlib/camera/camera_frame.py:38–49`, `:245–246`). Nie znalazłem podstaw do uznania pojedynczej kopii kamery na granicy za istotny koszt; `copy()` kopiuje jej dane, a nie całą scenę (`.venv/Lib/site-packages/manimlib/mobject/mobject.py:665–699`).

D28 jako komendy niebędące cue jest wykonalne: `view` nie trafia do kolejki przerywającej animację (`src/manimcue/live_scene.py:475–478`, `:560–562`). Statyczny `wait` bez nawigacji nadal nie publikuje klatek wewnętrznych; istniejący test sprawdza właśnie taki przypadek (`tests/test_live_session.py:350–358`). Po nawigacji publikacja jest świadomym wyjątkiem (`src/manimcue/live_scene.py:588–591`). Niespójności wymagające naprawy to punkty 1–2.

Nie wykazałem nowego błędu własności bajtów `QImage`: `frame` pozostaje lokalnie żywy przez synchroniczną aktualizację obrazu (`src/manimcue/live_layers.py:106–116`). Info nie ma podłączonych sygnałów myszy do kontrolera; połączenia dotyczą głównego widoku (`src/manimcue/slides/present/player.py:254–258`, `:59`). `exit_after_last_slide` prowadzi przez `close()` (`:521–522`), a ponowne zatrzymywanie sesji nie przesuwa terminu wymuszenia (`src/manimcue/live_session.py:172–175`).

**Werdykt:** najpierw poprawić 1–5 i uzupełnić testy z punktu 6. Następnie próba dwóch ekranów powinna objąć rzeczywisty drag i reset, pan po obrocie, nawigację po końcu sekwencji oraz `back` po ręcznej zmianie kamery. Sama udana demonstracja obecnego testu D28 nie wystarczy, ponieważ omija on zdarzenia myszy (`tests/test_live_layers.py:282–289`).

---

## Runda 11 — codex, 2026-10-22: kontrakt F5 (warstwy pełne)

Pytania: `codex-round11-prompt` (unia modelu, zegar ruchu, wspólny start D17, reverse/replay/
pętla/auto_next, walidacja długości, kryteria i budżet). Przegląd read-only z próbą pydantic.

**Co weszło** (kontrakt F5 w `PLAN.md`, decyzje D29-D31 w `SPEC.md`):
- Unia dyskryminowana po `kind` z migracją v2 przed walidacją; `to_file` zawsze z bieżącą
  wersją (p. 1-2).
- Sesje live i playery klipów pod indeksem warstwy kompozycji; kryterium z przemieszanymi
  rodzajami (p. 3).
- `slide_file` = plik bazowy jednego slajdu przez `from_file`, test z innego CWD (p. 4).
- Zegar ruchu: `QElapsedTimer`, aktywny czas slajdu, nie `position()` (p. 5).
- Wspólny start: PoC zamiast założeń — przygotowanie pierwszych klatek obniżyło rozjazd z 67 ms
  do 18 ms przy 4 źródłach 1080p60; bariera z timeoutem i błędem pojedynczej warstwy (p. 6).
- Transport grupowy przez śledzenie stanu bazy (`playbackStateChanged`) — `next`, koniec pętli,
  `skip_all`, `auto_next`, `start_paused` bez osobnych wywołań; żądany stan w trakcie
  przygotowania (p. 7). Baza statyczna z własnym stanem, bez walidacji długości (p. 8).
- Reverse: `end_thumbnail` z renderu (p. 9).
- Walidacja długości: po renderze i raz przed prezentacją, tolerancja z czasów klatek,
  zwolnienia i błędy nazwane (p. 10). Pozycja klatek kluczowych poza kadrem dozwolona (p. 11).
- Kryteria: deterministyczne offscreen + integracyjne wideo z timeoutem; budżet 6 h jako cel
  prototypu, raport przy 12 h (p. 12).

**Odpowiedź codex (bez zmian):**

Przegląd read-only. Nie uruchamiałem prezentacji ani testów multimedialnych; wykonałem jedynie izolowaną próbę unii pydantic w pamięci. Poniżej nowe problemy propozycji F5, bez ponownego zgłaszania ustaleń rund 6–10.

1. **[WAŻNE] A: dyskryminator wymaga migracji przed walidacją, sam domyślny `kind` nie wystarczy.**

   **Dowód:** obecny `LiveLayer` nie ma `kind` (`src/manimcue/slides/config.py:179`), a `from_file()` przekazuje przetworzony słownik bezpośrednio do `model_validate()` (`src/manimcue/slides/config.py:422`). Izolowana próba potwierdziła: brak tagu w unii dyskryminowanej daje `union_tag_not_found`, mimo domyślnego tagu w modelu.

   **Konsekwencja:** dodanie `Field(discriminator="kind")` zerwie obiecaną obsługę plików v2.

   **Poprawka planu:** wybrać unię dyskryminowaną z `Literal["live"]` i `Literal["clip"]`; przed walidacją starych prezentacji dopisywać `kind="live"`. Zwykła unia również może działać, ale wymaga odrzucenia niejednoznacznych danych zawierających jednocześnie pola obu rodzajów.

   Wrapper nie wymaga osobnego adaptera: konstruuje model z argumentów i odczytuje adnotacje pól (`src/manimcue/slides/config.py:263`, `:273`). Przejścia przez `model_dump()` również zachowają poprawnie zadeklarowaną unię (`src/manimcue/slides/config.py:311`, `:365`). Dopisać test całej ścieżki `next_slide → PreSlideConfig → SlideConfig → JSON`, obejmujący słowniki i instancje modeli.

2. **[WAŻNE] A: v3 jest uzasadnione, ale plan nie opisuje ponownego zapisu dokumentu v2.**

   **Dowód:** wersja jest przechowywana w modelu (`src/manimcue/slides/config.py:384`), a `to_file()` zapisuje ją bez normalizacji (`src/manimcue/slides/config.py:427`). Obecny czytnik odrzuca wersje większe od obsługiwanej (`src/manimcue/slides/config.py:393`).

   **Konsekwencja:** dokument wczytany jako v2, następnie rozszerzony o klip, może zostać zapisany nadal jako v2. Starszy fork nie dostanie wtedy zaplanowanego komunikatu o nowym formacie.

   **Poprawka planu:** zapisywać aktualną wersję albo wyliczać minimalną wersję wymaganą przez zawartość. `FORMAT_VERSION = 3` jest właściwe dla nowej semantyki, lecz samo podniesienie stałej nie domyka migracji.

3. **[KRYTYCZNE] A/C: filtrowanie warstw live musi zachować indeksy całej kompozycji.**

   **Dowód:** kontroler tworzy sesję dla każdego elementu `slide.layers`, czytając `scene_file`, `scene_name` i `fps` (`src/manimcue/live_layers.py:74–83`). Następnie indeks sesji staje się indeksem elementu graficznego (`src/manimcue/live_layers.py:108–119`); klik również interpretuje indeks jako pozycję w `sessions` (`src/manimcue/live_layers.py:146–149`).

   **Konsekwencja:** po dodaniu unii obecna pętla nie obsłuży `ClipLayer`. Proste odfiltrowanie klipów też jest błędne: dla `[clip, live]` klatka live trafi do warstwy 0, a klik warstwy 1 nie wybierze sesji.

   **Poprawka planu:** przechowywać sesje pod indeksem warstwy kompozycji, np. `dict[layer_index, session]`. Tym samym indeksem adresować klatki, błędy, aktywację i geometrię. Kryterium musi zawierać przemieszane `[clip, live, image, live]`, nie tylko jeden live na końcu.

4. **[WAŻNE] A: `slide_file()` rozwiązuje hashe, ale nie oznacza „renderu całego slajdu”.**

   **Dowód:** plik bazowy powstaje niezależnie od warstw; miniatury warstw są dodawane dopiero później (`src/manimcue/slides/slide/base.py:654`, `:676–681`). Czytnik rozwiązuje bazowe ścieżki względem katalogu prezentacji (`src/manimcue/slides/config.py:407–414`), lecz dla warstw obecnie przepisuje tylko `scene_file` i `thumbnail` (`:417–420`).

   **Konsekwencja:** helper zwracający `slides[index].file` jest dobrą drogą do znalezienia zahashowanego klipu, ale zgubi warstwy źródłowego slajdu. Względne `ClipLayer.file` także wymagają nowej obsługi.

   **Poprawka planu:** nazwać kontrakt: „plik bazowy jednego slajdu”, określić numerację indeksów i zwracać rozwiązaną ścieżkę przez `PresentationConfig.from_file()`. Źródłowy deck musi być wcześniej wyrenderowany; jego ponowny render może zmienić wynik helpera. Dodać test z innym katalogiem roboczym.

5. **[KRYTYCZNE] B: `position()` nie daje płynnego zegara ruchu, a „sekundy od startu” są niejednoznaczne.**

   **Dowód:** FFmpeg Qt 6.12 aktualizuje pozycję timerem co **50 ms**; pauza zatrzymuje timer, pętla zgłasza `duration`, potem `0`, a koniec — końcową pozycję i `EndOfMedia` ([`qffmpegmediaplayer.cpp`, linie 38–40, 74–97, 290–305](https://raw.githubusercontent.com/qt/qtmultimedia/6.12/src/plugins/multimedia/ffmpeg/qffmpegmediaplayer.cpp)). Getter platformowy zwraca zapamiętaną pozycję, aktualizowaną przy zgłoszeniu zmiany ([`qplatformmediaplayer_p.h`, linie 37, 86–90](https://raw.githubusercontent.com/qt/qtmultimedia/6.12/src/multimedia/platform/qplatformmediaplayer_p.h)). Baza otrzymuje iloczyn szybkości slajdu i CLI (`src/manimcue/slides/present/player.py:469–470`).

   **Konsekwencja:** częstsze odpytywanie nie zapewni 60 aktualizacji geometrii na sekundę. Przy szybkości 2× pozycja oznacza czas materiału, nie czas rzeczywisty od startu. Po pętli ruch cofnie się do początku, chociaż niezapętlona warstwa-klip może już stać na końcu.

   **Poprawka planu:** wybrać jednoznacznie czas materiału albo aktywny czas prezentacji. Zalecam `QElapsedTimer` dla geometrii, z akumulacją przy pauzie i jawnym resetem przy replay; API jest dostępne lokalnie (`.venv/Lib/site-packages/PySide6/QtCore.pyi:2742`). Zdefiniować wpływ szybkości, pętli, końca bazy i buforowania. To zegar animacji prostokątów, bez sterowania seekiem dekoderów. Jeśli pozostaje czas materiału, potrzebna jest interpolacja między próbkami oraz jawna obsługa nieciągłości.

6. **[KRYTYCZNE] C: bariera `LoadedMedia` nie gwarantuje wspólnego pierwszego obrazu.**

   **Dowód:** backend zgłasza `LoadedMedia` po ustawieniu źródła; buforowanie jest odrębnym etapem uruchamiania odtwarzania ([`qffmpegmediaplayer.cpp`, linie 234–285](https://raw.githubusercontent.com/qt/qtmultimedia/6.12/src/plugins/multimedia/ffmpeg/qffmpegmediaplayer.cpp)). Silnik ustala początek własnego czasu po znalezieniu pierwszego pakietu ([`qffmpegplaybackengine.cpp`, linie 93–108](https://raw.githubusercontent.com/qt/qtmultimedia/6.12/src/plugins/multimedia/ffmpeg/qffmpegplaybackengine.cpp)). Lokalne API rozróżnia `LoadedMedia`, `BufferedMedia`, `InvalidMedia` oraz `errorOccurred` (`.venv/Lib/site-packages/PySide6/QtMultimedia.pyi:863`, `:891–899`).

   **Konsekwencja:** N wywołań `play()` w jednej iteracji oznacza wspólne wydanie poleceń, nie wspólną widoczną klatkę. Zastąpienie bariery oczekiwaniem na `BufferedMedia` przed pierwszym `play()` również nie jest bezpiecznym rozwiązaniem.

   **Poprawka planu:** zachować `LoadedMedia` jako barierę przygotowania źródeł. Podłączać sygnały przed `setSource()`, obsługiwać błąd i timeout, rozróżnić awarię bazy od opcjonalnej warstwy. Bariera powinna należeć do konkretnego wejścia na slajd i uruchamiać grupę najwyżej raz. Widoczny start mierzyć osobno; jeśli jest wymagany ostrzejszy próg, najpierw PoC przygotowania pierwszych klatek pod miniaturami.

7. **[KRYTYCZNE] C/D: wspólny transport musi obejmować więcej niż `play_pause()` i replay.**

   **Dowód:** `next()` wznawia wyłącznie bazę (`src/manimcue/slides/present/player.py:604–609`); zakończenie pętli przewija i pauzuje wyłącznie bazę (`:329–337`). `skip_all` oraz `auto_next` przechodzą dalej z sygnału bazy (`:307–325`). Start początkowy osobno przekazuje `start_paused` (`:345`), a zwykłe ładowanie natychmiast wywołuje `play()` (`:473–476`).

   **Konsekwencja:** po wdrożeniu tylko opisanych metod strzałka wznowi samą bazę, warstwy będą grały po zakończeniu pętli, a polecenie wydane podczas ładowania może zostać nadpisane późniejszym startem bariery.

   **Poprawka planu:** dodać wspólny stan żądany: przygotowanie, odtwarzanie, pauza, koniec, reverse. Wszystkie wymienione wejścia muszą korzystać z operacji grupowych. Dopisać przypadki: pauza przed gotowością, `next` po pauzie, replay podczas ładowania, `skip_all`, `auto_next`, zakończenie pętli z obiema wartościami `auto_next`.

8. **[WAŻNE] B/E: slajd-obraz wymaga własnego stanu transportu i reguły długości.**

   **Dowód:** dla obrazu baza zatrzymuje player (`src/manimcue/slides/present/player.py:477–480`), natomiast `play_pause()` obsługuje tylko stan Playing i Paused (`:638–646`). GIF jest wyjątkiem odtwarzanym przez player (`:455–458`).

   **Konsekwencja:** sam nowy zegar nie sprawi, że spacja zatrzyma ruch nad PNG. Nie ma też skończonej długości bazy, z którą można porównać niezapętlony klip nad obrazem.

   **Poprawka planu:** dla statycznej bazy przyjąć ręczny koniec slajdu i zwolnienie z porównania długości albo dodać jawną długość slajdu. Obraz-warstwa nie podlega walidacji czasu. GIF sklasyfikować świadomie jako animowane medium albo statyczną pierwszą klatkę — identycznie podczas renderu, walidacji i prezentacji.

9. **[KRYTYCZNE] D: „ostatnia klatka” przy reverse wymaga osobnego przygotowania.**

   **Dowód:** reverse przechodzi na poprzedni slajd (`src/manimcue/slides/present/player.py:625–627`), którego warstwy nie musiały wcześniej grać w tej sesji. Miniatura F5 ma przedstawiać pierwszą klatkę (`PLAN.md:359`), a replay obecnie uruchamia player ponownie od zera (`src/manimcue/slides/present/player.py:630–635`).

   **Konsekwencja:** zatrzymanie bieżących warstw nie zapewnia końcowego obrazu poprzedniego slajdu. Dla zapętlonej warstwy nie wiadomo dodatkowo, czy „ostatnia” oznacza koniec pliku, czy obraz w chwili końca bazy.

   **Poprawka planu:** najprościej generować końcowy obraz zastępczy klipu do reverse. Określić osobno końcowy prostokąt, obraz klipu zapętlonego oraz replay w trybie reverse. Testować wejście reverse bez wcześniejszego odtworzenia docelowego slajdu. Nie rozszerzać tego automatycznie na końcowy stan live — to wymaga osobnej decyzji.

10. **[WAŻNE] E: walidacja długości potrzebuje metadanych i obsługi nieznanej długości.**

    **Dowód:** `get_duration_ms()` otwiera kontener i czyta długość pierwszego strumienia wideo; nie dekoduje całości, ale zgłasza błąd przy braku `duration` lub `time_base` (`src/manimcue/slides/convert.py:122–130`). Każde wywołanie ponownie otwiera plik (`:124`). Model szybkości bazy nie wymusza wartości dodatniej ani skończonej (`src/manimcue/slides/config.py:210–211`).

    **Konsekwencja:** „jedna klatka” nie określa tolerancji dla 24 fps kontra 60 fps, VFR ani GIF. Dzielenie przez zerową szybkość jest niezdefiniowane, a ponawianie odczytów przy każdym wejściu na slajd jest zbędne.

    **Poprawka planu:** wspólny walidator wywoływać po uzyskaniu plików renderu oraz raz przed prezentacją, po rozwiązaniu ścieżek. `from_file()` pozostawić bez sondowania multimediów. Buforować metadane według ścieżki, rozmiaru i mtime; odrzucać szybkości niefinitywne i ≤0. Dla CFR określić np. tolerancję jako większy z czasów klatki obu materiałów po uwzględnieniu szybkości. Dla VFR/GIF i nieznanej długości ustalić jawny fallback albo czytelny błąd. Koszt odczytu trzeba zmierzyć; to nie jest koszt dekodowania całego filmu.

11. **[WAŻNE] A/F: trzeba domknąć granice modelu ruchu i istniejące wejścia eksportu.**

    **Dowód:** początkowy `rect` musi obecnie mieścić się w kadrze (`src/manimcue/slides/config.py:192–195`), podczas gdy plan oczekuje wjazdu warstwy (`PLAN.md:378–379`). Eksport buduje komunikat, pobierając `scene_name` każdej warstwy (`src/manimcue/slides/config.py:375–379`); render bezwarunkowo wywołuje generator miniatur live (`src/manimcue/slides/slide/base.py:680–681`).

    **Konsekwencja:** pozostawione walidatory zablokują wjazd spoza ekranu. Dodanie klipu może też zamienić zamierzony błąd eksportu w `AttributeError`.

    **Poprawka planu:** rozdzielić poprawność wymiarów od ograniczenia pozycji do kadru; walidować skończone, nieujemne i ściśle rosnące czasy. Miniatury i diagnostykę rozgałęzić według rodzaju. Liniowe `(t, rect)` wystarcza na automatyczne przesuwanie i skalowanie. Easing jest opcjonalnym rozszerzeniem; uruchamianie ruchu klawiszem wymaga osobnego modelu wyzwalania i nie wynika z tej listy.

12. **[WAŻNE] F: kryteria potwierdzają wydanie poleceń, ale jeszcze nie jakość odtwarzania; 6 h jest budżetem optymistycznym.**

    **Dowód:** kryterium startu mierzy jedną iterację zdarzeń, nie rozjazd widocznych klatek (`PLAN.md:372–373`). Podgląd bazy uruchamia dodatkowy player (`src/manimcue/slides/present/player.py:563–566`). Ochrona ostatniej klatki jest podłączona tylko do sinka bazy (`:284`, `:685–690`).

    **Konsekwencja:** zielone testy modeli i wywołań metod nie wykryją czarnej warstwy po końcu, opóźnionego startu dekodera ani przeciążenia. Nie ma uczciwej stałej „N dekoderów 1080p60 na Windows” bez wskazania kodeka, GPU, sterownika i pomiaru z live oraz preview.

    **Poprawka planu:** rozdzielić testy deterministyczne od integracyjnych. Offscreen sprawdzać model, interpolację, routing i stan bariery; rzeczywiste wideo zaliczać dopiero po odebraniu poprawnych klatek i sprawdzeniu pikseli z timeoutem. Dodać końce klipów, anulowanie przygotowania i opóźnione sygnały poprzedniego slajdu. Na komputerze prelegenta zmierzyć bazę + 1/2/3 klipy 1080p60, z Info i live, oraz ustalić dopuszczalny rozjazd startu. **6 h traktowałbym jako cel prototypu**, a limit 12 h jako punkt raportu; pełnego ukończenia nie da się obecnie wiarygodnie obiecać.

**Werdykt: F5 można implementować po poprawkach**, przede wszystkim po ustaleniu zegara, transportu grupowego, indeksowania mieszanych warstw i końcowego obrazu reverse. Najpierw krótki PoC kilku rzeczywistych playerów na Windows; jego wynik powinien doprecyzować kryterium wspólnego startu i budżet.

---

## Runda 12 — codex, 2026-10-22: przegląd kodu F5

Pytania: `codex-round12-prompt` (poprawność `ClipGroup`, kompozycja i live w ruchu, model
i render, jakość testów). Przegląd read-only z próbami Qt w pamięci.

**Co weszło:**
- Bariera bazy przyjmuje tylko nową klatkę dekodera: odrzuca klatkę przywróconą przez
  `frame_changed` (porównanie z `Player.frame`) i klatki w `NoMedia`/`LoadingMedia`; regresja
  sprawdzona w obie strony (p. 1).
- Replay w trakcie przygotowania pomijany; replay w pauzie wznawia grupę dla obu rodzajów bazy
  (p. 2). `next` nad bazą statyczną: wznowienie albo następny slajd, bez logiki pętli (p. 3).
- Awaria klipu: player odłączony i usunięty, w miejsce elementu wideo miniatura (p. 4).
- Obwódka live jedzie z warstwą (`SlideComposition.layer_moved`) (p. 5).
- Testy: liczniki klatek od konstrukcji (przygotowanie ≤ 2 klatki na klip), moment zwolnienia
  bariery, pauza w trakcie przygotowania sprawdzana na wszystkich playerach i braku klatek,
  reverse z rzeczywistymi klatkami cofanej bazy (p. 6-7). Pomiar rozjazdu w teście to
  dostarczenie do wątku GUI — widoczny start mierzy PoC.
- Połączenia sygnałów grupy rozłączane w `clear()` (p. 8); metadane klipów w pamięci
  podręcznej po ścieżce, rozmiarze i mtime, błędy sondowania z etykietą slajdu (p. 9).

**Odpowiedź codex (bez zmian):**

1. **[KRYTYCZNE] Bariera bazy może zaakceptować klatkę poprzedniego slajdu.**

   **Dowód:** grupa zostaje przygotowana przed `setSource()` bazy (`src/manimcue/slides/present/player.py:465–469`). `on_base_frame()` akceptuje każdą poprawną klatkę, bez identyfikatora wejścia ani źródła (`src/manimcue/clip_layers.py:103–107`). Tymczasem `frame_changed()` wstrzykuje zapamiętaną klatkę po otrzymaniu niepoprawnej (`src/manimcue/slides/present/player.py:715–720`), a `self.frame` nie jest zerowane przy ładowaniu (`src/manimcue/slides/present/player.py:447–493`).

   **Konsekwencja:** opróżnienie sinka podczas zmiany źródła może zwolnić barierę obrazem poprzedniej bazy. Nowa baza rozpocznie właściwe dekodowanie już po wspólnym starcie. Próba w pamięci potwierdziła, że wstrzyknięta poprawna klatka zwalnia tę barierę.

   **Poprawka:** oddzielić klatki dekodera od klatek przywracanych do wyświetlenia; przygotowanie bazy przypisać do konkretnego wejścia i nowego źródła. Dodać regresję: stara klatka → zmiana źródła → niepoprawna klatka → przywrócenie starej.

2. **[WAŻNE] Replay podczas przygotowania uruchamia samą bazę; replay w pauzie ma różną semantykę zależnie od rodzaju bazy.**

   **Dowód:** `Player.replay()` bezwarunkowo wykonuje `base.play()` (`src/manimcue/slides/present/player.py:655–661`). Grupa podczas przygotowania ignoruje replay (`src/manimcue/clip_layers.py:191–194`) i ignoruje zmiany stanu bazy (`src/manimcue/clip_layers.py:168–171`). Przy bazie statycznej replay grupy zachowuje pauzę, ponieważ uruchamia klipy tylko przy `self.running` (`src/manimcue/clip_layers.py:195–200`).

   **Konsekwencja:** jeżeli baza już przygotowała klatkę, a pozostałe klipy jeszcze czekają, replay puści bazę poza barierą. W pauzie baza wideo wznowi grupę, natomiast baza statyczna pozostawi ją zatrzymaną.

   **Poprawka:** rozstrzygać replay grupowy przed wywołaniem metod bazy; podczas przygotowania aktualizować wyłącznie stan żądany. Przetestować replay podczas przygotowania i w pauzie dla obu rodzajów bazy.

3. **[WAŻNE] `next` może utkwić na zapętlonym slajdzie z bazą statyczną.**

   **Dowód:** slajd z `loop=True` ustawia nieskończoną pętlę playera bazy (`src/manimcue/slides/present/player.py:502–505`), lecz obraz zatrzymuje ten player (`src/manimcue/slides/present/player.py:490–493`). Przy działającej grupie statycznej `next()` dochodzi do obsługi `next_terminates_loop` i ustawia żądanie zakończenia (`src/manimcue/slides/present/player.py:627–640`). Realizacja żądania wymaga cofnięcia pozycji bazy (`src/manimcue/slides/present/player.py:332–340`).

   **Konsekwencja:** przy `next_terminates_loop=True` kolejne naciśnięcia mogą stale zamawiać zakończenie pętli zatrzymanego playera, zamiast przejść dalej.

   **Poprawka:** obsłużyć `static_active` w całości: wznowić zatrzymaną grupę albo przejść do następnego slajdu, bez logiki pętli bazy.

4. **[WAŻNE] Awaria klipu nie pozostawia miniatury i zatrzymany player wypada ze sprzątania.**

   **Dowód:** normalna warstwa wideo powstaje jako sam `QGraphicsVideoItem`, bez miniatury (`src/manimcue/composition.py:98–102`). `drop()` usuwa player ze słownika i wyłącznie go zatrzymuje (`src/manimcue/clip_layers.py:128–133`). `deleteLater()` wykonywane jest tylko dla playerów pozostających w słowniku (`src/manimcue/clip_layers.py:224–230`); utworzone playery mają grupę jako rodzica (`src/manimcue/clip_layers.py:79`).

   **Konsekwencja:** błędny plik bez pierwszej klatki pozostawia pustą warstwę. Jego obiekt playera pozostaje dzieckiem długowiecznej grupy również po zmianie slajdu.

   **Poprawka:** po awarii odłączyć wyjście, zaplanować usunięcie playera i pokazać miniaturę lub jawny placeholder. Obecny test sprawdza jedynie zawartość słownika, więc obu problemów nie wykrywa (`tests/test_clip_layers.py:337–346`).

5. **[WAŻNE] Obwódka aktywnego lub błędnego live nie podąża za ruchem warstwy.**

   **Dowód:** ruch aktualizuje prostokąt i element warstwy (`src/manimcue/composition.py:138–147`), natomiast obwódka kopiuje prostokąt dopiero podczas `frame_layer()` (`src/manimcue/live_layers.py:186–193`). Wywołują ją aktywacja i błąd (`src/manimcue/live_layers.py:136–153`), nie zegar ruchu (`src/manimcue/clip_layers.py:218–222`).

   **Konsekwencja:** obraz odjedzie, a oznaczenie aktywacji lub błędu pozostanie w poprzednim miejscu. Trafianie kliknięciem korzysta z aktualnych elementów sceny, więc dodatkowo rozjedzie się z widoczną obwódką (`src/manimcue/composition.py:194–204`).

   **Poprawka:** aktualizować geometrię obwódki przy zmianie prostokąta oznaczonej warstwy albo powiązać ją z elementem warstwy.

6. **[WAŻNE] Test wspólnego startu nie wykrywa przedwczesnego odtwarzania, a pomiar 50 ms nie potwierdza widocznego startu.**

   **Dowód:** `started_early` zapisuje zdarzenie tylko przy jednoczesnym `preparing=True` i pustym `pending` (`tests/test_clip_layers.py:307–311`). `start()` zeruje `preparing` przed uruchomieniem playerów (`src/manimcue/clip_layers.py:147–151`). Monitor jest ponadto podłączany już po utworzeniu playera, który rozpoczął przygotowanie (`tests/test_clip_layers.py:302–309`; `src/manimcue/clip_layers.py:91–94`).

   Pomiar klatek podłączany jest dopiero po zakończeniu bariery i zapisuje czas wykonania callbacków (`tests/test_clip_layers.py:312–323`). Pętla obsługuje zdarzenia porcjami przez `processEvents()` (`tests/test_clip_layers.py:197–203`).

   **Konsekwencja:** wadliwa implementacja może przejść test: asercja `started_early` nie obserwuje właściwego naruszenia, a blisko dostarczone callbacki nie dowodzą bliskiego czasu wyświetlenia klatek.

   **Poprawka:** obserwować transport przed rozpoczęciem przygotowania; zarejestrować moment gotowości każdego źródła i wspólnego zwolnienia bariery. Po nim identyfikować pierwsze nowe klatki, a pomiar dostarczenia sygnałów opisywać osobno od pomiaru obrazu.

7. **[WAŻNE] Testy pauzy i reverse pozostawiają istotne części kryteriów bez sprawdzenia.**

   **Dowód:** test pauzy podczas przygotowania sprawdza wyłącznie bazę i zegar, bez stanów playerów warstw (`tests/test_clip_layers.py:349–360`). Test reverse odczytuje ręcznie dostarczoną zieloną pixmapę i prostokąt; nie czeka na klatki cofanej bazy (`tests/test_clip_layers.py:363–384`). Test ruchu wykonuje replay tylko podczas odtwarzania (`tests/test_clip_layers.py:282–285`).

   **Konsekwencja:** zielony wynik tych testów nie wykryje grającego klipu po zamówionej pauzie, błędnego transportu cofanej bazy ani problemów replay z punktu 2.

   **Poprawka:** przed próbą prelegenta dodać deterministyczne regresje punktów 1–5 oraz scenariusze `next` podczas przygotowania, `start_paused`, zakończenia pętli, `skip_all` i wyjścia po ostatnim slajdzie. Dla reverse sprawdzać rzeczywiste klatki bazy; dla pauzy — wszystkie playery i nieruchomy obraz po przepompowaniu zdarzeń.

8. **[DROBNE] Zachowany sink zbiera połączenia z kolejnych wejść.**

   **Dowód:** `set_layers()` zachowuje elementy dla tej samej listy i trybu (`src/manimcue/composition.py:81–83`). Każde `enter()` dokłada nową lambdę do sinka (`src/manimcue/clip_layers.py:80–83`), a `clear()` nie rozłącza tych połączeń (`src/manimcue/clip_layers.py:224–237`).

   **Konsekwencja:** ponowne ładowanie zachowanego układu zwiększa liczbę callbacków każdej klatki. Próba trzech wejść wykazała wzrost liczby odbiorców: 2 → 3 → 4. Sprawdzanie `entry` zapobiega aktualizacji przez stare callbacki, ale ich nie usuwa (`src/manimcue/clip_layers.py:109–111`). Nie jest to dowód wycieku sinków elementów zniszczonych podczas przebudowy.

   **Poprawka:** przechowywać i rozłączać własne połączenia albo podłączyć jeden odbiornik na czas życia elementu.

9. **[DROBNE] Walidacja przed prezentacją ponownie sonduje te same pliki i nie zawsze podaje kontekst błędu.**

   **Dowód:** każde `video_info()` otwiera kontener od nowa (`src/manimcue/media.py:15–22`); walidator wywołuje je dla każdej bazy i warstwy (`src/manimcue/media.py:51–54`), przechodząc po wszystkich slajdach (`src/manimcue/media.py:65–68`). Etykieta slajdu trafia do błędu różnicy długości, ale nie do błędu metadanych (`src/manimcue/media.py:20–21`, `:58–61`).

   **Konsekwencja:** wielokrotne użycie jednego renderu mnoży operacje otwarcia pliku; nieznana długość lub fps daje słabszy komunikat niż niezgodność długości.

   **Poprawka:** buforować metadane według rozwiązanej ścieżki, rozmiaru i `mtime_ns`; błędy sondowania opakować nazwą prezentacji, slajdu i roli pliku.

Nie wykazałem dodatkowego błędu skalowania pixmap: kod zastępuje transformację, zachowując źródłową pixmapę (`src/manimcue/composition.py:147`, `:156–163`). Podgląd klipu korzysta z miniatury, bez playera warstwy (`src/manimcue/slides/present/player.py:575`; `src/manimcue/composition.py:114–125`). Stary timeout po `clear()` jest odcinany numerem wejścia (`src/manimcue/clip_layers.py:135–137`, `:226`).

**Werdykt: F5 można zamknąć po poprawkach i próbie, ale obecnie nie.** Najpierw naprawić punkty 1–7 i potwierdzić je regresjami; obecny test startu nie stanowi wystarczającego dowodu synchronizacji (`tests/test_clip_layers.py:307–324`).

Przegląd był read-only, z małymi próbami Qt w pamięci. Nie uruchamiałem pełnego pytesta, renderu ani prezentacji na dwóch ekranach.

---

## Runda 13 — codex, 2026-10-22: kontrakt F6a (`SceneView`)

Pytania: `codex-round13-prompt` (updater i cache w CE, tekstury w manimgl, czas i dekodowanie,
API i kryteria). Przegląd read-only.

**Co weszło** (`src/manimcue/scene_view.py`, `frame_source.py`, D32 w `SPEC.md`):
- Zegar **absolutny** z `scene.time` gospodarza zamiast sumy `dt` — CE nie domyka przedziałów
  `play()`, GL zaczyna od 1/fps; z czasem sceny oba dają czas renderowanej klatki (p. 3-4).
- CE: `update()` odświeża klatkę także przy updaterach zawieszonych przez `.animate`, scena woła
  go po interpolacji; `interpolate_color` interpoluje tylko krycie, piksele są z dekodera;
  `set_opacity` bez zapisu w klatce dekodera; updater czasowy, żeby `wait()` nie zamrażał (p. 1-2).
- Stan odtwarzania i dekoder wspólne dla widoku i kopii (rejestr modułu), w `__dict__`
  deterministyczny identyfikator z kluczem źródła — hash CE zmienia się z nowym renderem
  źródła; test zmienia segment osiągany dopiero w trakcie `wait` i pada bez klucza (p. 5, 12).
- GL: klatka czeka na `init_shader_wrapper` (wrapper leniwy, `copy()` go zeruje); każdy widok
  ma własny plik pierwszej klatki, kopie dzielą teksturę z cache; test dwóch widoków jednego
  klipu w różnych chwilach w CE i GL (p. 6-7). `become`/`Transform` między widokami — poza
  kontraktem, opisane (p. 8). Zwalnianie tekstur i rejestru — `ponytail:` w kodzie (p. 9).
- Czas → klatka: CFR, ε na granicach, test 24 i 60 fps, koniec, pętla, cofnięcie (p. 10);
  cofnięcie dekoduje od początku — `ponytail:` z drogą przez `container.seek` (p. 11).
- Granica slajdu nie resetuje widoku — test ciągłości slajd 1 → 2 (p. 13).
- Testy w osobnych procesach CE i GL (p. 14). Budżet: PoC zmieścił się w bramce 3 h (p. 15).

**Ustalone przy implementacji (poza recenzją):**
- Pillow 13 usunął `mode` w `Image.fromarray`, a CE 0.21 używa go przy **każdym**
  `ImageMobject` w Cairo (`camera.py:1130`) — przypięcie `pillow<13` w `pyproject.toml`.
- W slajdach manimgl `wait()` to osobny plik częściowy, a fork kroi pliki po liczbie `play()` —
  slajdy się przesuwają (ostrzeżenie upstreamu). Gospodarz GL w testach używa `play()`.

**Odpowiedź codex (bez zmian):**

1. **[KRYTYCZNE] CE: zwykły updater nie gwarantuje odtwarzania podczas `.animate`.**  
   **Dowód:** CE domyślnie ustawia `suspend_mobject_updating=True` i zawiesza updater animowanego obiektu (`.venv/Lib/site-packages/manim/animation/animation.py:137`, `:205–214`). Dodatkowo interpolacja `ImageMobject` nadpisuje `pixel_array` interpolacją obrazów kopii (`.venv/Lib/site-packages/manim/mobject/types/image_mobject.py:297–301`). To koliduje bezpośrednio z przykładem `view.animate.scale(...)` (`PLAN.md:418`).  
   **Konsekwencja:** transformacja geometrii może działać, lecz obraz zatrzymać się albo pochodzić z kopii zamiast aktualnego dekodera. Samo wyłączenie zawieszania nie rozstrzyga własności pikseli podczas interpolacji.  
   **Poprawka planu:** przed implementacją API zrobić PoC **odtwarzanie + przesunięcie + skalowanie + FadeIn/FadeOut**. Oddzielić aktualizację klatki od interpolacji obrazu i określić, kto aktualizuje odtwarzanie podczas animacji.

2. **[WAŻNE] CE: normalne `wait()` działa, ale tylko z updaterem rozpoznawanym jako czasowy.**  
   **Dowód:** `should_update_mobjects()` sprawdza `has_time_based_updater()` (`.venv/Lib/site-packages/manim/scene/scene.py:435–445`); `get_moving_mobjects()` uwzględnia updatery rodziny (`:937–945`). Kamera pobiera bieżące piksele przez `get_pixel_array()` (`.venv/Lib/site-packages/manim/camera/camera.py:1046`), a metoda obrazu zwraca aktualny `pixel_array` (`.venv/Lib/site-packages/manim/mobject/types/image_mobject.py:216–218`). Jawnie ustawione `is_static_wait` omija automatyczną decyzję (`.venv/Lib/site-packages/manim/scene/scene.py:435`).  
   **Konsekwencja:** podmiana RGBA jest poprawną drogą dla nieanimowanego widoku w zwykłym `play()` i `wait()`; „static image” nie jest tu automatyczną przeszkodą. Updater bez argumentu `dt` albo wymuszone zamrożenie nie daje tej gwarancji.  
   **Poprawka planu:** zapisać wymaganie updatera czasowego oraz wyłączenie obsługi wymuszonego frozen wait. Kryterium 1 rozszerzyć o `wait()` i `play()` animujące **inny** obiekt (`PLAN.md:435–436`).

3. **[KRYTYCZNE] Sumowanie `dt` w CE nie jest równoważne ciągłemu czasowi gospodarza.**  
   **Dowód:** CE próbkuje `np.arange(0, run_time, 1/fps)`, bez końca przedziału (`.venv/Lib/site-packages/manim/scene/scene.py:1097–1101`). Updater dostaje różnicę kolejnych próbek (`:1700–1708`), a po animacji tylko `update_mobjects(0)` (`:1389–1393`). Przy skippingu próbką jest natomiast całe `run_time` (`:1097–1098`).  
   **Konsekwencja:** przy 30 fps zwykłe sekundowe `play()` daje updaterowi łącznie około 29/30 s. Kolejne wywołania kumulują brakujące końcówki; trafienie cache/skipping może przesunąć stan inaczej niż pełny render. To nowe ryzyko stanu odtwarzania, niezależne od znanego pomijania renderowania.  
   **Poprawka planu:** zdefiniować zegar absolutny z domknięciem granic wywołań, zamiast samego `t += dt`. Dodać porównanie `wait(2)` z dwoma `wait(1)` oraz renderu zimnego, ciepłego i częściowo pominiętego.

4. **[WAŻNE] GL ma inną fazę próbkowania czasu niż CE.**  
   **Dowód:** manimgl rozpoczyna od `1/fps`, bo dodaje ten krok do `np.arange(...)` (`.venv/Lib/site-packages/manimlib/scene/scene.py:471`). W `play()` aktualizuje obiekty przed emisją klatki (`:551–559`), analogicznie w `wait()` (`:607–612`). CE zaczyna od zera (`.venv/Lib/site-packages/manim/scene/scene.py:1101`).  
   **Konsekwencja:** w renderze GL updater otrzymuje czas wirtualny, nie czas dekodowania; jednak identyczne „pierwsza klatka = t=0” nie wynika z obu adapterów. Zmiana fps zmienia próbki czasu, nie nominalną szybkość odtwarzania; w CE dochodzi błąd z punktu 3.  
   **Poprawka planu:** określić mapowanie numeru klatki wyjściowej na czas źródła osobno dla obu silników. Testować pierwszą klatkę, granicę koloru i koniec przy dwóch fps gospodarza, zamiast jedynie „to samo w manimgl” (`PLAN.md:437`).

5. **[WAŻNE] Klucz źródła nie zastępuje hashowania obrazu ani kontraktu stanu cache.**  
   **Dowód:** lokalny CE serializuje `__dict__` (`.venv/Lib/site-packages/manim/utils/hashing.py:292–298`) i jawnie włącza piksele mobjectów do hasha wywołania (`:452–454`). Zwykły ndarray jest tutaj hashowany pełnym SHA-256, bez rozwijania milionów liczb do JSON (`:71–87`, `:285–291`). Plan proponuje tylko ścieżkę, rozmiar i mtime (`PLAN.md:426–427`).  
   **Konsekwencja:** atrybut źródła uczestniczy w hashu, ale nadal pozostaje liniowy koszt odczytu pikseli. Podmiana materiału z zachowaniem rozmiaru, mtime i bieżącej klatki nie zmieni tego klucza. Dekoder jako zwykły atrybut wprowadza też do serializacji szczegóły wykonawcze.  
   **Poprawka planu:** oddzielić serializowalny stan od zasobów dekodera; określić tożsamość zawartości źródła i jawne unieważnianie. Kryterium 6 powinno sprawdzać również identyczną pierwszą klatkę przy zmienionej dalszej części filmu oraz poprawność czasu po trafieniu cache (`PLAN.md:442`).

6. **[KRYTYCZNE] GL: `shader_wrapper.textures[0]` nie istnieje przez cały cykl życia mobjectu.**  
   **Dowód:** wrapper startuje jako `None`, powstaje dopiero przez `get_shader_wrapper(ctx)` (`.venv/Lib/site-packages/manimlib/mobject/mobject.py:108`, `:2023–2026`). `copy()` ponownie ustawia go na `None` (`:689–691`), a `FadeIn` tworzy kopię celu (`.venv/Lib/site-packages/manimlib/animation/fading.py:35–36`). Aktualizacja obiektów poprzedza emisję klatki (`.venv/Lib/site-packages/manimlib/scene/scene.py:558–559`).  
   **Konsekwencja:** bezwarunkowy zapis z updatera może trafić na `None`, także po kopiowaniu. PoC współdzielenia tekstury z `.animate` nie dowodzi poprawności inicjalizacji kopii (`PLAN.md:430–431`).  
   **Poprawka planu:** przechowywać oczekującą klatkę i wgrywać ją po uzyskaniu wrappera/kontekstu; przetestować aktualizację przed pierwszym renderem, kopię przed i po renderze oraz FadeIn.

7. **[WAŻNE] GL: współdzielenie tekstury musi zależeć od odtwarzacza, nie od pliku filmu.**  
   **Dowód:** `image_path_to_texture(path, ctx)` ma `lru_cache` i tworzy teksturę z pliku (`.venv/Lib/site-packages/manimlib/utils/shaders.py:23–30`). `copy()` zachowuje zwykłe atrybuty przez płytką kopię (`.venv/Lib/site-packages/manimlib/mobject/mobject.py:665`), a nowy wrapper ponownie korzysta z loadera tekstur (`.venv/Lib/site-packages/manimlib/shader_wrapper.py:93–97`).  
   **Konsekwencja:** dwa niezależne widoki korzystające z tej samej ścieżki pierwszego obrazu i kontekstu będą nadpisywały wspólną teksturę. Różne pozycje `seek()` ujawnią konflikt. Nie muszą mieć osobnych ścieżek **filmu**; przy obecnej konstrukcji potrzebują osobnej tożsamości tekstury. Kopie techniczne animacji mogą natomiast potrzebować współdzielenia.  
   **Poprawka planu:** rozróżnić niezależny `SceneView` i kopię techniczną animacji. Dodać test dwóch widoków tego samego źródła z różnymi czasami.

8. **[WAŻNE] GL: `Transform` i `become()` nie przenoszą automatycznie odtwarzacza ani zawartości tekstury.**  
   **Dowód:** interpolacja obejmuje `data` i `uniforms`, bez mieszania pikseli tekstur (`.venv/Lib/site-packages/manimlib/mobject/mobject.py:1808–1823`). `become()` przypisuje `texture_paths`, ale pokazany blok nie przenosi zegara/dekodera ani nie odtwarza wrappera (`:726–740`). `set_opacity()` zmienia dane wierzchołków, więc sam upload tekstury nie kasuje opacity (`.venv/Lib/site-packages/manimlib/mobject/types/image_mobject.py:52–58`).  
   **Konsekwencja:** transformacja geometrii tego samego odtwarzacza i transformacja między dwoma filmami to różne kontrakty. Obietnica „jak na każdym obrazie” jest za szeroka (`PLAN.md:408`).  
   **Poprawka planu:** zagwarantować geometrię i opacity; transformację między źródłami jawnie wyłączyć albo zdefiniować jako konkretną zmianę źródła/crossfade. Dodać osobną politykę `become()`.

9. **[WAŻNE] Brakuje właściciela i zwalniania tekstur.**  
   **Dowód:** loader zatrzymuje tekstury w cache (`.venv/Lib/site-packages/manimlib/utils/shaders.py:23–30`); `release_textures()` zwalnia je bezpośrednio (`.venv/Lib/site-packages/manimlib/shader_wrapper.py:212–217`). Plan wprowadza unikalne pliki, ale nie opisuje zamykania zasobów (`PLAN.md:424–431`).  
   **Konsekwencja:** cache może zatrzymywać tekstury usuniętych widoków; bezwarunkowe `release()` z jednej kopii może uszkodzić pozostałe. To dowód ryzyka retencji i współdzielonego zwalniania, **nie dowód nieograniczonego wycieku**.  
   **Poprawka planu:** ustalić jednego właściciela tekstury, dekodera i pliku tymczasowego, z idempotentnym zamknięciem. Dodać próbę wielokrotnego tworzenia/usuwania widoków i pomiar pamięci GPU.

10. **[WAŻNE] `floor(t·fps·rate)` wymaga dokładniejszego kontraktu niż test kolorów co pół sekundy.**  
    **Dowód:** taką formułę narzuca `PLAN.md:423–424`, podczas gdy istniejące metadane używają `average_rate` i osobnego `time_base` (`src/manimcue/media.py:30–33`). Gospodarze próbkują według własnych fps (`.venv/Lib/site-packages/manim/scene/scene.py:1100–1101`; `.venv/Lib/site-packages/manimlib/scene/scene.py:471`).  
    **Konsekwencja:** średnie fps nie określa chwil prezentacji VFR. Przy CFR błąd reprezentacji liczby na granicy może wybrać poprzednią klatkę; różne fps gospodarza i źródła z definicji powodują powtarzanie lub pomijanie próbek.  
    **Poprawka planu:** wybierać klatkę według PTS i jawnych przedziałów czasu albo ograniczyć F6a do CFR z racjonalnym fps i ustaloną tolerancją granic. Dodać numerowane klatki, granice ±ε, 24→60 i 60→24 fps, EOF i przejście pętli. Nie powtarzam ogólnej walidacji szybkości z wcześniejszych rund — tutaj chodzi o wybór konkretnej klatki.

11. **[WAŻNE] „Tylko bieżąca klatka” nie opisuje rzeczywistego kosztu dekodowania.**  
    **Dowód:** plan wymaga sekwencyjnego dekodowania i ponownego otwarcia po cofnięciu (`PLAN.md:424–425`); istniejąca ścieżka PyAV również iteruje po `container.decode(video=0)` (`src/manimcue/media.py:40`).  
    **Konsekwencja:** seek wstecz w okolice końca długiego klipu wymaga ponownego przejścia wcześniejszych klatek przy dosłownej realizacji planu. Wysoki `rate` nie usuwa kosztu dekodowania pomijanych obrazów. RGBA 1080p to wyliczeniowo około 7,9 MiB na tablicę, ale nie obejmuje buforów dekodera, kopii animacji i tekstury.  
    **Poprawka planu:** zagwarantować ograniczoną liczbę przechowywanych obrazów aplikacji, nie „jedną klatkę całej pamięci”. Dodać pomiar długiego 1080p, szybkiego odtwarzania, pętli i seeku wstecz; dopuścić seek do wcześniejszej klatki kluczowej z dalszym dekodowaniem.

12. **[WAŻNE] Metody sterowania wymagają jawnego kontraktu kopii; `.animate.pause()` nie wynika z API.**  
    **Dowód:** CE `copy()` używa `deepcopy` (`.venv/Lib/site-packages/manim/mobject/mobject.py:895–908`), GL tworzy płytką kopię i kopiuje listę updaterów (`.venv/Lib/site-packages/manimlib/mobject/mobject.py:665`, `:689`). Cel GL `.animate` powstaje przez `generate_target()` → `copy()` (`:702–705`).  
    **Konsekwencja:** bez adaptera CE może próbować kopiować zasób dekodera, a GL współdzielić go między kopiami. Wywołanie `pause/seek` na celu animacji nie gwarantuje zmiany stanu oryginału.  
    **Poprawka planu:** `pause/resume/seek` na początek traktować jako natychmiastowe komendy, poza `.animate`; zapewnić czytelny błąd dla takiego użycia. Zdefiniować niezależną kopię użytkową i techniczną kopię animacji bez dodatkowego przesuwania wspólnego dekodera.

13. **[WAŻNE] Granica slajdu nie resetuje widoku, a pętla prezentacji nie wykonuje go ponownie.**  
    **Dowód:** CE `next_slide()` tworzy sekcję i deleguje zapis granicy (`src/manimcue/slides/slide/manim.py:143–152`); baza aktualizuje konfigurację i indeks animacji (`src/manimcue/slides/slide/base.py:577–578`). Wynik powstaje przez sklejenie klipów, a reverse przez odwrócenie gotowego pliku (`:660–672`).  
    **Konsekwencja:** stan widoku powinien przechodzić ciągle między renderowanymi slajdami, chyba że autor wykona reset. Reverse gospodarza obejmuje już wkomponowany widok — ten kierunek jest poprawny. Powtarzanie gotowego klipu odtwarza jednak ten sam fragment widoku, nie dalszy czas dziecka.  
    **Poprawka planu:** dopisać tę semantykę i test dwóch kolejnych slajdów, pętli oraz reverse. Kryterium jednego slajdu CE tego nie sprawdza (`PLAN.md:441`). Dodać także test integracyjny GL, skoro obie ścieżki są zakresem F6a (`PLAN.md:406`).

14. **[DROBNE] `-s` oraz wybór silnika wymagają testów kontraktu, nie nowej architektury.**  
    **Dowód:** `save_last_frame` wyłącza zapis filmu (`.venv/Lib/site-packages/manim/_config/utils.py:807–808`), więc nie zastępuje testu klatek wyjściowych. Wybór `MANIM` jest ustalany przy imporcie na podstawie API (`src/manimcue/slides/slide/__init__.py:30–49`); plan chce go współdzielić (`PLAN.md:432`).  
    **Konsekwencja:** poprawny ostatni obraz nie dowodzi poprawnego odtwarzania; import `SceneView` musi też dawać tę samą klasę silnika co `Slide`.  
    **Poprawka planu:** osobne procesy testowe CE/GL, test końcowego stanu przy `-s` i test pominiętej sekcji z późniejszym widocznym odtwarzaniem. Nie traktować `-s` jako równoważnika renderu filmu.

15. **[WAŻNE] ~3 h to budżet eksperymentu, nie wiarygodna estymacja pełnych kryteriów.**  
    **Dowód:** zakres obejmuje dwa adaptery, dekoder, kontrolę czasu, cache i integrację (`PLAN.md:422–442`), pełne regresje i próbę prelegenta (`:443–445`), przy budżecie ~3 h (`:447`). Powyższe kolizje wynikają z konkretnych mechanizmów kopiowania, interpolacji i próbkowania wskazanych w punktach 1–13.  
    **Konsekwencja:** osiem obecnych kryteriów może przejść bez wykrycia zatrzymania podczas animacji, dryfu między `play()`, konfliktu dwóch widoków i problemów zasobów.  
    **Poprawka planu:** zachować 3 h jako bramkę PoC: animowany obraz CE, inicjalizacja/kopie GL, zegar między wywołaniami. Dopiero po wynikach oszacować implementację i rozszerzone testy.

**Werdykt:** tak, F6a można implementować po poprawkach — przede wszystkim po rozstrzygnięciu animacji CE, zegara oraz własności kopii i tekstur. Obecny kontrakt nie wystarcza do obietnicy „jak każdy obraz” (`PLAN.md:408`).

Przegląd był read-only; nie wykonywałem renderów ani pomiarów wydajności.

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

---

## Runda 14 — codex, 2026-10-22: PoC F6b (krokowanie sceny podrzędnej)

Pytania: `codex-round14-prompt` (nagrywanie CE bez renderu, odtwarzanie w gospodarzu, wartość
PoC „nagrania stanów” i ocena dróg). Przegląd read-only.

**Co weszło:**
- p. 1-2 zmieniły kierunek PoC: „nagranie stanów” odpowiadało tylko na „wektorowe F6a”, a
  odrzucenie greenleta było preferencją, nie dowodem. PoC wykonany **na greenlecie**: dziecko
  to zwykła `Scene` CE, adapter krokuje jedną próbkę na klatkę gospodarza, dziecko może czytać
  stan gospodarza (`wait_until`). Wynik w `PLAN.md` (faza 6b) i `experiments/f6b_stepping/`.
- p. 3-5: dziecko tworzone w `tempconfig(dry_run=True)`, `setup → construct → tear_down`;
  `play()` przez `compile_animation_data` → `begin_animations` → `update_to_time` →
  `finish` + `clean_up_from_scene`; `stop_condition` z `Wait` (CE `wait_until` bez zmian).
- p. 6, 8-10 rozwiązane inaczej, niż proponował codex: zamiast kopii mobjectów dziecka treść
  rysuje **kamera Cairo dziecka** w rozdzielczości ramki gospodarza (przezroczyste tło) do
  jednego `ImageMobject` o stałej tożsamości. Bez kopii znikają `always_redraw`/`ValueTracker`
  w migawkach i skalowanie obrysu; ramka (stała rodzina) jest animowalna. Odkryte przy tym:
  CE ustala rodziny ruchomych mobjectów raz na `play()` — kopie podmieniane w trakcie były
  niewidoczne, a stare rysowały się dalej.
- p. 11: stan RNG gospodarza zapisywany i przywracany wokół konstrukcji i kroków dziecka.
- p. 7, 12: ograniczenia (kamera ruchoma dziecka, dźwięk, sekcje) i pomiar — w wyniku F6b.

**Odpowiedź codex (bez zmian):**

1. **[KRYTYCZNE] PoC zmienia pytanie fazy: mierzy odtwarzanie, nie krokowanie żywego dziecka.**

   **Dowód:** cel wymaga równoległego postępu (`PLAN.md:458`), ale całe `construct()` ma wykonać się przed odtwarzaniem, a reakcje na gospodarza są wyłączone (`PLAN.md:466–473`). Kryteria sprawdzają potem wyłącznie postęp zapisanych stanów (`PLAN.md:479–484`).

   **Konsekwencja:** pozytywny wynik potwierdzi wektorowy odpowiednik F6a. Nie odpowie, czy można wznawiać wykonanie dziecka podczas pracy gospodarza. To nowa rozbieżność między obecną metodą eksperymentu a celem fazy.

   **Poprawka planu:** nazwać eksperyment „nagranie wektorowe sceny”. Oddzielić decyzję „czy warto rozwijać nagrania” od decyzji „czy zamykamy żywe krokowanie”. Pierwsza nie rozstrzyga drugiej.

2. **[WAŻNE] Odrzucenie greenlet jest decyzją projektową, nie dowodem braku jednowątkowej drogi.**

   **Dowód:** plan odrzuca greenlet jako zależność i „współbieżność tylnymi drzwiami” (`PLAN.md:464–465`). Tymczasem miejscem oddawania sterowania może być pętla próbek CE (`.venv/Lib/site-packages/manim/scene/scene.py:1381–1387`), analogicznie GL (`.venv/Lib/site-packages/manimlib/scene/scene.py:549–559`). Greenlet zachowuje stos wywołań i pozwala przełączać wykonanie wewnątrz jednego wątku — mechanizm opisuje [oficjalna dokumentacja](https://greenlet.readthedocs.io/en/stable/switching.html).

   **Konsekwencja:** technicznie istnieje droga: dziecko wykonuje zwykłe `self.play()`, adapter oddaje sterowanie po próbce, gospodarz postępuje, adapter wznawia dziecko. Dziecko może wtedy odczytać aktualny stan gospodarza. To współbieżność kooperatywna, bez równoczesnego wykonywania instrukcji. Długi fragment kodu bez oddania sterowania nadal blokuje gospodarza.

   **Poprawka planu:** pozostawić odrzucenie, jeśli taka jest preferencja projektu, ale zapisać uczciwie: „droga możliwa; nie akceptujemy zależności i utrzymywania zawieszonego stosu”. Generator wymagający `yield from` rzeczywiście zmienia API autora (`PLAN.md:462`); greenlet nie musi.

3. **[WAŻNE] „Bez renderu i plików” wymaga adaptera wykonania, nie zestawu flag.**

   **Dowód:** `Scene(renderer=None)` tworzy renderer i zawsze wywołuje `init_scene()` (`.venv/Lib/site-packages/manim/scene/scene.py:208–217`). Cairo tworzy kamerę, a następnie `SceneFileWriter` (`.venv/Lib/site-packages/manim/renderer/cairo_renderer.py:48–60`). Writer inicjalizuje katalogi już w konstruktorze; bez `dry_run` tworzy katalog obrazów także przed sprawdzeniem zapisu filmu (`.venv/Lib/site-packages/manim/scene/scene_file_writer.py:238`, `:260–282`). `dry_run` wyłącza wyjścia, ale zwykłe wykonanie renderera nadal przechodzi przez `update_frame()` (`.venv/Lib/site-packages/manim/_config/utils.py:1371–1377`; `.venv/Lib/site-packages/manim/renderer/cairo_renderer.py:167–168`).

   **Konsekwencja:** `write_to_movie=False` nie gwarantuje nawet braku katalogów; `dry_run` nie oznacza braku rasteryzacji. `skip_animations` zmienia wykonanie i czas (`.venv/Lib/site-packages/manim/renderer/cairo_renderer.py:75–78`), więc nie nadaje się do zbierania wszystkich próbek.

   **Poprawka planu:** najprostszy wariant PoC to podklasa/mixin nagrywający `play()`, z normalną inicjalizacją CE w lokalnym `tempconfig(dry_run=True)`, bez wywoływania renderera dla próbek. Wykonać `setup() → construct() → tear_down()`; zwykłe `render()` dodaje finalizację renderera (`.venv/Lib/site-packages/manim/scene/scene.py:257–282`). „Bez plików” ograniczyć do wyjścia sceny: np. `MathTex` niezależnie tworzy katalog i plik `.tex` (`.venv/Lib/site-packages/manim/utils/tex_file_writing.py:105–114`).

4. **[KRYTYCZNE] Recorder potrzebuje pełnego cyklu animacji, a nie samego `interpolate(alpha)`.**

   **Dowód:** CE kompiluje `_AnimationBuilder` przez `prepare_animation()` i nakłada argumenty `play()` (`.venv/Lib/site-packages/manim/scene/scene.py:989–1008`). Następnie dodaje zwykłe animowane obiekty, pomijając introducery (`:535–545`), a przed `begin()` wywołuje `_setup_scene()` (`:1343–1345`). Próbka wykonuje kolejno `animation.update_mobjects(dt)`, interpolację, aktualizację mobjectów, meshy i sceny (`:1700–1710`). Koniec obejmuje `finish()` i `clean_up_from_scene()` (`:1389–1393`); cleanup usuwa removers (`.venv/Lib/site-packages/manim/animation/animation.py:240–242`).

   **Konsekwencja:** uproszczona pętla może przejść test przesuwania kwadratu, ale zgubić `.animate`, `FadeIn`, usunięcie po `FadeOut`, aktualizacje pomocniczych obiektów animacji lub updatery sceny.

   **Poprawka planu:** wykorzystać `compile_animation_data()`, `begin_animations()` i `update_to_time()`, zastępując pętlę renderującą własną pętlą zapisu. Jawnie odtworzyć zakończenie. Zegar dziecka ustawiać osobno: `Scene.time` pochodzi z `renderer.time`, a normalnie zwiększa go emisja klatek (`.venv/Lib/site-packages/manim/scene/scene.py:231–233`; `.venv/Lib/site-packages/manim/renderer/cairo_renderer.py:191–195`).

5. **[WAŻNE] `Wait` i granice wywołań wymagają kontraktu nagrania.**

   **Dowód:** pojedynczy `Wait` ma osobną ścieżkę wykrywającą zamrożenie i `stop_condition` (`.venv/Lib/site-packages/manim/scene/scene.py:1329–1336`). Warunek zakończenia jest sprawdzany po wykonaniu próbki (`:1382–1387`). Sam `Wait` ma puste metody interpolacji i aktualizacji (`.venv/Lib/site-packages/manim/animation/animation.py:625–638`). Kryterium liczby stanów mówi tylko „fps × czas ±1” (`PLAN.md:479–480`).

   **Konsekwencja:** recorder traktujący wszystkie animacje jednakowo może wykonywać updatery podczas `frozen_frame=True`, ignorować wcześniejsze zakończenie albo zapisać stan sprzed usunięcia obiektu jako stan końcowy. Sama liczba próbek tego nie wykryje.

   **Poprawka planu:** określić osobno próbki obrazu i końcowy stan wykonania. Po cleanupie kod następujący po `play()` musi widzieć poprawną listę obiektów. Dodać przypadki: zamrożony wait, wait z updaterem sceny, `wait_until`, `FadeOut` oraz natychmiastowa zmiana między dwoma `play()`.

6. **[KRYTYCZNE] `copy()` daje kopię obiektów, ale nie bezpieczne, samodzielne środowisko odtwarzania.**

   **Dowód:** `Mobject.copy()` wykonuje `deepcopy`, a kopiowanie obejmuje atrybuty (`.venv/Lib/site-packages/manim/mobject/mobject.py:444–449`, `:895–908`). Updatery kopii zostaną ponownie wykonane przy `update()` (`:944–955`). Szczególnie `always_redraw` przechowuje funkcję zamykającą oryginalny `mob`: `lambda _: mob.become(func())` (`.venv/Lib/site-packages/manim/animation/updaters/mobject_update_utils.py:107–108`). `ValueTracker` przechowuje wartość w `points` (`.venv/Lib/site-packages/manim/mobject/value_tracker.py:78–90`).

   **Konsekwencja:** uruchomienie updatera migawki `always_redraw` może zmodyfikować oryginał. Ponadto afiniczne przekształcenie całej rodziny zmieni wartość skopiowanego `ValueTracker`, choć tracker nie jest treścią rysunku.

   **Poprawka planu:** kopiować korzenie jednym wspólnym `deepcopy`, zachowując wspólne referencje; z kopii usuwać updatery rekurencyjnie. Przechowywać niezmienne migawki i osobne kopie do wyświetlania. Transformować wyłącznie reprezentację wizualną; PoC ograniczyć do jawnie wspieranych `VMobject`, zamiast obiecywać dowolną rodzinę.

7. **[WAŻNE] Lista mobjectów nie obejmuje stanu kamery, sekcji ani dźwięku.**

   **Dowód:** `next_section()` deleguje bezpośrednio do writera (`.venv/Lib/site-packages/manim/scene/scene.py:352–362`), podobnie `add_sound()` (`:1802–1805`). Kamera jest własnością renderera (`:226–228`). W `MovingCamera` jej ramka określa szerokość, wysokość i środek kadru (`.venv/Lib/site-packages/manim/camera/moving_camera.py:62–114`). Kolor tła jest osobnym stanem kamery (`.venv/Lib/site-packages/manim/camera/camera.py:134–143`).

   **Konsekwencja:** nagranie mobjectów nie zachowa zoomu kamery, zmian tła, granic sekcji ani ścieżki audio. Animowanie `self.camera.frame` nie zastępuje zastosowania jej projekcji do treści.

   **Poprawka planu:** dla PoC jawnie wyłączyć ruchomą kamerę i audio; sekcje traktować jako metadane bez wpływu na nagrywanie albo odrzucać. Tło kamery pomijać świadomie jako element kontraktu przezroczystego nagrania. Nie przemilczać tych ograniczeń pod hasłem „Scene jak każda inna”.

8. **[KRYTYCZNE] Osobna treść dodawana przy pierwszym odświeżeniu nie ma cyklu życia ramki.**

   **Dowód:** `Scene.remove()` usuwa wskazane obiekty i ich rodzinę, nie niezależnych sąsiadów (`.venv/Lib/site-packages/manim/scene/scene.py:547–582`). Cleanup removera usuwa jego `mobject` (`.venv/Lib/site-packages/manim/animation/animation.py:240–242`). `Scene.add()` dopisuje obiekt na koniec listy (`.venv/Lib/site-packages/manim/scene/scene.py:521–532`).

   **Konsekwencja:** po `self.remove(frame)` albo `FadeOut(frame)` osobna treść pozostanie. `FadeIn(frame)` nie nada jej automatycznie krycia. Leniwe dodanie może też przenieść treść nad wcześniej dodany podpis.

   **Poprawka planu:** publicznym obiektem uczynić kontener obejmujący geometrię ramki i treść; ramka widoczna/niewidoczna powinna być jego częścią. Jeśli zostaje wariant dwóch niezależnych obiektów, trzeba jawnie ograniczyć API usuwania i animowania — nie da się wtedy obiecać zachowania zwykłego mobjectu.

9. **[WAŻNE] Odtwarzanie wektorów potrzebuje osobnej polityki krycia, zawieszenia i warstw.**

   **Dowód:** zwykłe `Mobject.update()` wraca przed aktualizacją dzieci, gdy kontener jest zawieszony (`.venv/Lib/site-packages/manim/mobject/mobject.py:944–955`). Istniejący `SceneView` odświeża przed `super().update()`, ale dotyczy to podmiany pikseli i osobnego `view_opacity` (`src/manimcue/scene_view.py:129–153`). Kamera sortuje globalnie spłaszczoną rodzinę według `z_index` (`.venv/Lib/site-packages/manim/utils/family.py:38–42`).

   **Konsekwencja:** bezpośrednie wstawienie świeżej migawki może przywrócić pełne krycie podczas fade. Wewnętrzny `z_index=100` dziecka może natomiast przebić nakładkę gospodarza mimo umieszczenia dziecka w grupie.

   **Poprawka planu:** odświeżenie wykonywać również przy zawieszeniu kontenera, ale wynik składać z aktualnym kryciem gospodarza i pierwotnym kryciem migawki. Ustalić mapowanie wewnętrznej kolejności dziecka na warstwę gospodarza. Sprawdzić fade przy zmieniającej się liczbie obiektów dziecka, nie tylko przy stałym kwadracie.

10. **[WAŻNE] Afiniczne mapowanie punktów nie wystarcza do odwzorowania kadru.**

    **Dowód:** rozmiar kadru pochodzi z konfiguracji kamery (`.venv/Lib/site-packages/manim/camera/camera.py:126–128`), więc nie należy kodować przybliżenia 14,2×8. `VMobject.scale()` domyślnie nie skaluje obrysu; robi to dopiero `scale_stroke=True` (`.venv/Lib/site-packages/manim/mobject/types/vectorized_mobject.py:484–487`, `:542–550`). Cairo ustawia szerokość linii osobno od punktów, a następnie używa macierzy kamera→piksele (`.venv/Lib/site-packages/manim/camera/camera.py:849–853`, `:610–628`).

    **Konsekwencja:** miniatura zachowa nadmiernie grube linie. Ściśle: `stroke_width` nie jest po prostu surową liczbą pikseli; wynik zależy także od kamery. Samo przekształcenie geometrii go jednak nie skaluje.

    **Poprawka planu:** pobierać rzeczywiste wymiary kadru. Dla zachowanych narożników \(p_{LL},p_{LR},p_{UL}\) użyć:
    \[
    p=p_{LL}+\frac{x+W/2}{W}(p_{LR}-p_{LL})
      +\frac{y+H/2}{H}(p_{UL}-p_{LL}).
    \]
    PoC ograniczyć do skali jednorodnej i skalować oba obrysy — zwykły i tła — względem niezmiennej migawki. Anizotropia oraz przycinanie do ramki wymagają odrębnej decyzji; transformacja współrzędnych nie jest przycinaniem (`PLAN.md:483–484`).

11. **[WAŻNE] Nowa pułapka inicjalizacji: dziecko zmienia losowość gospodarza.**

    **Dowód:** konstruktor każdej sceny wywołuje globalne `random.seed()` i `np.random.seed()` (`.venv/Lib/site-packages/manim/scene/scene.py:223–224`). Plan tworzy i wykonuje dziecko podczas budowania gospodarza (`PLAN.md:466`).

    **Konsekwencja:** dodanie nagrania może zmienić późniejsze losowania gospodarza, nawet gdy dziecko niczego nie rysuje.

    **Poprawka planu:** zachować i przywrócić oba globalne stany RNG wokół inicjalizacji oraz wykonania dziecka, również przy wyjątku. Dodać mały test porównujący dalszą sekwencję losowań gospodarza z nagraniem i bez niego.

12. **[WAŻNE] Kryteria i budżet nie wystarczają do decyzji o kontynuowaniu.**

    **Dowód:** plan mierzy „~20 mobjectów”, czas i pamięć, ale nie podaje progów (`PLAN.md:485–488`). `copy()` obejmuje wszystkie atrybuty (`.venv/Lib/site-packages/manim/mobject/mobject.py:444–449`), więc liczba korzeni nie opisuje rozmiaru geometrii. Istniejący identyfikator odtwarzania pochodzi z klucza pliku (`src/manimcue/scene_view.py:71–75`); nagranie wektorowe takiego źródła nie ma.

    **Konsekwencja:** 20 prostych figur i 20 rozbudowanych grup daje nieporównywalne wyniki. Przeniesienie stanów poza `__dict__` bez tożsamości całego nagrania może też pozostawić cache gospodarza niewrażliwy na zmianę późniejszych migawek.

    **Poprawka planu:** mierzyć liczbę elementów rodziny, punktów, przyrost pamięci procesu, czas nagrania i koszt odświeżania. Przed eksperymentem ustalić progi zaliczenia. Nadać nagraniu deterministyczny klucz obejmujący całą zawartość i parametry próbkowania. Dodać przypadek identycznego początku i zmienionej dalszej części nagrania. **~2 h traktować jako limit eksperymentu na wąskim podzbiorze**, nie estymację poprawnej obsługi powyższych mechanizmów.

**Werdykt:** tak, PoC można wykonać po poprawkach — jako eksperyment nagrania wektorowego o jawnym, ograniczonym zakresie. Jego sukces nie będzie podstawą do uznania żywego krokowania za rozwiązane ani niemożliwe (`PLAN.md:458`, `:466–486`). Przegląd był read-only; nie wykonywałem renderów ani pomiarów.

## Runda 15 — codex, 2026-10-22: kontrakt F7.0 (zgodność z CE 0.22)

Pytania: `codex-round15-prompt` (pełność listy złamań API, semantyka cache i flush, segmenty
w układzie 0.22, „tylko 0.22”, kryteria, budżet). Źródło 0.22 z rozpakowanego wheela. Przegląd
read-only.

**Co weszło:**
- p. 1: `max_files_cached = -1` przed `Scene.__init__`, przywracane w `finally`; kryterium 3
  z limitem 0.
- p. 2-3 rozwiązane inaczej: zamiast wrappera CLI albo czyszczenia segmentów atrybutem klasy —
  `--flush_cache` znika razem z flagą CE (segmenty czyści `manim cache clear`), atrybut
  `Slide.flush_cache` zachowuje semantykę upstreamu. Zmiana względem upstreamu zapisana jawnie.
- p. 4: czytelny błąd, gdy plan wyjścia nie jest wideo (kryterium 4).
- p. 6: test trafienia w cache CE dla `SceneView` (kryterium 5), komentarz o hashu.
- p. 5, 7: poza zakresem 7.0 jako ograniczenia forka sprzed 0.22 (CE 0.21 też wstawiał `None`
  dla pominiętych animacji, reverse wymusza `libx264` niezależnie od wersji CE). Zamiast korpusu
  — regresja end-to-end demo decku 0.21 vs 0.22 (kryterium 6).
- p. 8: decyzja „tylko 0.22” opisana jako świadome ograniczenie wsparcia.
- p. 9: budżet ~3 h, stop przy 6 h (codex proponował 4-6 h przy szerszym zakresie).

**Odpowiedź codex (bez zmian):**

Kontrakt 7.0 wymaga poprawek przed implementacją. Najpoważniejsze przeoczenie: ustawienie `max_files_cached = -1` dopiero w `render()` nie zapobiegnie usuwaniu segmentów w CE 0.22.

Poniżej `CE22/` oznacza wskazany rozpakowany wheel, a `CE21/` — `.venv/Lib/site-packages/manim/`. Przegląd był statyczny, tylko do odczytu; nie uruchamiałem renderów ani testów zapisujących pliki.

1. **[KRYTYCZNE] Limit cache trzeba ustawić przed inicjalizacją sceny.**

   **Dowód:** `CE22/scene/scene.py:252–257` kopiuje `config.max_files_cached` do ustawień writera podczas `Scene.__init__`. `CE22/scene/scene_file_writer.py:554–556` czyści cache według `self.settings.max_files_cached`, a nie bieżącego `config`. Tymczasem fork zmienia limit dopiero w `src/manimcue/slides/slide/manim.py:159–160`. CE21 odczytywało konfigurację podczas czyszczenia (`CE21/scene/scene_file_writer.py:1063`).

   **Konsekwencja:** prosta zamiana `float("inf")` na `-1` jest nieskuteczna. Przy ponad 100 segmentach — albo konfiguracji `max_files_cached=0` — CE usunie pliki przed `_save_slides`, powodując błąd składania slajdów.

   **Poprawka planu:** zapewnić limit `-1` podczas `Scene.__init__`, przywracając globalną konfigurację przez `finally`. Dodać test z początkowym limitem **0** i kilkoma animacjami: wszystkie slajdy muszą powstać, a konfiguracja musi zostać przywrócona również po wyjątku.

2. **[WAŻNE] Atrybut klasy i CLI nie mają tej samej dotychczasowej semantyki.**

   **Dowód:** `src/manimcue/slides/slide/manim.py:162–179` rozdziela dwie ścieżki. Flaga CE z CLI uruchamia końcowe `flush_cache_directory()`. Samo `self.flush_cache` trafia wyłącznie do `_save_slides`; tam usuwa katalog wynikowych slajdów (`base.py:615–616`). Ponadto ścieżka CLI zeruje `config["flush_cache"]` przed późniejszym przekazaniem go do `_save_slides`.

   **Konsekwencja:** propozycja „atrybut klasy czyści także segmenty CE” **zmienia zachowanie upstreamu**. Usunięcie CLI odbiera jednorazowe wymuszenie czyszczenia bez edycji sceny. Przepisanie testów CLI na atrybut klasy ukrywa tę utratę funkcjonalności.

   **Poprawka planu:** jawnie opisać zmianę semantyki. Jeżeli celem pozostaje zgodność CLI forka, zachować własną opcję wrappera `manim-cue render`, obsługiwaną przed przekazaniem argumentów do CE. Osobno testować czyszczenie wyników slajdów, segmentów CE i kombinację z `--disable_caching`.

3. **[WAŻNE] `clear_segment_cache` nie zostawia pustego katalogu.**

   **Dowód:** `CE22/utils/caching.py:17–31` wybiera tylko nieukryte pliki `.mov`, `.mp4`, `.webm`; `clear_segment_cache` usuwa właśnie ten zbiór. Manifest jest planowany osobno (`CE22/_config/output_plan.py:358`). Obecny test wymaga pustego katalogu przez `not list(local_media_folder.iterdir())` (`tests/slides/test_slide.py:151`, analogicznie po drugim czyszczeniu).

   **Konsekwencja:** wymiana funkcji czyszczącej nie wystarczy do zazielenienia testu. Pozostający `partial_movie_file_list.txt` jest poprawnym zachowaniem CE22, a nie pozostałym segmentem.

   **Poprawka planu:** określić, że znikają **rozpoznawane segmenty**, a manifest i inne pliki pozostają. Test powinien sprawdzać wszystkie trzy rozszerzenia i zachowanie pliku kontrolnego. Katalog pobierać z planu sceny/writera, zamiast rekonstruować jego położenie.

4. **[WAŻNE] Usunięcie `write_to_movie` jest poprawne tylko przy właściwym formacie wyjścia.**

   **Dowód:** `CE22/_config/render_session.py:72–79` rozwiązuje `format=auto` do MP4/MOV, ale przy `live_preview` lub GUI wybiera `NONE`. `CE22/renderer/opengl_renderer.py:966–968` zapisuje klatki według `output_spec`; `CE22/scene/scene_file_writer.py:361–362` nie dodaje segmentów dla wyjścia niewideo.

   **Konsekwencja:** zwykły render OpenGL faktycznie zapisuje segmenty bez `write_to_movie`. Nie jest jednak prawdą, że robi to zawsze. Podgląd interaktywny, `--format=none`, PNG lub sekwencja PNG mogą zostawić `_save_slides` bez segmentów.

   **Poprawka planu:** ustalić kontrakt obsługiwanych trybów: wymusić format wideo przed inicjalizacją sceny albo wcześnie odrzucać niezgodne tryby czytelnym komunikatem. Dodać osobne przypadki zwykłego OpenGL i OpenGL z podglądem.

5. **[WAŻNE] Ścieżki segmentów są obsługiwane poprawnie, ale kontrakt formatów pozostaje otwarty.**

   **Dowód:** `manim.py:94–98` pobiera pełne ścieżki z `partial_movie_files`; CE22 tworzy je przez `output_plan.segment_path()` (`scene/scene_file_writer.py:369`). `_save_slides` zachowuje rozszerzenie (`base.py:650–658`). GIF używa segmentów MP4 albo MOV, nie GIF (`CE22/_config/output.py:119–130`). Tymczasem reverse zawsze wybiera `libx264` (`src/manimcue/slides/utils.py:154`).

   **Konsekwencja:** nie potrzeba nowego wyszukiwania segmentów ani globowania katalogu. Jednak segment `.webm` prowadzi do próby zapisania H.264 do kontenera WebM podczas reverse; przezroczysty MOV również wymaga sprawdzenia zachowania alfa. Samo odnalezienie plików nie oznacza obsługi formatu.

   **Poprawka planu:** jawnie ograniczyć 7.0 do określonych formatów albo objąć testami MP4/MOV/WebM, reverse i przezroczystość. Dodać niestandardowy `partial_movie_dir` oraz GIF, aby wykryć błędne założenie o rozszerzeniu końcowego filmu. To także ograniczenie istniejącego forka, nie wyłącznie nowa regresja CE22.

6. **[WAŻNE] Zmiany hashowania wymagają testu trafienia w cache, nie tylko jego unieważnienia.**

   **Dowód:** CE22 zmienia sygnaturę `get_hash_from_play_call` o wymagane argumenty `backend`, `encoder_fingerprint`, `renderer_state` (`CE22/utils/hashing.py:416`). Serializuje też `pixel_array` dla animacji i mobjectów (`:464–468`), podczas gdy komentarz `scene_view.py:63–65` opisuje tylko dotychczasowe założenie o `__dict__`. Obecny `test_ce_cache_follows_new_source_render` sprawdza zmianę źródła, lecz nie dowodzi ponownego użycia niezmienionego segmentu.

   **Konsekwencja:** bezpośredniego błędu wywołania tu nie ma — fork nie wywołuje tej funkcji. Jest jednak nieopisana zmiana kontraktu cache. Test może przechodzić również wtedy, gdy cache nigdy nie trafia.

   **Poprawka planu:** dopisać sekwencję: identyczny render → potwierdzone trafienie CE; zmiana dalszej klatki źródła → unieważnienie; zmiana ustawień enkodera/backendu → odrębna tożsamość segmentu. Zachować test pikseli wyjścia i zaktualizować komentarz.

7. **[WAŻNE] Kryteria pomijają najbardziej ryzykowne mapowanie indeksów animacji.**

   **Dowód:** CE22 zachowuje `None` dla pominiętych animacji (`scene/scene_file_writer.py:364–367`). Fork usuwa te wpisy (`manim.py:94–98`), a następnie przesuwa indeksy o `from_animation_number` (`base.py:622–629`) i wycina listę według indeksów slajdu (`:646`). Testy `skip_animations` istnieją (`tests/slides/test_slide.py:545`), ale nie obejmują połączenia z `-n a,b`. Test pętli w `:356` sprawdza konstruowanie sceny; test reverse w `:209–213` porównuje ścieżki, nie kolejność klatek.

   **Konsekwencja:** zielony zestaw może nie wykryć slajdu z niewłaściwych animacji, błędnych granic lub niepoprawnego cofania.

   **Poprawka planu:** dodać integracyjny korpus Cairo/OpenGL: kilka `play()` na slajd, `wait()`, pomijany środkowy slajd, `start_skip_animations`/`stop_skip_animations`, `-n a,b` przecinające granice slajdów, pętla oraz `--save_sections`. Sprawdzać zawartość i długości klipów oraz odwróconą kolejność klatek; uwzględnić reverse dzielony na fragmenty.

8. **[DROBNE] Wsparcie wyłącznie 0.22 jest rozsądną decyzją produktową, ale nie koniecznością techniczną.**

   **Dowód:** wskazane użycia `Scene`, `next_section`, kamery Cairo, `ImageMobject`, `FadeIn`/`FadeOut`, `AnimationGroup` i metod mobjectów zachowują potrzebne sygnatury. `checkhealth.py:16` korzysta jedynie z wersji, a `render.py:58` deleguje CLI. Główne różnice dotyczą konfiguracji i cyklu życia writera. `pyproject.toml:32` obecnie deklaruje także starsze CE.

   **Konsekwencja:** obsługa obu wersji jest wykonalna przez niewielkie rozgałęzienie inicjalizacji i czyszczenia, lecz wymaga podwójnej walidacji. Jej odrzucenie nie wynika z niemożliwości zachowania API. Zawężenie zależności usuwa wcześniej deklarowane wsparcie.

   **Poprawka planu:** pozostawić `>=0.22,<0.23`, jeśli brak konsumenta 0.21 jest potwierdzony; nazwać to świadomym ograniczeniem wsparcia i odnotować w dokumentacji. Górna granica jest uzasadniona zależnością od wewnętrznych API CE. Nie widzę podstaw do wymagania obsługi obu wersji w 7.0.

9. **[WAŻNE] Dwie godziny wystarczą na łatkę startową, nie na pełne potwierdzenie kontraktu.**

   **Dowód:** `PLAN.md:542–560` zakłada kilka zmian konfiguracji, istniejący zestaw testów i demonstrację. Dochodzą przeoczona inicjalizacja ustawień writera, decyzja o CLI, macierz trybów wyjścia oraz testy indeksowania i cache opisane powyżej.

   **Konsekwencja:** można szybko uzyskać zielone podstawowe rendery, pozostawiając błąd zależny od liczby segmentów albo pomijanych animacji.

   **Poprawka planu:** przyjąć orientacyjnie **4–6 h** na implementację i ukierunkowaną walidację; szersze wsparcie formatów wycenić osobno. Zachować raport przy 4 h jako punkt kontroli, bez uznawania podstawowego renderu za zakończenie zgodności.

**Werdykt:** 7.0 można implementować po poprawkach. Warunki wejścia to przede wszystkim ustawienie limitu przed `Scene.__init__`, jawna decyzja o semantyce czyszczenia i CLI oraz dopisanie testów granic animacji. Lista trzech usuniętych/zmienionych kluczy nie opisuje jeszcze pełnego kontraktu migracji.
## Runda 16 — codex, 2026-10-22: D33 i kontrakt F5b (trwałe live, jedno kliknięcie)

Pytania: `codex-round16-prompt` (kierunek wejścia, `back` przy wyjściu wstecz, bariera D31 z READY,
klucz sesji, wymóg `rect`, mierzalność ≤ 50 ms, diagnoza uwag z próby, budżet). Przegląd read-only.

**Co weszło:**
- p. 1-2: jawna przyczyna zatwierdzonego przejścia zamiast `playing_reversed_slide`; `enter_cue`
  tylko przy wejściu do przodu, bez powtórzeń pętli i przejścia reverse → normalny plik.
- p. 3-5 i 13: cofanie cue wejścia i replay live **wydzielone** do osobnego etapu (checkpointy);
  5b to minimum pokazu. D33 zapisuje, że `back` nie cofa nazwanego `enter_cue`.
- p. 6: koordynacja startu także dla live z `enter_cue` nad bazą statyczną; timeout live osobno.
- p. 7: zamiast potwierdzania przygotowania wejścia — jawna polityka: `enter_cue` przerywa
  trwające cue (D10), spóźnienie o jedną publikację zgłoszone.
- p. 8: obraz, metadane i błąd przy sesji; mapowanie sesja → indeks na każdym wejściu.
- p. 9: generacja w kluczu, sesji zatrzymywanej i w ERROR nie przejmuje się, ID unikalne na slajdzie.
- p. 10: tożsamość ciągu bez pozycji i `thumbnail` (ścieżka, klasa, fps, rozmiar renderu).
- p. 11: pomiar na wspólnej osi `perf_counter`, ≥ 10 prób, ≤ 50 ms jako cel, nie gwarancja.
- p. 12: pomiar przed zmianą zostaje pierwszym etapem; demo ze stałymi kamerami.
- Budżet ~6 h na zawężony zakres (codex: ~8 h wiarygodne dla prototypu).

**Odpowiedź codex (bez zmian):**

1. **[KRYTYCZNE] Kierunku wejścia nie da się odczytać z `playing_reversed_slide`.**

   **Dowód:** `player.py:651` — `previous()` ustawia flagę na `False`, choć przechodzi wstecz; `player.py:656` — `reverse()` ustawia ją na `True` przed sprawdzeniem, czy poprzedni slajd istnieje. `player.py:527` — następne przejście po reverse odtwarza normalnie **ten sam slajd**. `player.py:661` — replay nie wywołuje `load_current_media()` ani kontrolera.

   **Konsekwencja:** samo przekazanie flagi do `show()` pomyli zwykłe cofnięcie z wejściem do przodu, ominie replay i może ponownie uruchomić cue po reverse. `V` na pierwszym slajdzie zostawia flagę zmienioną mimo braku przejścia.

   **Poprawka planu:** jawnie przekazywać przyczynę **zatwierdzonego przejścia**, osobno od trybu odtwarzania pliku. Wymagana tabela:
   
   - pierwszy slajd, również start od wskazanego indeksu — osobna inicjalizacja;
   - `next` — wejście dopiero przy rzeczywistej zmianie slajdu, nie przy wznowieniu;
   - `previous` i `V` — przejście wstecz, różny tryb bazy;
   - reverse → normalny plik tego samego slajdu — osobne zdarzenie;
   - `R` — osobne zdarzenie, również podczas reverse;
   - granica prezentacji — nowa sesja;
   - brak poprzedniego/następnego slajdu — brak zdarzenia;
   - zamknięcie — anulowanie, bez cue i cofania.

2. **[WAŻNE] „Koniec pętli” nie oznacza obecnie wejścia na slajd.**

   **Dowód:** `player.py:332` — zamówione zakończenie pętli albo przechodzi dalej przy `auto_next`, albo zatrzymuje bieżący slajd na końcu. Zwykłe powtórzenia pętli nie wywołują `show()`. `player.py:312` i `player.py:323` — `skip_all` oraz `auto_next` prowadzą bezpośrednio do `load_next_slide()`, które uwzględnia też flagę reverse.

   **Konsekwencja:** zapis D33 (`SPEC.md:598`) pozwala interpretować każde powtórzenie jako ponowne cue. Ponadto `auto_next` podczas reverse może najpierw przełączyć ten sam slajd na normalny plik.

   **Poprawka planu:** cue tylko na zatwierdzonym wejściu do przodu; powtórzenie pętli i zatrzymanie na jej końcu bez cue. Osobno określić zachowanie `skip_all` i `auto_next` podczas reverse oraz przetestować je przez rzeczywiste callbacki.

3. **[KRYTYCZNE] Nazwane `enter_cue` może być w ogóle niecofalne przez `back`.**

   **Dowód:** `live_scene.py:425` — kursor sekwencji przesuwa tylko komenda `next`; nazwany preset wykonuje `save_state()` bez przesunięcia kursora (`live_scene.py:432`). `step_back()` odmawia cofania przy `cursor == 0` (`live_scene.py:363`).

   **Konsekwencja:** świeża sesja wykonuje `enter_cue="spin"`, ale późniejsze `back` niczego nie cofa. Przy niezerowym kursorze może przywrócić ostatni snapshot, jednocześnie błędnie przesuwając kursor sekwencji.

   **Poprawka planu:** nie opierać cofania wejścia na istniejącym `back`. W planie trzeba jawnie uwzględnić zmianę protokołu i zarządzania stanem sceny.

4. **[KRYTYCZNE] Jedno `back` nie przywraca stanu sprzed wejścia przy ręcznych cue, replay i pominiętym wejściu.**

   **Dowód:** `live_scene.py:327` — cofany jest ostatni snapshot. Ręczne strzałki trafiają do live (`live_layers.py:214`). D33 nakazuje `back` na podstawie obecności pola (`SPEC.md:599`), choć plan dopuszcza niewysłanie cue po timeout (`PLAN.md:549`). Przerwanie domyka animację do końca (`SPEC.md:283`).

   **Konsekwencja:** po wejściu B i ręcznym cue cofnięte zostanie ręczne cue, a nie wejście B. Po niewysłanym wejściu można cofnąć wcześniejsze cue z A. Replay dokłada kolejne snapshoty. Samo wysłanie komendy nie dowodzi jej wykonania.

   **Poprawka planu:** odporna reguła to **checkpoint przed wejściem**, identyfikowany generacją sesji i identyfikatorem wejścia. Wyjście wstecz przywraca ten checkpoint wraz z kursorem i historią, niezależnie od ręcznych cue. Brak potwierdzonego checkpointu oznacza brak cofania. Przy trwającym cue: przerwać zgodnie z D10, następnie przywrócić checkpoint i potwierdzić wynik. Replay powinien wracać do tego samego checkpointu i uruchamiać wejście ponownie.

5. **[KRYTYCZNE] Kontrakt cofania myli slajd opuszczany z odtwarzanym.**

   **Dowód:** `player.py:651` — `←` ładuje poprzedni slajd normalnie; `player.py:656` — `V` ładuje reverse **poprzedniego** slajdu. Tymczasem `PLAN.md:565` przypisuje `←` reverse bazy. D33 opisuje cofnięcie cue slajdu opuszczanego (`SPEC.md:599`).

   **Konsekwencja:** po B→A baza może przedstawiać animację A, podczas gdy live właśnie cofa animację wejścia B. Nawet poprawny stan końcowy nie gwarantuje spójnej animacji trzech scen.

   **Poprawka planu:** rozpisać konkretną oś czasu A→B→A: który plik bazy gra, które cue live jest cofane, kiedy pokazuje się stan A. Poprawić kryterium dotyczące `←`; zdecydować, czy celem jest zgodność stanów końcowych, czy również animacji cofania.

6. **[KRYTYCZNE] Rozszerzenie samej bariery `ClipGroup` omija podstawowy przypadek baza + live.**

   **Dowód:** `clip_layers.py:64` — grupa jest potrzebna tylko dla klipu wideo lub keyframes; `clip_layers.py:79` — w pozostałych przypadkach `enter()` natychmiast zwraca `False`. `player.py:467` dodatkowo pomija grupę podczas reverse.

   **Konsekwencja:** slajd z bazą i nieruchomym live z `enter_cue` nie otrzyma bariery D33. Demo z dodatkowym klipem ukryje błąd.

   **Poprawka planu:** rozszerzyć warunek uruchomienia koordynacji o `enter_cue`, również nad bazą statyczną. Zdefiniować wysłanie cue przy `start_paused`, pauzie podczas przygotowania i późniejszym wznowieniu. Timeout live nie może korzystać bezpośrednio ze ścieżki usuwania playera klipu (`clip_layers.py:164`).

7. **[KRYTYCZNE] READY nie oznacza, że trwała sesja jest bezczynna i gotowa do wspólnego startu.**

   **Dowód:** `live_session.py:70` ustawia `ready` po inicjalizacji; `CUE_START` i `CUE_DONE` nie zmieniają tego stanu. `live_scene.py:478` kolejkuje komendy, a `live_scene.py:570` pozwala nowej komendzie przerwać bieżące cue.

   **Konsekwencja:** wejście B podczas animacji A spełnia warunek READY, lecz cue B rozpocznie się po przerwaniu, domknięciu i publikacji A. „Jeden tick” wysłania nie oznacza wspólnego początku animacji.

   **Poprawka planu:** oddzielić „proces zainicjalizowany” od „wejście przygotowane”. Przed zwolnieniem bariery wymagać potwierdzenia przygotowania konkretnego wejścia i odebranej klatki granicznej. Ustalić politykę dla trwającego cue oraz szybkich przejść; nie używać samego `state == "ready"`.

8. **[KRYTYCZNE] Zachowanie procesu nie zachowuje obrazu ani poprawnego indeksu warstwy.**

   **Dowód:** `live_layers.py:43` — sesje i metadane są indeksowane po pozycji w kompozycji. `composition.py:88` zachowuje pixmapy tylko przy tej samej liście warstw. Nowy slajd dostaje miniaturę (`composition.py:109`). Odczyt nie zwraca ponownie tego samego `frame_id` (`frame_buffer.py:101`), a bezczynna scena nie publikuje stale (`composition.py:80`).

   **Konsekwencja:** przy A→B live może przeskoczyć do miniatury i pozostać na niej mimo zachowanego PID. Zmiana pozycji live w liście, np. `[live, clip]`→`[clip, live]`, grozi wysłaniem obrazu lub obwódki pod zły indeks.

   **Poprawka planu:** przechowywać ostatni obraz i metadane przy tożsamości sesji; na każdym wejściu odtworzyć mapowanie sesja→indeks kompozycji i natychmiast wstawić obraz. Przenieść także czas startu i błąd; fokus zwalniać. Dodać test zmiany indeksu i przejścia bez nowej publikacji.

9. **[WAŻNE] Klucz `(prezentacja, session_id)` nie wystarcza do zarządzania życiem sesji.**

   **Dowód:** `live_session.py:172` — `request_stop()` ustawia termin zabicia procesu, ale nie zmienia od razu `state`; sesja może nadal wyglądać na READY. ERROR również zamawia zatrzymanie (`live_session.py:73`). Obecny kontroler oddziela sesje zatrzymywane (`live_layers.py:95`), a test szybkiego powrotu wymaga nowego obiektu (`tests/test_live_layers.py:204`).

   **Konsekwencja:** po przerwie w ciągu slajdów szybki powrót może odzyskać sesję już skazaną na zakończenie. Wyczyszczenie `failed` może ukryć błąd przenoszonej sesji. Dwa wystąpienia tego samego ID na jednym slajdzie mają nieokreślone znaczenie.

   **Poprawka planu:** klucz logiczny uzupełnić generacją procesu; sesji zatrzymywanej nigdy nie przywracać. Zdefiniować ciągłość jako sąsiednie slajdy tej samej prezentacji plus jawnie dozwolone operacje na tym samym slajdzie. ERROR pozostaje błędem do opuszczenia ciągu lub jawnego restartu. Walidować unikalność ID na slajdzie i zgodność wewnątrz ciągłego odcinka. Późniejsze użycie ID po przerwie tworzy nową generację.

10. **[WAŻNE] `rect` jest zbyt restrykcyjny, a semantyka `thumbnail` pominięta.**

    **Dowód:** D33 wymaga identycznego `rect` (`SPEC.md:595`), lecz rozmiar renderu zależy tylko od szerokości i wysokości, nie pozycji (`config.py:253`). Miniatura live jest pierwszą klatką świeżej sceny (`config.py:237`, `slides/slide/base.py:726`).

    **Konsekwencja:** przesunięcie nieruchomego panelu między slajdami niepotrzebnie staje się błędem walidacji. Miniatura B może przedstawiać stan początkowy procesu, choć trwały live jest już po cue A; podgląd Info nadal pokazuje miniatury.

    **Poprawka planu:** dla zgodności procesu porównywać kanoniczną ścieżkę sceny, klasę, fps i wynikowy rozmiar renderu. Stałe położenie pozostawić wymogiem demonstracji, jeśli tego chce prelegent. `thumbnail` wyłączyć z tożsamości sesji; określić ją jako fallback/podgląd, bez obietnicy stanu B. Ciągłość obrazu głównego zapewniać cache’em z punktu 8.

11. **[WAŻNE] Kryterium ≤50 ms miesza dostarczenie klatki z jej wyświetleniem.**

    **Dowód:** istniejący test wprost mierzy dostarczenie do GUI, nie wyświetlenie (`tests/test_clip_layers.py:332`). Live przechodzi przez kolejkę wysyłki (`live_session.py:108`), oczekiwanie `select` (`live_scene.py:415`), render/readback/publikację (`live_scene.py:533`) i timer GUI 4 ms (`live_layers.py:21`). Kod dokumentuje zaokrąglanie timeoutu `select` na Windows (`live_scene.py:560`).

    **Konsekwencja:** test offscreen może mierzyć użyteczną metrykę programową, ale nie potwierdzi tego, co zobaczy prelegent. Pierwsza poprawna klatka może być niezmieniona; pierwsza zmieniona zależy także od treści animacji.

    **Poprawka planu:** zastosować kontrolowane animacje z natychmiastową zmianą znacznika w każdym z trzech obszarów. Rejestrować wspólną osią monotoniczną: żądanie, zwolnienie bariery, odbiór cue, publikację live i pierwszą zmienioną klatkę odebraną w GUI. Oddzielić opóźnienie od rozrzutu, READY od pierwszej klatki i test offscreen od pomiaru okna. ≤50 ms traktować jako cel na określonym sprzęcie, raportowany z wielu prób, a nie gwarancję wynikającą z jednego ticku.

12. **[WAŻNE] Diagnoza ospałości jest częściowa, a „nieruchome sceny” nie jest jednoznaczne.**

    **Dowód:** ranking opiera się na offscreen i sam odnotowuje brak pomiaru okna (`PLAN.md:525`). D33 deklaruje restart największym kosztem (`SPEC.md:592`), choć replay i pętla już zachowują proces (`live_layers.py:64`). Na slajdzie 5 faktycznie przesuwa się prostokąt Orbit (`examples/demo.py:119`), a notatka błędnie obiecuje pauzę wszystkiego (`examples/demo.py:129`).

    **Konsekwencja:** trwałość usuwa koszt restartu podczas zmiany slajdu, ale nie wyjaśnia opóźnienia ręcznych cue ani renderowania. Trzy stałe prostokąty nie dowodzą jeszcze, że kamera i układ wewnątrz scen pozostają nieruchome.

    **Poprawka planu:** zachować pomiar przed zmianą jako pierwszy etap. Osobno mierzyć start procesu, przejście z zachowaniem sesji i reakcję na cue. W demo ustalić stałe prostokąty i kamery oraz widoczne animacje obiektów. Punkty 1–3 uwag mogą pozostać w 5c–5e; 5b musi jednak naprawić ciągłość obrazu i jawnie opisać statyczny podgląd oraz brak pauzy live.

13. **[WAŻNE] ~8 h jest wiarygodne dla prototypu, nie pełnego kontraktu.**

    **Dowód:** `PLAN.md:542` obejmuje model, walidację, trwałość, nawigację, barierę, pomiary i demo. Obecne testy sprawdzają głównie restart oraz izolację starych sesji (`tests/test_live_layers.py:187`), a nie checkpointy, replay i ciągłość między slajdami.

    **Konsekwencja:** pełne wykonanie wymaga również protokołu przywracania, potwierdzeń operacji i testów wyścigów. Limit 16 h łatwo osiągnąć przed próbą prelegenta.

    **Poprawka planu:** rozdzielić zakres. Minimalny etap realizujący pokaz: trwała sesja w sąsiednich slajdach, zachowany obraz, jedno cue wejścia, wspólny start i pomiar w oknie. Odroczyć animowane cofanie live i deterministyczny replay — **jawnie wyłączając je z kryteriów tego etapu**. Zachować poprawną izolację procesów, błędy i anulowanie szybkich przejść. Jeśli cofanie i replay pozostają wymagane, zwiększyć budżet po zaprojektowaniu protokołu.

**Werdykt:** 5b można implementować po poprawkach, ale obecny D33 nie jest gotowym kontraktem. Najpierw trzeba rozstrzygnąć zdarzenia nawigacji, checkpointy cofania, gotowość do startu i przenoszenie obrazu. Przegląd był statyczny i read-only; nie uruchamiałem testów ani pomiarów.

## Runda 17 — codex, 2026-10-22: kontrakt F5c (druga próba)

**Pytania:** Czy proporcje, ciągłość, demo i stan są sprawdzalne i zgodne z D17/D20/D27/D31/D33? Czy zakres i budżet są zamknięte?

**Co weszło:**

1. Przyjęto jawny frame_config przed konstrukcją i wspólną ścieżkę miniatur; odrzucono wystarczalność samego frame_shape, ponieważ test GL wykazał stałe FRAME_WIDTH/HEIGHT w Camera.refresh_uniforms.
2. Przyjęto alternatywę letterbox z recenzji: render 16:9 i czarne pasy zachowują całą treść bez łatania Manima.
3. Przyjęto regresje wąskiego kadru, resetu i F2 bez zmiany czułości D28.
4. Przyjęto dopasowanie wszystkich reprezentacji klipu i ruchu.
5. Przyjęto obwódkę tylko live i hit-test pełnego kontenera klipu.
6. Przyjęto placeholder do nowej poprawnej klatki oraz izolację wejść.
7. Przyjęto snapshot istniejących pól, małe powiadomienia, bez nowego zegara.
8. Przyjęto tabelę stanu; odrzucono historię każdej iteracji pętli i potwierdzenia wykonania cue, bo rozszerzają protokół poza cel czytelności bieżącego stanu.
9. Przyjęto nakładkę viewportu, wspólny tekst Info oraz S z kontrolą konfliktów.
10. Przyjęto deterministyczny początek i koniec cue, nominalne 2 s i D33; odrzucono ±1 klatkę jako sprzeczne z D17.
11. Przyjęto macierz diagnostyczną i limit 45 min; brak reprodukcji nie dowodzi winy backendu, prawdziwy ekran pozostaje próbą człowieka.
12. Przyjęto geometrię i raster po kompozycji, deterministyczną ciągłość i budżet 8 h + 45 min; odrzucono rozbudowany dziennik komunikatów jako rozszerzenie celu.

**Odpowiedź codex (bez zmian):**

1. **[KRYTYCZNE] Poprawka live wymaga `frame_config.frame_shape`; sama rozdzielczość nie wystarcza.**

   **Dowód:** `src/manimcue/live_worker.py:28–36` przekazuje tylko rozdzielczość. W manimgl: `.venv/Lib/site-packages/manimlib/camera/camera.py:30–32,64–70` konstruktor przyjmuje `frame_config`, a `CameraFrame` przyjmuje `frame_shape` (`camera/camera_frame.py:26,46–48`). `Scene` scala konfigurację przed utworzeniem kamery (`scene/scene.py:88–110`). Komentarz przy `resolution` sugeruje automatyczne dopasowanie, ale konstruktor go nie wykonuje.

   **Konsekwencja:** diagnoza 5c jest trafna, lecz kontrakt nie wskazuje właściwego API ani momentu zmiany. Dopasowanie po `build_objects` byłoby za późne dla scen rozmieszczających treść według kamery.

   **Poprawka planu:** jawnie zapisać:
   `camera_config={"resolution": (w,h), "frame_config": {"frame_shape": (H*w/h,H)}, ...}` — przed budową sceny. Alternatywą jest `camera.resize_frame_shape(fixed_dimension=True)` (`camera.py:207–222`), również przed budową obiektów. `frame_shape` nie jest bezpośrednim argumentem `Camera`. `capture_first_frame` uruchamia ten sam worker (`live_session.py:200–206`), więc nie potrzebuje osobnej implementacji geometrii.

2. **[KRYTYCZNE] Stała wysokość usuwa deformację, ale może wyciąć istniejącą treść 16:9.**

   **Dowód:** `PLAN.md:617–618` wybiera stałą wysokość. Panel 7–8 ma `rect=(0.36,0.15,0.28,0.6)` (`examples/demo.py:153–158`). Przy bazie 16:9 jego proporcja pikselowa wynosi około **0,83**, więc dla wysokości kadru 8 szerokość spada z około 14,22 do **6,64**. Tymczasem `Panel` dziedziczy obiekty umieszczone przy `x=±3`, o promieniu/półboku 1 (`live_scene.py:609–611`), oraz sweep do prawej strony (`live_scene.py:629–630`).

   **Konsekwencja:** okrągły obiekt może być poprawny geometrycznie, ale częściowo niewidoczny. Uniwersalna zmiana workerów obejmie też inne sceny, nie tylko `ThreePanel`.

   **Poprawka planu:** wybrać i uzasadnić politykę kadrowania. Dla treści zaprojektowanej pod 16:9 bezpieczniejsze jest zachowanie całego kadru: rozszerzanie jednej osi albo letterbox. Stała wysokość jest rozsądna dla świadomie projektowanych wąskich paneli, nie jako automatyczna gwarancja zgodności. Dopisać kontrolę widoczności całej treści istniejących paneli.

3. **[WAŻNE] Brakuje regresji D22, D28 i pomiarów F2 po zmianie kadru.**

   **Dowód:** korpus ma stałe `FRAME_WIDTH/HEIGHT` oraz narożniki obliczane z 16:9 (`tests/scenes/live_gl.py:27–28,65–78`). Test `corner()` także zakłada te proporcje (`tests/test_live_layers.py:100–104`). Nawigacja używa stałych wymiarów (`live_scene.py:504–512`), zgodnie z mechanizmem upstreamu `window.py:129–137`. Reset przywraca kopię kadru granicznego (`live_scene.py:516–517,543–544`), natomiast upstreamowe `CameraFrame.to_default_state()` przywraca globalne `FRAME_SHAPE` (`camera_frame.py:62–65`). Progi wydajności określa D26 (`SPEC.md:525–529`).

   **Konsekwencja:** testy 16:9 nie sprawdzą nowego przypadku. Nie należy też mechanicznie zamieniać stałych D28 na aktualne wymiary kamery: pan przechodzi jeszcze przez transformację kadru, a orbit ma własną czułość. Scena wywołująca upstreamowy reset może ponownie wprowadzić deformację.

   **Poprawka planu:** zachować dotychczasowy korpus 16:9 i dodać wariant wąski: orbit, pan w obu osiach, zoom, reset po READY, po cue i po `back`. Zweryfikować miniaturę po ponownym renderze. Ponowić pomiary F2 przy dotychczasowych rozdzielczościach i progach; nie obniżać progów ani nie przesuwać próbników pikseli tylko po to, aby testy przeszły.

4. **[KRYTYCZNE] `KeepAspectRatio` tylko w elemencie wideo da niespójne obrazy zależnie od trybu.**

   **Dowód:** wideo ma osobną gałąź (`composition.py:101–105`), ale obrazy, miniatury, reverse i zastępnik po awarii korzystają z pixmap (`composition.py:107–110,116–128,141–151`). `set_layer_pixmap` rozciąga niezależnie obie osie (`composition.py:172–179`). Ruch ponownie wywołuje tę funkcję (`composition.py:153–163`).

   **Konsekwencja:** koło będzie okrągłe podczas odtwarzania, a eliptyczne w miniaturze, reverse lub po błędzie. Zmiana proporcji prostokąta przez D30 może ponownie rozciągać pixmapę. Podgląd następnego slajdu w Info używa właśnie miniatur (`player.py:581–582`).

   **Poprawka planu:** objąć jedną regułą dopasowania wszystkie reprezentacje **klipu**: wideo, obraz, miniaturę, `end_thumbnail`, zastępnik i ruch. Dla źródła `sw×sh` użyć skali `min(rw/sw,rh/sh)` oraz wyśrodkowania. Zachować pełny prostokąt D30 jako kontener; nie zmieniać interpolacji ani zegara. Nie przenosić tej reguły bezwarunkowo na klatki live.

5. **[WAŻNE] Kontrakt kliknięcia i obwódki nie odpowiada obecnej implementacji.**

   **Dowód:** `PLAN.md:620` mówi o kliku i obwódce prostokąta klipu. Obwódka należy jednak do `LiveLayerController` i dotyczy sesji live (`live_layers.py:221–228,266–274`). Trafienie warstwy opiera się na elementach pod kursorem, nie na `layer_rects` (`composition.py:210–220`); klik w klip zwalnia live, bo klip nie ma sesji (`live_layers.py:224–226`).

   **Konsekwencja:** przesunięta, dopasowana pixmapa nie będzie zajmowała całego kontenera. Klik w przezroczysty margines może trafić do niższego live i aktywować go. Sama zmiana skalowania nie zachowa deklarowanego zachowania.

   **Poprawka planu:** wyjaśnić, że obwódka aktywności dotyczy live. Osobno zdecydować, czy margines klipu blokuje klik do niższych warstw. Jeśli tak, hit-test musi uwzględniać prostokąt kontenera i kolejność warstw. Dodać test kliknięcia środka, marginesu i obszaru poza kontenerem.

6. **[KRYTYCZNE] Mignięcie wynika z pustego elementu przed pierwszą klatką, nie z samego oczekiwania bariery.**

   **Dowód:** `composition.py:101–105` tworzy od razu pusty `QGraphicsVideoItem`, zamiast miniatury. `ClipGroup.enter()` podpina nowe źródło i uruchamia dekoder (`clip_layers.py:91–108`). Ochrona pustej klatki działa dopiero, gdy istnieje `self.frames[index]` (`clip_layers.py:141–158`), a `clear()` usuwa ten cache (`clip_layers.py:295–296`). Osobno istnieje już przypięcie pierwszej klatki na czas asynchronicznej pauzy (`clip_layers.py:145–155`), sprawdzane w `test_persistent_live.py:297–318`.

   **Konsekwencja:** „miniatura/ostatnia klatka” to właściwy kierunek, ale ogólne zdanie nie zamyka błędu. Użycie starej klatki jako nowej gotowości może przedwcześnie zwolnić barierę. Nakładka miniatury pozostawiona nad wideo może później ukrywać odtwarzanie.

   **Poprawka planu:** placeholder widoczny od utworzenia nowej kompozycji do **pierwszej poprawnej klatki nowego wejścia**; dopiero ta klatka uczestniczy w barierze. Określić zachowanie dla braku miniatury, błędu, timeoutu, zmiany indeksu, szybkiego A→B→A i replay. Stara klatka wyłącznie jako świadomy fallback właściwego klipu; bez zaliczania jej do READY i bez naruszania obecnego przypięcia klatek.

7. **[KRYTYCZNE] „Jedno źródło stanu” jest wykonalne, ale same istniejące sygnały nie opisują wszystkich wyników.**

   **Dowód:** `slide_changed` emituje setter indeksu (`player.py:394–404`), jeszcze przed `load_current_slide()` (`player.py:536–548`). Przygotowanie i żądany stan są w `ClipGroup` (`clip_layers.py:51–54,194–199,234–241`), stan grupy statycznej w `running`. Live udostępnia `changed/error`, ale `tick()` nie przekazuje dalej wszystkich zdarzeń cue (`live_layers.py:171–201`). `LiveSession.state=="ready"` nie oznacza, że cue nie trwa.

   **Konsekwencja:** obserwowanie tylko `playbackStateChanged` pokaże „gra” podczas przygotowania dekoderów, a potem „pauza”, mimo że użytkownik oczekuje startu. Nie wyjaśni też klawisza, który niczego nie zmienił.

   **Poprawka planu:** budować wspólny snapshot z istniejących pól i sygnałów, odświeżany także po zakończeniu callbacków nawigacji i zmianach bariery. Dopuszczalne są małe powiadomienia obserwacyjne; bez zmiany reguł upstreamu. Rozdzielić transport bazy/grupy, kierunek reverse, gotowość live i fokus. Nowy zegar odtwarzania jest zbędny; komunikat ~2 s może wygaszać `QTimer.singleShot` z ochroną przed wygaszeniem nowszego komunikatu.

8. **[WAŻNE] Zapowiedziana tabela zdarzeń nie istnieje, a lista klawiszy nie wystarcza.**

   **Dowód:** `PLAN.md:640–642` odwołuje się do tabeli, ale sekcja jej nie zawiera. Rzeczywiste rozgałęzienia to m.in. przygotowanie, wznowienie, oczekiwanie na koniec pętli i przejście (`player.py:625–653`), `auto_next/skip_all` (`player.py:317–345`), granice prezentacji (`player.py:519–548`) oraz timeout bariery live (`clip_layers.py:178–186`, `live_layers.py:145–149`).

   **Konsekwencja:** komunikat „→ slajd 8” może być fałszywy, gdy strzałka tylko wznawia, zamawia wyjście z pętli albo jest konsumowana przez live. Po 5 s baza może ruszyć bez cue, choć live nadal startuje.

   **Poprawka planu:** tabela musi obejmować:

   | Zdarzenie | Wymagane rozróżnienie |
   |---|---|
   | `→` | wznowienie, zamówienie startu, wyjście z pętli, przejście, reverse→normal |
   | `←`, `V`, `R` | zatwierdzone działanie, granica/no-op, brak cofania/replay live |
   | Spacja | pauza/wznowienie grupy, zmiana zamiaru podczas przygotowania, koniec |
   | Pętla | kolejny obrót, żądanie zakończenia, osiągnięcie końca |
   | `auto_next`, `skip_all` | przejście automatyczne bez klawisza |
   | Koniec decku | pozostanie albo zamknięcie przez `exit_after_last_slide` |
   | Wiele prezentacji | identyfikator prezentacji oraz lokalny numer slajdu |
   | D31 | przygotowanie, gotowość, start w pauzie, błąd/timeout klipu lub bazy |
   | Live | start, READY, pominięte cue po timeout, późniejsze READY, błąd |
   | Fokus | klik, Esc, zmiana slajdu, utrata aktywności aplikacji, błąd |
   | Klawisz live | wysłano cue, zignorowano przed READY, autorepeat, koniec sekwencji |

   „Wysłano” nie może oznaczać „wykonano”; potwierdzenie wykonania wymaga zdarzenia protokołu.

9. **[WAŻNE] Nakładka musi należeć do widoku, a skrót wymaga konkretnej decyzji.**

   **Dowód:** okno główne i bieżące Info współdzielą scenę (`composition.py:1–4`, `player.py:253–266`). Domyślne skróty zajmują Q, Space, strzałki, V, R, F, H (`slides/config.py:91–107`), a aktywne live dodatkowo konsumuje Esc i skonfigurowane NEXT/PREVIOUS (`live_layers.py:276–293`).

   **Konsekwencja:** tekst dodany do `SlideComposition` pojawi się również w obrazie Info. Skrót Esc lub strzałka będzie zależał od fokusu. Kombinacja z modyfikatorem nie zapewnia odrębności, bo obecny dispatch operuje kodem klawisza.

   **Poprawka planu:** nakładka jako dziecko viewportu głównego widoku, przezroczysta dla myszy i bez przejmowania fokusu; osobny wiersz Info korzysta z tego samego tekstu. Wybrać np. **S**, wolne w domyślnym zestawie i routerze live. Sprawdzić również konfiguracje użytkownika oraz łączenie klawiszy (`config.py:109–144`), nie tylko `Config()`.

10. **[WAŻNE] Idempotencja demo nie naprawia nawigacji wstecz, a ±1 klatka przeczy przyjętej synchronizacji.**

   **Dowód:** `flip` przełącza kolor i obraca względnie (`examples/live_three.py:21–24`). D33 celowo nie wysyła cue przy `←`, reverse ani replay (`SPEC.md:603–617`). Już zmierzony rozrzut ciepłej sesji wynosił medianowo 48 ms, maksymalnie 51 ms (`PLAN.md:588–595`), podczas gdy 5c żąda końca ±1 klatka (`PLAN.md:638–639`).

   **Konsekwencja:** ustawienie absolutnego kąta końcowego nie gwarantuje powtarzalnej animacji: kolejne wejście może animować od celu do tego samego celu. Idempotentny cue nie przywróci też stanu przy wejściu od tyłu. Równe nominalne długości nie gwarantują wspólnego końca trzech niezależnych rendererów.

   **Poprawka planu:** zdefiniować deterministyczny stan początkowy i końcowy cue oraz sprawdzić, że każde wejście rzeczywiście animuje. Kryterium identycznych pikseli ograniczyć do ustalonego momentu po zatwierdzonym wejściu do przodu. Pozostawić D33 dla cofania i jasno pokazać to w stanie. Wymagać nominalnie 2 s i raportować zmierzony rozrzut; nie obiecywać frame-lock.

11. **[WAŻNE] Diagnoza linii wymaga macierzy prób; sam rozmiar okna jest niejednoznaczny.**

   **Dowód:** `SlideView` wyłącza ramkę, ustawia czarne tło i wykonuje `fitInView` przy show/resize (`composition.py:201–205,245–251`). Scena ma jawny `sceneRect`, baza własny rozmiar, a aktywna obwódka jest elementem tej sceny (`composition.py:32–38`, `live_layers.py:266–274`). Zmiana rozdzielczości prezentacji modyfikuje scenę (`composition.py:48–53`).

   **Konsekwencja:** z kodu nie wynika dowód, że linię tworzy letterbox lub `fitInView`. Możliwe są krawędź obwódki, piksele źródła, szew skalowania albo artefakt backendu. „1614×956” może oznaczać ramkę okna, obszar klienta lub viewport.

   **Poprawka planu:** ustalić rozmiar viewportu i DPR; porównać obraz bazowy/wideo, brak warstw, warstwy bez fokusu, fokus, błąd, nakładkę wyłączoną/włączoną. Porównać render samej sceny, `viewport().grab()` i zrzut prawdziwego okna, zapisać pozycję linii względem `mapFromScene(sceneRect())`. Sprawdzić także przejście między prezentacjami o innych rozdzielczościach. Raport „nie nasz kod” wymaga zawężającego reproduktora.

12. **[WAŻNE] Kryteria pikselowe i budżet nie odpowiadają zakresowi.**

   **Dowód:** `PLAN.md:632–643` nie określa rozdzielczości pomiaru, DPR, maski obiektu, próbkowania ani fps. `tests/test_live_layers.py:87–104` bada surową pixmapę, co nie wykrywa deformacji wprowadzonej transformacją widoku. `test_reverse_shows_clip_end_frame_in_final_rect` sprawdza prostokąt i piksel źródła (`tests/test_clip_layers.py:461–481`), nie proporcje wyświetlonego obrazu. Plan sam odróżnia Qt offscreen od próby ekranowej (`PLAN.md:159–160`).

   **Konsekwencja:** „kwadrat ma równe boki podczas obrotu” nie definiuje pomiaru; dla projekcji 3D może być wręcz nieprawdziwe. Okresowe zrzuty nie dowodzą „w żadnej klatce okna”. Zmiana dopasowania obrazów może świadomie zmienić istniejące oczekiwania testów pikseli, m.in. `test_clip_layers.py:214–237`.

   **Poprawka planu:** określić scenę 2D, kolory/maski, kąty, rozdzielczość renderu, viewport i DPR; mierzyć obraz po kompozycji. Osobno testować transformację geometryczną i wynik rasteryzacji. Ciągłość sprawdzać deterministycznie przy opóźnionej pierwszej klatce, pustych i spóźnionych klatkach, timeoutach oraz błędach; rzeczywisty ekran zostawić próbie prelegenta. Zaktualizować testy wyrażające dawną semantykę rozciągania, zachowując testy z-order.

   **Budżet:** ~4 h jest wiarygodne dla ograniczonego zestawu poprawek, nie dla całego kontraktu wraz z regresjami, stanem, diagnostyką i próbą. Najmniejszy zakres zachowujący cel: poprawne proporcje we wszystkich reprezentacjach, placeholder klipu, deterministyczne demo oraz prosty stan „prezentacja/slajd, transport, live, fokus” w Info i nakładce. Odłożyć bogate komunikaty po każdym klawiszu oraz gwarancję końca ±1 klatka; diagnozę linii prowadzić z osobnym limitem czasu.

**Werdykt:** kontrakt 5c wymaga poprawy przed implementacją. Najpierw zamknąć politykę kadrowania, wszystkie ścieżki dopasowania klipów, cykl placeholdera i tabelę stanu; usunąć gwarancję synchronizacji ±1 klatka. Przegląd był statyczny, read-only — bez uruchamiania GUI i testów.

## Runda 18 — codex, 2026-10-22: kontrakt F5d-f

**Pytania:** Czy podgląd, alfa tła, obwódka i demo są wykonalne w zamkniętym zakresie D17/D20/D27-D34?

**Co weszło:**

1. Przyjęto bramkę GL i ograniczenie gwarancji do pustego tła i pasów; odrzucono naprawę mieszania wszystkich shaderów, bo wymagałaby ingerencji w Manima.
2. Przyjęto pełną ścieżkę krycia przez LiveSpec i capture_first_frame, klucz cache z kryciem i wersją oraz jawny transport prostego RGBA i PNG bez konwersji.
3. Przyjęto zmianę live_publish: pasy odwzorowują camera.background_rgba, test 0/0.5/1; celowo ujednolicamy ich kolor z kamerą zamiast zachowywać stałą czerń przy kryciu 1.
4. Przyjęto obie tożsamości i ciągi D33, zmianę krycia po przerwie oraz zachowanie niespłaszczonego obrazu; style nie są tożsamością procesu.
5. Przyjęto niezależne pętle i szybkości, bez wspólnego restartu; podgląd ma rect_at(0), także nad obrazem.
6. Przyjęto jawne odroczenie ruchu podglądu; odrzucono dodatkowy zegar i wyjątek pozycji bazy od D30 jako zbędne dla grających klipów.
7. Przyjęto brak dekodowania ukrytego Info i pomiar wpływu w próbie człowieka; odrzucono automatyczny próg CPU/GPU i benchmark 1/2/3 źródeł jako rozszerzenie bez dostępnego prawdziwego okna.
8. Przyjęto normalny plik i pierwszą miniaturę w reverse, sprzątanie celu, końca i zamknięcia oraz odcięcie callbacków.
9. Przyjęto Color Pydantic bez Qt, jego zapis JSON, mnożenie alfy przez opacity, skończone liczby i zgodność starszych decków.
10. Przyjęto jawny indeks i rolę; aktywna warstwa ma pierwszeństwo nawet z None, release wybiera pierwszy błąd nawet z None; szerokość ograniczona do wymiarów kontenera.
11. Przyjęto kontrolowane klatki i końcową kompozycję, surową alfę oraz regresje; odrzucono gwarancję dowolnej półprzezroczystej treści GL zgodnie z punktem 1.
12. Przyjęto kontrastową bazę pod live, pasy, instrukcję klik/Esc, korektę mianowników i test dziewięciu slajdów; render CE i GL oddzielony od próby playera. Przy rect_at(0) klip 5 zaczyna w kadrze (zachowuje powiększanie), aby podgląd pokazywał animację.
13. Przyjęto większy budżet i ograniczenia zakresu; odrzucono wycięcie walidacji ciągłości, cache i pełnych regresji.

**Odpowiedź codex (bez zmian):**

1. **[KRYTYCZNE] 5e zakłada, że wystarczy rozpoznać jeden format alfy całej klatki. Kod manimgl tego nie gwarantuje.**

   **Dowód:** `.venv/Lib/site-packages/manimlib/camera/camera.py:124` czyści framebuffer surowym `background_rgba`; `:141` odczytuje jego zawartość bez konwersji alfy. `shader_wrapper.py:370` ustawia osobne mieszanie RGB i alfy dla wypełnień, `:392` nakłada teksturę jako premultiplikowaną, a `:397` przywraca `glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)`. Obecny odbiornik deklaruje prostą alfę: `src/manimcue/live_layers.py:193`.

   **Konsekwencja:** nie można bezwarunkowo zmienić `QImage` na `RGBA8888_Premultiplied`. Zwykłe mieszanie z `SRC_ALPHA` mnoży również składową alfa źródła, natomiast ścieżka wypełnień robi to inaczej. Nieczarne przezroczyste tło dodatkowo może naruszać warunek RGB ≤ alfa wymagany dla premultiplikacji. Jeden piksel pustego tła przy `background_opacity=0.5` nie sprawdzi półprzezroczystej treści ani krawędzi.

   **Poprawka planu:** rozpocząć 5e od bramki wykonalności: rzeczywisty GL, tło czarne i kolorowe, wypełnienie, stroke oraz nakładanie dwóch półprzezroczystych obiektów. Zapisać oczekiwane RGBA przed Qt i wynik nad znanym tłem. Dopiero wtedy ustalić normalizację i format transportu. Jeżeli pełna poprawność wymaga ingerencji w Manima, ograniczyć gwarancję zamiast obiecywać naprawę samym wyborem formatu `QImage`.

2. **[WAŻNE] Miniatura wymaga osobnej konwersji i zmiany klucza cache.**

   **Dowód:** `src/manimcue/slides/slide/base.py:723` buduje klucz bez `background_opacity`; `:727` tworzy `LiveSpec` bez tego parametru; `:729` zapisuje bajty przez `Image.frombytes("RGBA", ...)`. `src/manimcue/live_session.py:18` także nie ma pola krycia.

   **Konsekwencja:** po zmianie krycia można dostać starą, nieprzezroczystą miniaturę. Jeżeli transport zostanie premultiplikowany, zapisanie jego bajtów jako zwykłego RGBA do PNG da błędne kolory przy późniejszym wczytaniu.

   **Poprawka planu:** wymienić pełną ścieżkę parametru: model → `LiveSpec` → worker, również dla `capture_first_frame`. Dodać krycie i wersję interpretacji pikseli do klucza miniatury. Jawnie ustalić konwersję transport → PNG oraz test miniatury po ponownym renderze z innym kryciem bez `--flush-cache`.

3. **[WAŻNE] Pasy D34 powstają poza kamerą; parametr kamery ich nie zmieni.**

   **Dowód:** `src/manimcue/live_scene.py:545` tworzy czarny canvas, a `:546` bezwarunkowo ustawia alfę pasów na 255. `PLAN.md:703` wymaga przepuszczania tła przez pasy.

   **Konsekwencja:** samo zastąpienie stałej w `live_worker.py:40` pozostawi czarne, nieprzezroczyste pasy. Przy kryciu pośrednim mogą też powstać inne kolory pasów i właściwego tła kamery.

   **Poprawka planu:** wskazać `live_publish` jako obowiązkowe miejsce zmiany. Ustalić, czy pasy odwzorowują rzeczywiste `camera.background_rgba`, czy zawsze czarne tło o zadanym kryciu. Sprawdzić środek i oba pasy dla 0, 0.5 i 1, również w miniaturze.

4. **[WAŻNE] Spójność krycia sesji jest właściwa, ale tylko wewnątrz ciągu D33. Brakuje tożsamości wykonawczej i testu zapamiętanego obrazu.**

   **Dowód:** `SPEC.md:593` definiuje ciąg sąsiednich wystąpień; przerwa otwiera nową generację (`:597`). `config.py:524` waliduje właśnie takie ciągi. Kontroler niezależnie buduje tożsamość w `live_layers.py:100`. Ostatni `QImage` i jego bajty są zachowywane w `:200`, a ponownie wstawiane w `:131`. Obecny test przejęcia obrazu: `tests/test_persistent_live.py:132`.

   **Konsekwencja:** globalny zakaz różnych wartości dla tego samego ID byłby nadmiarowy. Dodanie pola tylko do walidatora pozostawi dwie różne definicje tożsamości. Sam test zachowania obrazu nie wykryje wcześniejszego spłaszczenia do starej bazy.

   **Poprawka planu:** dopisać krycie do obu tożsamości; dopuścić inne krycie po przerwie ciągu. Testować A → B ze zmianą indeksu warstwy i koloru bazy, bez nowej publikacji live: zachowany obraz ma ponownie mieszać się z bazą B. Style obwódki mogą zmieniać się między slajdami bez restartu sesji.

5. **[WAŻNE] „Wspólny start pętli” podglądu jest niejednoznaczny dla różnych długości materiałów.**

   **Dowód:** `PLAN.md:688–692` nakazuje zapętlać klipy i obiecuje wspólny start pętli. Dzisiejsza baza podglądu ma własne `setLoops(-1)` (`player.py:127`). Główne klipy zapętlają się niezależnie (`clip_layers.py:106`). Walidacja długości zwalnia klipy z `loop` i bazy statyczne (`PLAN.md:369`).

   **Konsekwencja:** dla bazy 2 s i klipu 3 s nie wiadomo, czy klip restartuje po 2 s, czy kończy własną pętlę. Dla klipu 1 s nie wiadomo, czy drugi obrót zaczyna samodzielnie. Nad obrazem nie istnieje pozycja wideo bazy ani granica jej pętli.

   **Poprawka planu:** wybrać jedno zachowanie. Najmniejszy zakres: wspólny start tylko początkowy, później niezależne pętle; jawnie zaakceptowany dryf. Dla bazy statycznej określić osobno zegar ruchu albo pozostawić geometrię w `rect_at(0)`. Dodać przypadki klip krótszy/dłuższy, różne szybkości i baza-obraz.

6. **[WAŻNE] Ruch podglądu świadomie odbiega od D30, ale plan nie nazywa tej różnicy.**

   **Dowód:** `PLAN.md:690` wybiera pozycję bazy. `SPEC.md:565–568` odrzuca ten zegar z powodu skoków pętli, szybkości i aktualizacji co około 50 ms. Okno główne używa aktywnego czasu (`clip_layers.py:287`).

   **Konsekwencja:** przy szybkości bazy 2× podgląd wykona ruch dwa razy szybciej niż okno główne; przy pętli geometria podglądu wróci do początku, podczas gdy główna pozostanie na końcu. To może być zamierzone, lecz „tym samym `rect_at`” nie oznacza tego samego zachowania.

   **Poprawka planu:** zapisać wyjątek od D30 oraz jednostkę czasu: `position()/1000`, reset przy pętli i zachowanie podczas ładowania. Testować zadane pozycje, szybkość 2× i przejście koniec → początek. Jeżeli celem jest wierny podgląd, użyć osobnego aktywnego zegara podglądu.

7. **[WAŻNE] Niezależność logiczna podglądu nie gwarantuje braku spowolnienia okna głównego.**

   **Dowód:** `composition.py:3` potwierdza wspólną kompozycję okna głównego i bieżącego Info; następny slajd ma osobną. `player.py:127` ma już osobny dekoder bazy podglądu. Kolejny klip oznacza kolejny `QMediaPlayer` i sink (`clip_layers.py:96`). Pomiary w `PLAN.md:336–340` pokazują zauważalny czas przygotowania i zależność rozrzutu od liczby źródeł.

   **Konsekwencja:** dodatkowe dekodery współdzielą CPU, zasoby GPU, pamięć i obsługę GUI. Mały viewport 360×240 nie jest gwarancją dekodowania materiału w tej rozdzielczości. Zielony test bariery nie wykluczy pogorszenia czasu przejścia. Z kodu nie da się wywnioskować faktycznego użycia dekodera sprzętowego Qt FFmpeg.

   **Poprawka planu:** dodać pomiar z podglądem włączonym/wyłączonym: baza + 1/2/3 klipy i live, czas przejścia do zmienionej klatki, czas przygotowania, tempo klatek i obciążenie CPU/GPU. Ustalić próg regresji przed implementacją. Rozważyć start podglądu dopiero po zwolnieniu bariery głównej oraz zatrzymanie dekoderów przy ukrytym Info.

8. **[WAŻNE] Reverse i sprzątanie potrzebują kontraktu dla celu podglądu, a nie flagi okna głównego.**

   **Dowód:** podczas reverse `next_slide_config` zwraca bieżący slajd (`player.py:446–448`), a `preview_next_slide` używa jego normalnego `file` (`:606`). `composition.py:125` wybiera `end_thumbnail` tylko dla `at_end`. `player.py:653` sprząta główny kontroler klipów, lecz nie ma analogicznej ścieżki dla nowych klipów podglądu.

   **Konsekwencja:** skopiowanie konfiguracji głównej może wyświetlić w podglądzie nieruchome `end_thumbnail` zamiast klipu do przodu. Sprzątanie wyłącznie przy zmianie indeksu ominie reverse → normalny, koniec decku i zamknięcie. Spóźniony callback może trafić do przebudowanego elementu.

   **Poprawka planu:** podgląd zawsze normalnego `file`, pierwszej miniatury i geometrii początkowej — również podczas reverse; `end_thumbnail` zachować dla głównego reverse. Sprzątanie powiązać ze zmianą celu/trybu podglądu i zamknięciem. Wymagać odcięcia starych callbacków, zwolnienia sinków, timerów i źródeł. Test A → B → A oraz przejście między prezentacjami o różnych rozdzielczościach.

9. **[WAŻNE] Kontrakt koloru i liczb `BorderStyle` jest zbyt szeroki oraz niedookreślony.**

   **Dowód:** `config.py:25` już używa `pydantic_extra_types.color.Color`; import Qt jest celowo odroczony (`:53–55`). `PLAN.md:710` obiecuje dowolną „nazwę albo hex”, lecz nie określa składni, alfy koloru ani skończoności szerokości.

   **Konsekwencja:** walidacja przez `QColor` wprowadzi zależność modelu/renderowania od Qt. Walidatory Qt i Pydantic nie muszą akceptować tego samego zbioru nazw i formatów hex. Kolor zawierający alfę oraz osobne `opacity` mają dwie możliwe interpretacje. Samo `width > 0` dopuszcza nieskończoność.

   **Poprawka planu:** walidować bez Qt, np. istniejącym `Color`, i określić jego składnię jako publiczny kontrakt. Ustalić kanoniczny zapis JSON oraz mnożenie alfy koloru przez `opacity` albo zakazać alfy w kolorze. Wszystkie liczby muszą być skończone. Brak pól w starym v2/v3 ma dawać dotychczasowe style; jawne `null` wyłączać obwódkę. Dodać test importu/walidacji modelu bez ładowania Qt i round-trip całego decku.

10. **[WAŻNE] Jedna obwódka wymaga jawnego stanu roli, szczególnie przy `None`.**

    **Dowód:** `live_layers.py:225` przenosi obwódkę na błąd; `:235` na aktywną warstwę; `:266` po zwolnieniu wybiera pierwszy błąd. Przy ruchu `:273` przekazuje dalej jedynie aktualny kolor. `frame_layer` używa stałej szerokości (`:277–282`).

    **Konsekwencja:** po dodaniu różnych stylów kolor nie wystarczy do odtworzenia szerokości, krycia i roli. Wyłączenie stylu aktywnej warstwy może zostawić poprzednią obwódkę błędu albo ją ukryć — plan nie rozstrzyga. Nie wiadomo też, czy po `release` pomijać błędy z `error_border=None`.

    **Poprawka planu:** zdefiniować wybór `(indeks, aktywna/błąd)` i dopiero z niego wyliczać cały styl. Określić pierwszeństwo oraz zachowanie niewidocznego stylu. Test: dwie warstwy o różnych stylach, błąd jednej, aktywacja drugiej, ruch, `release`, warianty `None`. Dodać zachowanie szerokości większej niż mały kontener — obecne odsunięcie o połowę szerokości może odwrócić prostokąt.

11. **[WAŻNE] Obecne kryteria obrazu mogą przejść mimo błędnego działania.**

    **Dowód:** `PLAN.md:721` wymaga tylko dwóch różnych klatek po ponad 200 ms. Bazowy generator testowych klipów jest niemal cały jednokolorowy (`tests/test_clip_layers.py:40`), a helper live odczytuje RGB samej pixmapy z tolerancją 50 (`tests/test_live_layers.py:87–97`). D22 wymaga masek i tolerancji (`SPEC.md:491–497`).

    **Konsekwencja:** różnicę w prostokącie klipu może spowodować baza lub ruch miniatury. Działający klip okresowy może dać dwie identyczne próbki. Odczyt samej pixmapy nie dowodzi poprawnego mieszania. Kontrola pióra nie sprawdza widocznego krycia ani grubości obwódki.

    **Poprawka planu:** użyć nieruchomej bazy i klipu z kontrolowanymi zmianami koloru, osobno testować ruch. Dla alfy renderować końcową kompozycję nad nieprzezroczystym znanym tłem, mierzyć również surową alfę przez `pixelColor`. Sprawdzać miniaturę, pierwszą i zachowaną klatkę, pasy, hit-test i widok Info. Zachować testy D22 oraz F2 dla domyślnego krycia i dodać wariant przezroczysty; koszt konwersji mierzyć także w GUI. Offscreen nadaje się do tych testów, ale nie zastępuje pomiaru wydajności i próby w prawdziwym oknie.

12. **[DROBNE] Slajd 9 nie ma jeszcze scenariusza gwarantującego widoczny efekt; „1–8 bez zmian” utrwala błędne notatki.**

    **Dowód:** po slajdzie 8 pozostaje znacznik po lewej stronie (`examples/demo.py:151–170`). Plan nie określa jego położenia względem nowego live (`PLAN.md:717`). Notatki zawierają już mianowniki `/3`, `/4`, `/5`, `/6` i `/8` (`demo.py:88`, `:107`, `:129`, `:141`, `:163`).

    **Konsekwencja:** animacja bazy poza obszarem live nie pokaże różnicy między czarnym i przezroczystym tłem. Sam render CE/GL nie pokaże obwódki aktywowanej dopiero w playerze. Dopisanie slajdu na końcu zachowuje istniejące indeksy, ale zwiększa niespójność opisów.

    **Poprawka planu:** określić kontrastowy obiekt bazy przechodzący przez pustą część live, panel o innych proporcjach dla pokazania pasów oraz instrukcję kliknięcia i Esc. Kryterium rozdzielić na render obu silników i prezentację z procesem live GL. Usunąć mianowniki z notatek albo ujednolicić je do dziewięciu; dopuścić te korekty mimo „bez zmian”. Nie znalazłem podstawy do zakładania istniejącego testu pełnego, dziewięcioslajdowego demo — trzeba go jawnie zaplanować.

13. **[WAŻNE] Budżet 6,5 h pomija rozstrzygnięcia techniczne i walidację wydajności.**

    **Dowód:** `PLAN.md:732` przydziela 2 h na alfę i 3 h na podgląd, mimo nieustalonej semantyki pętli oraz kilku ścieżek reprezentacji obrazu. Poprzednia faza osobno budżetowała regresje i diagnozę (`:669`); samo pełne uruchomienie zestawu trwało ponad pięć minut (`:673`).

    **Konsekwencja:** 6,5 h jest celem prototypu, nie wiarygodnym zobowiązaniem dla obecnych kryteriów. Największą niewiadomą pozostaje poprawność alfy manimgl, której nie należy ukrywać pod kosztem „przekazania parametru”.

    **Poprawka planu:** najpierw krótki PoC alfy z decyzją zakresową. Aby utrzymać budżet: niezależne pętle podglądu bez wspólnego restartu, bez ruchu podglądu w pierwszym przyroście, ograniczony jawny format kolorów. Zachować animowane klipy, przezroczyste puste tło live, własny styl obwódki i czytelne demo. Nie wycinać testów ciągłości sesji, cache miniatur ani pomiaru wpływu podglądu na przejścia.

**Werdykt:** plan wymaga korekty przed implementacją, przede wszystkim ustalenia rzeczywistego kontraktu alfy oraz pętli podglądu. Spójność `background_opacity` w ciągu D33 jest zasadna. Przegląd był read-only; nie wykonywałem nowych pomiarów GPU/CPU ani testów, więc nie przypisuję dodatkowym dekoderom niezmierzonego kosztu liczbowego.

**Walidacja po domknięciu:** wykonano próbę dodatkowej recenzji `codex exec -s read-only`
zgodnie z CLAUDE.md; połączenie do API zablokowane przez sandbox (socket error 10013,
fallback HTTPS również bez połączenia). Nowa odpowiedź nie powstała; rozstrzygnięcia powyżej
opierają się na dostarczonej pełnej rundzie 18 i walidacji kodu/testów.


## Runda 19 — codex, 2026-10-23: kontrakt F7a (adapter live Cairo)

**Pytania:** Czy zegar, lifecycle, historia, alfa i izolacja silników zapewniają panel live CE w decku fazy 8 bez patchowania Manima?

**Co weszło:**

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

**Odpowiedź codex (bez zmian):**

1. **[KRYTYCZNE] Plan wraca do zegara, który już oblał pomiar na Windows.**

   **Dowód:** `PLAN.md:887` proponuje `select` z timeoutem jednej klatki. Tymczasem `PLAN.md:183–187` dokumentuje około 29 fps wskutek zaokrąglania timeoutu; działające rozwiązanie używa `time.sleep` i nieblokującego odczytu gniazda (`src/manimcue/live_scene.py:573–579`).

   **Konsekwencja:** szybki render Cairo nie zapewni proponowanych 60 odebranych klatek/s.

   **Poprawka planu:** zachować istniejący mechanizm terminów: zegar monotoniczny, `sleep` do terminu, `live_poll(0)`, pomijanie spóźnionych terminów. `select` z timeoutem zostawić do bezczynności i barier.

2. **[WAŻNE] Sterowanie `play()` bez patchowania CE jest wykonalne, ale granica nadpisania jest niedookreślona.**

   **Dowód:** CE przekazuje `play()` przez `manager.py:260` do renderera. `renderer/cairo_renderer.py:123–134` wykonuje begin, przygotowuje obraz statyczny i wybiera osobno frozen wait albo `play_internal()`. `update_frame()` jest oddzielne od `render()` i kopiującego `get_frame()` (`:139`, `:183–195`). Jednak renderer przed każdym play odtwarza `skip_animations` i przelicza pomijanie (`:78–79`); sekcja może ponownie je włączyć (`:269–270`).

   **Konsekwencja:** samo nadpisanie `play_internal()` oraz wyłączenie cache nie kontroluje całego przebiegu. `next_section(skip_animations=True)` może naruszyć założenia zegara mimo poprawnej konfiguracji startowej.

   **Poprawka planu:** wskazać dokładnie odpowiedzialność podklasy renderera: polityka skip dla każdego play, frozen wait, begin/cleanup i publikacja. Jawnie odrzucać albo ignorować sekcje pomijające animacje. `format=none` i `disable_caching=True` są właściwe: pierwsze wyłącza wyjście, drugie hashowanie — to osobne warunki (`_config/output_plan.py:266`, `cairo_renderer.py:88–104`).

3. **[WAŻNE] D10 nie definiuje końcowego stanu updaterów.**

   **Dowód:** plan wymaga `finish()`/cleanup i doprowadzenia czasu logicznego do końca (`PLAN.md:852–860`). CE `Animation.finish()` wykonuje interpolację do 1 i wznawia updatery (`animation/animation.py:216–227`), ale dodatnie `dt` dociera do updaterów przez `Scene.update_to_time()` (`scene/scene.py:1714–1724`). Zwykłe zakończenie pętli wykonuje jeszcze `update_mobjects(0)` (`:1412–1413`).

   **Konsekwencja:** animowany `Transform` osiągnie koniec, lecz niezależny updater przesuwający obiekt przez `dt` pozostanie w stanie chwili przerwania. Sam skok `Scene.time` tego nie naprawia. Określenie „stan końcowy całego cue” jest za szerokie.

   **Poprawka planu:** określić, czy D10 domyka wyłącznie animacje, czy również integruje brakujące `dt` updaterów. Najmniejszy zakres zgodny z obecnym GL: domknięcie animacji bez symulowania pominiętego czasu updaterów. Dodać test animacji równoległej z niezależnym updaterem i kolejnego play odczytującego `Scene.time`.

4. **[WAŻNE] „Statyczne `wait` ze `stop_condition`” nie odpowiada klasyfikacji CE.**

   **Dowód:** CE traktuje obecność `stop_condition` jako powód aktualizowania sceny (`scene/scene.py:461–471`). `Wait` odrzuca jednoczesne `stop_condition` i `frozen_frame=True` (`animation/animation.py:615`). Plan żąda statycznego/dynamicznego stop_condition oraz zachowania frozen frame (`PLAN.md:865`, `:980`).

   **Konsekwencja:** implementator nie wie, czy ma zachować semantykę CE, czy wprowadzić nową optymalizację „nieruchomy obraz, ale aktywny warunek”.

   **Poprawka planu:** rozpisać macierz: zwykłe statyczne wait, wait z updaterem, wait z warunkiem bez ruchu, frozen wait oraz niedozwolone połączenie frozen+warunek. Dla warunku zakończonego wcześniej zdefiniować czas logiczny jako faktycznie odczekany, bez skoku do maksymalnego czasu.

5. **[KRYTYCZNE] Snapshot obiecuje zachowanie grafu obiektów, ale nie podaje mechanizmu, który to zapewnia.**

   **Dowód:** `PLAN.md:915–921` gwarantuje referencje autora, współdzielone dzieci i dokładne relacje grup. CE `Mobject.copy()` to `deepcopy` (`mobject/mobject.py:1016–1029`); `Transform.begin()` kopiuje cel i wyrównuje strukturę źródła (`animation/transform.py:200–211`). Wyrównanie może tworzyć dodatkowe submobjecty (`mobject/mobject.py:3204–3228`).

   **Konsekwencja:** osobne kopie dwóch grup ze wspólnym dzieckiem mogą utracić współdzielenie. Transformowanie rodzica i dziecka osobnymi animacjami może aktualizować ten sam obiekt wielokrotnie. Przywrócenie list sceny/foreground nie przywraca automatycznie grafu ani wszystkich referencji.

   **Poprawka planu:** najpierw osobna bramka snapshotu: mapa oryginał→stan, wspólne memo kopiowania i jawne odtworzenie krawędzi grafu. Określić obsługiwane pola oraz updaterów. Nie przedstawiać `Restore`/`Transform` jako gotowego rozwiązania tej gwarancji; przy ograniczeniu budżetu zawęzić snapshot do udokumentowanego korpusu panelu.

6. **[WAŻNE] Cofanie nazwanych cue jest niespójne już między kontraktem a istniejącym GL.**

   **Dowód:** D33 wyklucza cofanie nazwanych `enter_cue` (`SPEC.md:615–617`), podobnie `PLAN.md:921`. Obecny live GL wywołuje `save_state()` przed każdym presetem, również nazwanym (`live_scene.py:425–437`). `step_back()` zmniejsza kursor i cofa ostatni snapshot (`:363–367`).

   **Konsekwencja:** po `next → nazwany enter_cue → back` kursor cofnie sekwencję, ale obraz cofnie nazwane cue. CE nie może jednocześnie zachować tej implementacji i deklarowanej semantyki D33.

   **Poprawka planu:** dodać ten konkretny test i ustalić wspólną politykę historii. Snapshot musi być powiązany z pozycją sekwencji albo należy jawnie zmienić kontrakt. Uwzględnić też limit historii: GL ogranicza ją do 50 stanów i deduplikuje (`manimlib/scene/scene.py:660–667`); CE nie ma określonego limitu ani zasad deduplikacji.

7. **[WAŻNE] Koszt cofania CE nie został zmierzony, a wynik GL nie jest przenośny.**

   **Dowód:** GL współdzieli niezmienione kopie między snapshotami (`manimlib/scene/scene.py:880–887`), a rewind tworzy dodatkowe kopie celów (`live_scene.py:332`). CE dodatkowo kopiuje cel wewnątrz `Transform.begin()` (`animation/transform.py:205`). Mikrobenchmark mierzy wyłącznie render i jedną kopię pikseli (`experiments/f7a_cairo/measure.py:100–109`).

   **Konsekwencja:** budżet 0,6 s animacji nie obejmuje przygotowania snapshotów, wyrównania geometrii ani pamięci. Wyniku „0,2 ms + 1–2 ms” z D10 GL nie można użyć dla CE.

   **Poprawka planu:** zmierzyć osobno snapshot, przygotowanie Transform, przywrócenie i pamięć po wielu cue; uwzględnić grupę o zmienionej liczbie dzieci. Gwarancję czasu rewind liczyć od komendy do odebranej klatki końcowej, z osobnym raportem pracy przygotowawczej.

8. **[WAŻNE] Bootstrap i sprzątanie po błędzie pozostają opisem intencji.**

   **Dowód:** `PLAN.md:838–839` wymaga respektowania lifecycle. CE manager uruchamia setup przed blokiem `try`; przy wyjątku z construct abortuje encode jobs i ponownie rzuca wyjątek, bez dojścia do tear_down (`manager.py:153–175`). Obecny worker sprząta zasoby specyficzne dla GL: `scene.file_writer`, `scene.camera.ctx.release()` (`live_worker.py:56–60`).

   **Konsekwencja:** proste podmienienie `run()` na `render()` nie daje obiecanego sprzątania przy błędzie build/cue. Bez określenia roli `construct()` autor może też przypadkowo ominąć pętlę live własnym nadpisaniem.

   **Poprawka planu:** określić własność lifecycle i backendowego finalizera, dokładnie jeden cleanup oraz zachowanie oryginalnego wyjątku. Ustalić, że bazowe `construct()` prowadzi build i pętlę cue, a jego nadpisanie jest poza kontraktem lub walidowane. Shutdown podczas animacji ma przerywać pętlę bez wykonywania reszty callable; shutdown podczas blokującego import/build wymaga nadzorcy i kill.

9. **[WAŻNE] Izolacja silników jest właściwym kierunkiem, lecz konfiguracja CE wymaga dłuższego zakresu ochrony.**

   **Dowód:** worker importuje obecnie GL przed plikiem autora (`live_worker.py:15–25`). CE `tempconfig` mutuje globalny singleton i przy wyjściu go przywraca (`_config/__init__.py:75–88`); renderer nadal czyta globalny config podczas kolejnych play (`cairo_renderer.py:88`, `:274`). Plan mówi o konfiguracji przed konstrukcją, lecz nie określa jej ponownego narzucenia po imporcie autora ani utrzymania przez całą sesję (`PLAN.md:866`, `:927–928`).

   **Konsekwencja:** moduł autora ustawiający `config.renderer`/cache/wyjście może unieważnić konfigurację workera. Krótki `tempconfig` tylko wokół konstruktora również nie wystarczy.

   **Poprawka planu:** import autora, następnie narzucenie obowiązkowych ustawień live i utrzymanie ich przez cały lifecycle. Dodać równoległy test dwóch procesów CE z różnymi wymiarami/fps/kryciem oraz GL obok. Procesy spawn izolują singletony; sam wspólny import `manim` i `manimlib` nie jest dowodem konfliktu. Gwarancję „bez GL” ograniczyć do importów infrastruktury — plik autora może sam importować oba silniki. Migracja v2/v3→GL i jawny v4 są sensowne.

10. **[WAŻNE] Mikrobenchmark jest poprawnie opisany, ale nie uzasadnia proponowanych progów.**

    **Dowód:** 30 klatek rozgrzewki i 240 próbek są rzeczywiście odrzucane/zapisywane, a mediana i p95 liczone poprawnie (`measure.py:63–64`, `:99–119`). Cały przebieg trwał jednak tylko 8,21 s (`results.json:16838`), z ustaloną kolejnością rozmiarów i przypadków (`measure.py:79`, `:86`). Aktualizacja geometrii jest poza stoperem; kopia dotyczy obszaru treści, nie całego payloadu panelu (`:100–104`). Rzeczywisty transport kopiuje pełny bufor, a odbiornik dodatkowo go odwraca (`frame_buffer.py:55–56`, `:103–108`).

    **Konsekwencja:** tabela jest wiarygodnym wynikiem krótkiego mikrobenchmarku, nie pomiarem stabilności 60 fps, kosztu SHM ani wielu warstw. Dużo wolniejszy render treści 538×303 niż 960×540 pozostaje niewyjaśniony. Teza raportu, że zapas „uzasadnia” 60 fps (`REPORT.md:46`), jest mocniejsza niż dane.

    **Poprawka planu:** pozostawić 60 fps jako cel produktowy do sprawdzenia. Powtórzyć pomiar w kilku niezależnych przebiegach ze zmienioną kolejnością, mierzyć pełny payload i cały tor Qt. Raportować rozrzut między przebiegami oraz maksimum/opóźnione klatki. Nie sumować osobnych p95 — obecny skrypt słusznie liczy p95 sum sparowanych próbek.

11. **[WAŻNE] Kryteria offscreen nie mają jeszcze wystarczająco precyzyjnych wyroczni.**

    **Dowód:** `PLAN.md:975–996` wymaga „dokładnej maski”, „różnych klatek”, pierwszej klatki i zgodności alfy. `Wait` z warunkiem może nie zmieniać obrazu; rotacja może okresowo powtarzać obraz. Panel 538×648 ma treść 538×303, czyli 345 wierszy pasów (`PLAN.md:894`), a więc asymetryczny podział pasów.

    **Konsekwencja:** licznik frame_id może zaliczyć duplikaty; hash całego obrazu nie opisuje regularności ruchu. „Dokładna maska” nie określa tolerancji antyaliasingu. Symetryczna scena nie wykryje odwrócenia ani przesunięcia pasa o piksel.

    **Poprawka planu:** ustalić sposób liczenia zmian pikseli, obszar pomiarowy, ciągły ruch przez całe 30 s i tolerancję rasteryzacji. Dodać asymetryczne narożniki i jawne współrzędne treści dla nieparzystych pasów. Dla alfy sprawdzać rzeczywiste złożenie Qt nad znaną bazą, również miniaturę i klatkę zachowaną D33. Wymiar bufora ma wynikać z rozdzielczości decku i rect, zgodnie z `LiveLayer.size()`, nie z aktualnego rozmiaru okna.

12. **[WAŻNE] Część wskazanych przypadków już istnieje; brakuje ich istotnych kombinacji.**

    **Dowód:** błąd build, nieznana komenda, shutdown i D33 są już wymienione (`PLAN.md:976`, `:982–990`). Rozdział nie żąda jednak wprost: nieznanego `enter_cue`, zamknięcia playera podczas aktywnego play, błędu ciepłej sesji podczas przejęcia, dwóch jednocześnie animujących warstw CE ani zmiany krycia na granicy dwóch generacji.

    **Konsekwencja:** można zaliczyć wszystkie pojedyncze kryteria i nadal uzyskać zawieszony start grupy, odziedziczony błędny proces lub nieaktualny obraz po zmianie slajdu.

    **Poprawka planu:** dopisać te kombinacje z oczekiwanym wynikiem: nieznane cue nie abortuje bieżącego, zamknięcie odbiera wszystkie procesy/SHM, ERROR/stopping nie podlega przejęciu, przerwa pozwala zmienić krycie, sąsiedni ciąg tego zabrania. Zachować rozróżnienie: offscreen sprawdza routing zdarzeń, próba człowieka — rzeczywisty fokus i projektor.

13. **[WAŻNE] Budżet 12 h nie ma podstaw dla zadeklarowanego zakresu.**

    **Dowód:** `PLAN.md:1004–1006` przydziela snapshotowi zachowującemu graf 2 h, a całemu korpusowi, pomiarom i regresjom 3 h. Jednocześnie zakres obejmuje nowy backend, zegar, wszystkie odmiany wait, rewind, kamerę, normalizację alfy, migrację formatu, miniatury i D33.

    **Konsekwencja:** największe niewiadome mają sztywne małe estymaty, zanim wykonano dowód wykonalności. Limit 24 h może zostać osiągnięty przy częściowo zintegrowanym adapterze.

    **Poprawka planu:** podzielić na bramki z osobnymi estymatami po wyniku: lifecycle/zegar/alfa → panel i transport → integracja D33 → rozszerzenia. Dla celu fazy 8 można odroczyć pan/zoom/reset, obsługę animowanej kamery i snapshot dowolnego grafu, ograniczając gwarancję do jawnego korpusu panelu seminarium. Zachować D10, podstawowe cofanie potrzebnych cue, miniaturę, błędy i D33. To wymaga jawnego zawężenia deklaracji zachowania D1–D35.

14. **[DROBNE] Część odsyłaczy CE nie odpowiada obecnemu plikowi.**

    **Dowód:** plan wskazuje `update_frame:159`, `render:194`, `add_frame:217` (`PLAN.md:846–848`); obecne `update_frame` zaczyna się w `cairo_renderer.py:139`, a `render` wywołuje `get_frame()` w `:184`; kopia jest wewnątrz `get_frame:195`.

    **Konsekwencja:** dowód wygląda na dokładniejszy, niż jest, i utrudnia późniejszą implementację.

    **Poprawka planu:** odświeżyć odsyłacze oraz zapisać identyfikator/hash zainstalowanego źródła CE obok wersji 0.22.0.

**Werdykt:** nie zatwierdzać kontraktu w obecnej postaci. Adapter Cairo bez patchowania Manima jest wykonalny; blokują go przede wszystkim sprzeczny mechanizm tempa, nieustalona semantyka historii/back oraz zbyt szeroka gwarancja snapshotu. Pomiar nie jest fałszywy, ale potwierdza wyłącznie szybkie rysowanie prostych scen. Przegląd był read-only; nie uruchamiałem benchmarku ani nie zmieniałem plików.

## Runda 20 — codex, 2026-10-23: kontrakt F5g (checkpointy live)

**Pytania:** Czy checkpointy obu silników, rezerwacja, ACK, historia, generacje, bariera i fallback zapewniają zgodny i czytelny stan live po ←, V i R?

**Co weszło:**

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

**Odpowiedź codex (bez zmian):**

1. **[KRYTYCZNE] GL nie zapewnia obiecanego dokładnego odtworzenia grafu i updaterów.**

   **Dowód:** `PLAN.md:832–839` odsyła do D37, a kryterium `PLAN.md:888–892` wymaga dokładnego grafu, referencji i updaterów w obu silnikach. GL zapisuje `get_state()` (`src/manimcue/live_scene.py:234–238`), a przywraca przez `undo()` (`:264`). W zainstalowanym ManimGL `SceneState.restore_scene()` używa `mob.become(mob_copy)` (`.venv/Lib/site-packages/manimlib/scene/scene.py:906–911`). `become()` domyślnie ma `match_updaters=False`, wyrównuje rodziny i przenosi dane wizualne (`.venv/Lib/site-packages/manimlib/mobject/mobject.py:718–740`). Snapshoty dodatkowo współdzielą wcześniejszą kopię na podstawie wizualnego `looks_identical()` (`scene.py:880–887`), które nie porównuje updaterów (`mobject.py:743–765`).

   **Konsekwencja:** zmiana updatera bez zmiany obrazu może nie trafić do nowego snapshotu; przywrócenie wyglądu nie dowodzi przywrócenia updaterów ani tożsamości dzieci po zmianie topologii. „Użyć istniejących snapshotów” nie wystarcza do zaliczenia wspólnego kontraktu CE/GL.

   **Poprawka planu:** jako pierwszą bramkę sprawdzić GL: zmianę updatera przy identycznym obrazie, usunięcie dziecka, współdzielone dziecko i referencję autora do przywracanego dziecka. Następnie albo rozszerzyć adapter snapshotów bez patchowania Manima, albo zawęzić wspólną gwarancję i kryterium 2. Nie deklarować dokładności przed tą bramką.

2. **[KRYTYCZNE] Brakuje blokady między przygotowaniem checkpointu a wykonaniem wejścia.**

   **Dowód:** `PLAN.md:825–828` zabrania przeplatania operacji z ręcznym cue „podczas przygotowania”. Po przygotowaniu `start_paused` pozostawia jednak cue oczekujące na start (`:818–819`). D20 nadal kieruje strzałki do aktywnego live (`SPEC.md:468–470`; `src/manimcue/live_layers.py:306–329`). Transport wykonuje komendy FIFO (`src/manimcue/live_transport.py:170`, `:232–233`), a dowolna oczekująca komenda przerywa zwykłe cue (`:264–266`).

   **Konsekwencja:** po potwierdzeniu checkpointu można ręcznie zmienić scenę przed `enter`. Wejście zagra wtedy z innego stanu niż zapisany; replay nie powtórzy pierwotnego przebiegu. Podobny wyścig występuje między zwolnieniem bariery a obsłużeniem `enter` przez worker.

   **Poprawka planu:** zdefiniować okres rezerwacji sceny: od przyjęcia checkpoint/restore do przyjęcia `enter`, także podczas oczekiwania w pauzie. Określić kolejność już zakolejkowanych komend i odrzucanie nowych. Dodać testy przez router klawiatury, również przy fokusie live: `R`, potem `→`/`←`, pauza i wznowienie.

3. **[KRYTYCZNE] Nie wiadomo, jak potwierdzać granice operacji anulowanego wejścia.**

   **Dowód:** `PLAN.md:810–813` wymaga odebrania, wstawienia do warstwy i potwierdzenia każdej granicy. Jednocześnie tylko najnowsze wejście może zmieniać bieżący stan interfejsu (`:825–830`). Worker blokuje się na `frame_seen` i po 2 s kończy błędem (`src/manimcue/live_transport.py:240–246`). Obecnie ACK jest automatycznie zamawiany już w `try_read_frame()`, przed wstawieniem obrazu (`src/manimcue/live_session.py:169–179`; `src/manimcue/live_layers.py:200–214`).

   **Konsekwencja:** dla szybkiego A→B→A odrzucenie starej granicy może zablokować worker, a jej wyświetlenie może pokazać stan B na A. Obecny automatyczny ACK nie realizuje opisanej kolejności „wstaw, potem potwierdź”.

   **Poprawka planu:** rozdzielić odbiór protokołu od prawa do kompozycji. Granice starej operacji w żywej generacji należy odebrać i potwierdzić bez wyświetlania; granicę aktualnej operacji wyświetlić przed ACK. Jawnie przypisać odpowiedzialność za ACK i przetestować status przed klatką oraz anulowanie między nimi.

4. **[WAŻNE] Nowa generacja ma nieokreśloną politykę pierwszego cue.**

   **Dowód:** `PLAN.md:765` daje świeży build bez cue dla `initial`; `:766` nakazuje cue dla `next`; `:775` kończy historię po przerwie, zmianie prezentacji lub błędzie. Obecny kontroler tworzy nowy proces, gdy nie może przejąć starego, lecz nadal zamawia cue na podstawie przyczyny `next/auto_next/skip_all` (`src/manimcue/live_layers.py:111–145`).

   **Konsekwencja:** wejście do kolejnej prezentacji, powrót po slajdzie bez panelu i wejście po ERROR mogą oznaczać „nowa sesja bez cue” albo „nowa sesja z cue celu”. Nie wiadomo też, czy replay tego pierwszego wejścia ma uruchomić cue, które przy inicjalizacji celowo pominięto.

   **Poprawka planu:** oddzielić przyczynę nawigacji od utworzenia generacji. Dopisać tabelę dla zimnego `next`, zimnego `previous/V`, przejścia między prezentacjami, wejścia po ERROR i replay lokalnego początku. Określić także zachowanie warstw bez `session_id`, które według D33 pozostają w D27 (`SPEC.md:599`).

5. **[WAŻNE] Po cofnięciu nie określono, kiedy przestaje istnieć przyszła gałąź.**

   **Dowód:** `PLAN.md:772` porzuca przyszłą gałąź dopiero przy ponownym wejściu do przodu. `:780–782` wymaga kolejnych cofnięć po kolejnych wpisach. `:855` chroni checkpoint bieżącego wejścia. Fallback po braku checkpointu pozostawia aktualny stan (`:860–865`), ale nie definiuje zmiany pozycji w historii.

   **Konsekwencja:** po C→B→A nie wiadomo, czy checkpointy B/C nadal są legalnymi celami restore i kandydatami do eksmisji. Po nieudanym C→B kolejne `←`, `R`, `→` mogą korzystać z historii, która nie odpowiada rzeczywistemu stanowi procesu.

   **Poprawka planu:** określić osobno bieżący wpis, stos poprzedników, odłączoną przyszłość i ważność checkpointów. Nieudany restore powinien jawnie oznaczać rozbieżność historii ze sceną. Dodać przebiegi `← ← →`, `R → V`, eksmisję wpisu pośredniego i dalszą nawigację po fallbacku.

6. **[WAŻNE] Deduplikacja i unieważnianie identyfikatorów nie tworzą jeszcze pełnego protokołu.**

   **Dowód:** `PLAN.md:787` wymaga unikalności `request_id` w generacji, ale `:800–802` ogranicza deduplikację do bieżącego wejścia. Komendy `:792–796` nie mają osobnego pola generacji ani wejścia; nie określono kodowania ich w tokenach. Nie zdefiniowano odpowiedzi na powtórny zapis istniejącego ID, powtórny drop ani spóźnione `enter` po porzuceniu gałęzi.

   **Konsekwencja:** stary `enter` może zostać potraktowany jako nowa operacja po usunięciu rejestru deduplikacji. Samo odcięcie callbacków w GUI nie zapobiega mutacji sceny przez worker.

   **Poprawka planu:** ustalić format identyfikatorów, zakres i czas przechowywania wyników oraz reguły dla usuniętych ID. Worker musi odrzucać operacje unieważnionych wejść. Podać konkretne maksymalne długości tokenów, linii i kolejki oraz sposób zamknięcia wejścia.

7. **[WAŻNE] Przywrócenie stanu autora pozostaje ograniczone nawet w CE; automatyczne `unsupported` nie jest wiarygodną gwarancją.**

   **Dowód:** CE kopiuje graf obiektów osiągalnych z list sceny i zachowuje referencje updaterów (`src/manimcue/live_scene_ce.py:63–78`); restore odtwarza słowniki tych obiektów, listy sceny i czas (`:80–88`). Nie zapisuje pól sceny autora. `PLAN.md:837–840` wyłącza zamknięcia, RNG i dowolne pola, ale mówi też o wykrywaniu nieobsługiwanej zawartości.

   **Konsekwencja:** updater odczytujący zmienione `self.phase`, licznik w zamknięciu albo zasób zewnętrzny może działać poprawnie technicznie, lecz po restore dawać inny wynik. Nie musi wystąpić wyjątek pozwalający zwrócić `unsupported`. D10 dodatkowo nie integruje pominiętego czasu updaterów (`SPEC.md:658`), więc przerwany i pełny przebieg mogą mieć różne końce.

   **Poprawka planu:** oprzeć gwarancję na jawnym korpusie i zasadach autorstwa, nie na obietnicy wykrywania wszystkich zależności. Oddzielić przywrócenie referencji updatera od przywrócenia jego zależności. Identyczny koniec replay wymaga tego samego sposobu przerwania albo cue deterministycznego względem stanu checkpointu.

8. **[WAŻNE] D28 wymaga osobnej reguły dla kamery GL podczas operacji stanu.**

   **Dowód:** `view` jest wykonywane natychmiast w `live_poll()`, poza kolejką cue (`src/manimcue/live_transport.py:234–235`). Kamera GL należy do snapshotu (`src/manimcue/live_scene.py:287–289`), a każda publikacja graniczna ustawia `live_view_home` (`:338–340`). CE ma `view` jako no-op (`SPEC.md:671–672`). Szkic blokuje ręczne cue, ale nie gesty kamery (`PLAN.md:825–826`).

   **Konsekwencja:** pan/zoom podczas snapshotu lub animowanego restore może zmienić obraz, zostać nadpisany albo zmienić późniejsze działanie resetu. Dodanie granic checkpointów zmienia także momenty zapamiętywania „home”.

   **Poprawka planu:** jawnie blokować gesty D28 przez okres operacji albo określić ich kolejność. Ustalić, czy checkpoint/restore aktualizuje home, i dodać test kamera→checkpoint→zmiana widoku→restore→reset. Zachować jawne ograniczenie CE.

9. **[WAŻNE] Limit pamięci pomija istotne grafy i nie ma wykonalnej definicji rezerwy.**

   **Dowód:** `PLAN.md:849–858` liczy snapshoty i historie oraz wymaga odmowy przed alokacją kopii. GL `undo()` tworzy dodatkowy snapshot w `redo_stack` (`.venv/Lib/site-packages/manimlib/scene/scene.py:669–672`). Animacja GL kopiuje targety (`src/manimcue/live_scene.py:259`); CE kopiuje stan początkowy animacji (`src/manimcue/live_scene_ce.py:99`) i słowniki podczas restore (`:82`).

   **Konsekwencja:** można utrzymać limit checkpointów, a przekroczyć budżet przez redo i kopie robocze. Rozmiaru dowolnego `deepcopy` nie da się bezpiecznie wywnioskować wyłącznie z rozmiaru bieżącego grafu; kod kopiowania klas może alokować dodatkowe dane.

   **Poprawka planu:** zdefiniować rachunek obejmujący aktywne undo/redo, snapshoty wejść i szczytowe kopie robocze, z deduplikacją wspólnych buforów. Ograniczyć rachunek do obsługiwanych typów. Bramka 4 h powinna najpierw wykazać konserwatywną rezerwę na korpusie, zanim zaakceptuje się liczbę 256 MiB.

10. **[WAŻNE] Bariera replay musi zastąpić obecną ścieżkę restartu, a nie tylko ją uzupełnić.**

    **Dowód:** obecny replay natychmiast wykonuje `setPosition(0)` i `play()` (`src/manimcue/slides/present/player.py:719–731`); klipy restartuje osobno (`src/manimcue/clip_layers.py:256–272`). Przy reverse `clips.enter()` jest pomijane (`player.py:499`). Szkic wymaga przygotowania wszystkich właściwych klatek przed startem (`PLAN.md:814–819`).

    **Konsekwencja:** dołożenie samego restore pozostawi bazę grającą przez 0,6 s przywracania. Pozostawienie istniejących callbacków startu może też przedwcześnie wysłać cue. Dotyczy to szczególnie `V` po `R`, replay w reverse i `auto_next/skip_all` po reverse.

    **Poprawka planu:** wymienić wszystkie ścieżki uruchomienia bazy i cue, które mają respektować nową barierę, oraz reset stanu pętli. Dodać ochronę przed callbackami starego odtwarzania podczas przygotowania. Samo „istniejący replay” nie definiuje już całej operacji.

11. **[DROBNE] Pasek nie rozróżnia jeszcze poprawnie początku, końca i braku wykonania.**

    **Dowód:** `PLAN.md:874` mówi ogólnie „przywrócono stan N”, choć previous przywraca stan pozostawiony na N, a replay jego początek. `:879` łączy błędy z „cue pominięte”, mimo że wysłane cue może być przerwane lub mieć nieznany wynik (`:802`, `:830`). Obecny widok nadal mapuje sesję READY na „gotowe” (`src/manimcue/slides/present/player.py:855`).

    **Konsekwencja:** komunikat może sugerować zgodność live z bieżącą bazą albo niewykonanie cue, które już częściowo zagrało. Dwusekundowy komunikat nie wystarcza do wyjaśnienia trwałej rozbieżności.

    **Poprawka planu:** użyć tekstów „przywrócono stan pozostawiony na N” i „przywrócono początek N”; oddzielić „niewysłane”, „przerwane” i „wynik nieznany”. Trwale pokazywać nieaktualność panelu i jej przyczynę, z priorytetem nad READY oraz zwykłymi komunikatami cue.

12. **[WAŻNE] Kryteria są częściowo sprzeczne, a budżet 16 h wymaga ponownej estymacji po pierwszej bramce.**

    **Dowód:** „dokładnie jedno cue na wejście/replay” (`PLAN.md:886–887`) nie uwzględnia `initial`, braku cue, anulowania i fallbacku. Kryterium animacji z klatką pośrednią (`:905`) nie wyłącza braku zgodnych widocznych węzłów. ≥10 prób (`:905–908`) daje słabą podstawę do interpretacji p95. Obecne testy nawigacji sprawdzają głównie wysłanie `"flip"` i brak `"back"` (`tests/test_persistent_live.py:199–232`); CE ponownie wykorzystuje te scenariusze (`tests/test_live_ce_player.py:53–66`). Budżet całego rozszerzenia to 16 h (`PLAN.md:919–921`).

    **Konsekwencja:** wykonawca może spełnić liczniki bez poprawnego stanu albo nie zaliczyć legalnego restore bez widocznej interpolacji. Największe niewiadome — GL, rachunek pamięci i anulowanie — pozostają skumulowane w krótkim budżecie.

    **Poprawka planu:** zastąpić ogólny licznik tabelą oczekiwanych operacji dla każdego scenariusza. Rozdzielić testy semantyki, pikseli i czasu; klatki pośredniej wymagać tylko dla odpowiedniej sceny. Po bramce snapshotów ponownie oszacować resztę. Bez utraty głównego celu można odroczyć retransmisje i rozbudowaną obsługę duplikatów, pozostawiając brak retransmisji, korelację oraz odrzucanie starych operacji. Ograniczyć gwarancję do jawnego korpusu paneli; nie wycinać izolacji generacji, ACK, fallbacku ani D3 bez zmiany decyzji.

**Werdykt:** nie przekazywałbym jeszcze 5g do implementacji jako zamkniętego kontraktu. Podstawowa semantyka A→B→A, reverse→normalny plik i pętli jest sensowna oraz uwzględnia rundę 16. Blokują przede wszystkim zbyt mocna obietnica snapshotów GL oraz brak pełnej reguły rezerwacji sceny, obsługi anulowanych granic i historii po fallbacku.

Przegląd był statyczny i read-only; niczego nie zmieniałem. Nie uruchamiałem testów ani pomiarów — wykonalność czasowa i pamięciowa pozostaje do wykazania.

## Runda 21 — codex, 2026-10-23: kontrakt F10 (player ImGui)

**Pytania:** Czy kontrakt zapewnia parytet PC z D44, wspólny kod z webem, poprawne przejścia/5g/ACK, dwa okna i brak zawieszeń? Czy zadania, bramki i budżet są wykonalne bez rozstrzygania architektury podczas portu?

**Co weszło:**

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

**Odpowiedź codex (bez zmian):**

**Werdykt: poprawić kontrakt przed przekazaniem 10a Haiku.** Kierunek ImGui ma potwierdzenie w PoC, ale PoC nie potwierdza jeszcze parytetu, protokołu 5g ani obsługi dwóch pełnoekranowych okien. Największe ryzyko to ponowne zablokowanie UI przez synchroniczne dekodowanie.

Przegląd read-only, bez implementacji. Sprawdziłem lokalne API imgui-bundle 1.93.0 i wykonałem małe próby kontekstu ImGui bez okna. Nie wykonywałem próby dwóch monitorów ani nowego pomiaru w prawdziwym oknie.

1. **[KRYTYCZNE] D43 faktycznie zmienia D17, mimo deklaracji „bez zmian”.**

   **Dowód:** `PLAN.md:1318` wprowadza wspólny zegar wyznaczający klatkę każdego dekodera. `SPEC.md:372` opisuje niezależne zegary wideo i zaakceptowany dryf. `CLAUDE.md:16` i `PLAN.md:1404` wyłączają zegar główny z zakresu.

   **Konsekwencja:** wykonawca dostaje sprzeczne wymagania. Nazwanie synchronizacji „skutkiem ubocznym” nie usuwa kosztu jej implementacji ani konieczności rozstrzygnięcia zachowania przy spóźnieniu.

   **Poprawka planu:** jawnie dopuścić wewnętrzny zegar prezentacji na PC jako zastąpienie ograniczenia D17, bez publicznego seeku i gwarancji synchronizacji live. Rozdzielić czas mediów, aktywny czas ruchu D30 i czas rzeczywisty Info.

2. **[KRYTYCZNE] Brakuje polityki spóźnienia dekodera; PoC może zagłodzić UI i ACK live.**

   **Dowód:** `experiments/f5i_imgui/sources_desktop.py:105` synchronicznie dekoduje kolejne klatki aż do celu w nieograniczonej pętli. `stage.py:197` aktualizuje źródła kolejno. `PLAN.md:1315` zakłada poll live raz na klatkę.

   **Konsekwencja:** po zastoju, przy wysokim `playback_rate` lub trudniejszym materiale każdy strumień nadrabia zaległości w wątku UI. Obsługa klawiszy i live czeka; deadline 2 s ACK nie jest zabezpieczeniem przed blokującym wywołaniem natywnym.

   **Poprawka planu:** określić budżet pracy źródła na tick, pomijanie spóźnionych klatek, priorytet poll/ACK oraz zachowanie po dużym opóźnieniu. Dodać test sztucznego zastoju i przeciążenia. Wyraźnie zapisać: jeden wątek aplikacji nie zapewnia responsywności blokującego dekodera. Jeśli wymagane są twarde granice reakcji, dopuścić osobny proces dekodowania.

3. **[WAŻNE] Formuła CFR nie wystarcza do obsługi wszystkich deklarowanych mediów.**

   **Dowód:** `sources_desktop.py:65` używa `average_rate`, `:66` zakłada dostępne `duration`, `:119` przelicza `frame.time` na indeks. `PLAN.md:1335` rozszerza źródła na obraz/GIF. `media.py:52` jawnie wyróżnia GIF i bazę statyczną.

   **Konsekwencja:** nie określono obsługi zmiennych opóźnień GIF, disposal, brakujących metadanych, przesuniętego początku PTS ani materiału VFR. Skalowanie przy konwersji RGBA nie oznacza tańszego dekodowania zakodowanego strumienia.

   **Poprawka planu:** ustalić zakres wejścia: CFR gwarantowane przez render, a pozostałe pliki walidowane albo odtwarzane według PTS. GIF odtwarzać według czasów poszczególnych klatek, z limitem pamięci. Osobno mierzyć decode, konwersję, upload i seek na granicy pętli. Reverse bazy czyta `rev_file` do przodu — nie wymaga dekodowania wstecz.

4. **[KRYTYCZNE] Bariera 5g wymaga gotowego obrazu przywróconego stanu, nie samego READY.**

   **Dowód:** `SPEC.md:698` wymaga korelacji żądań i klatek; status bez wskazanej klatki nie zwalnia bariery. `live_entry.py:169` czeka jednocześnie na zakończenie operacji i odebranie właściwej granicy. `live_layers.py:201` wysyła enter/release dopiero przy faktycznym starcie grupy.

   **Konsekwencja:** uproszczone `all(source.ready)` może uruchomić bazę przed zakończeniem restore. Dotyczy to także ciepłej sesji, replay, reverse i wejścia bez cue. Pauza musi zatrzymać start mediów i cue, ale pozwolić przygotować checkpoint.

   **Poprawka planu:** wpisać kolejność: przygotowanie pierwszych klatek → checkpoint/restore → skorelowana klatka graniczna → przyjęcie do kompozycji → ACK → gotowość grupy → faktyczny start i enter/release. Zachować wspólny deadline 5 s, unieważnianie poprzedniego wejścia i odcięcie niepewnego workera po timeout.

5. **[KRYTYCZNE] „ACK po narysowaniu” jest nieprecyzyjne i mocniejsze od obecnej implementacji.**

   **Dowód:** `live_layers.py:332` ustawia obraz kompozycji, a `:335` wysyła ACK przed późniejszym malowaniem Qt. PoC jest jeszcze wcześniejsze: `sources_desktop.py:171` wywołuje domyślne `try_read_frame()`, które potwierdza granicę w `live_session.py:181`, przed uploadem w `sources_desktop.py:180`.

   **Konsekwencja:** `add_image()` zapisuje komendę; nie oznacza wykonania renderera ani fizycznego wyświetlenia. Z kolei oczekiwanie na fizyczne wyświetlenie nie jest obecnym kontraktem D41.

   **Poprawka planu:** zdefiniować konkretny punkt ACK. Najmniejsza zgodna wersja: właściwa klatka została przyjęta do trwałego zasobu kompozycji, którego następny update nie zniszczy przed użyciem. Jeśli wymagany jest zakończony render, użyć udokumentowanego callbacku i przetestować jego kolejność także dla viewportów. Anulowane granice nadal potwierdzać bez kompozycji. API udostępnia `before_swap` i `after_swap` (`hello_imgui.pyi:1887`, `:1901`), ale swap nie jest dowodem fizycznego wyświetlenia.

6. **[KRYTYCZNE] Multi-viewport nie dowodzi obsługi dwóch pełnoekranowych okien na wskazanych monitorach.**

   **Dowód:** PoC tylko włącza `enable_viewports` (`stage.py:40`) i tworzy zwykłe `begin("Info")` (`:220`). `hello_imgui.pyi:1137` i `:1149` opisują monitor i fullscreen okna aplikacji; `:2433` udostępnia wskaźnik głównego okna GLFW. Obecne `Player.full_screen()` przełącza **oba** okna (`player.py:756`).

   **Konsekwencja:** możliwość ręcznego wyciągnięcia Info nie zapewnia programowego utworzenia osobnego viewportu, wskazania monitora, przełączania obu okien i odtworzenia ich geometrii. Parametry głównego okna nie są automatycznie parametrami Info.

   **Poprawka planu:** przed portem zrobić małą bramkę Windows: dwa monitory, osobne Info od startu, F w obie strony, różne DPI, zachowanie po zmianie fokusu. Nazwać używane API dla viewportu Info i zdecydować fullscreen bez ramek czy wyłączny. GLFW ma operacje per okno, lecz trzeba uzyskać właściwe uchwyty i uwzględnić automatyczne minimalizowanie fullscreen po utracie fokusu. [Dokumentacja GLFW](https://www.glfw.org/docs/latest/window).

7. **[WAŻNE] PyOpenGL, kursor i vsync są wykonalne, ale kontrakt pomija warunki ich poprawności.**

   **Dowód:** tekstury PoC powstają w `post_init` (`desktop.py:100`), a ustawienia wybierają jedynie vsync (`stage.py:45`), bez jawnego wyboru backendu renderującego. `hello_imgui.pyi:2679` udostępnia wybór backendów; `imgui/__init__.pyi:3003` udostępnia `set_mouse_cursor`.

   **Konsekwencja:** PyOpenGL wymaga bieżącego kontekstu OpenGL. Przy kilku viewportach trzeba kontrolować kontekst, współdzielenie tekstur i ich usuwanie. Ukrycie kursora jest stanem ustawianym przez backend, a vsync nie jest twardą gwarancją częstotliwości.

   **Poprawka planu:** przypiąć GLFW + OpenGL3, określić callbacki uploadu i zwalniania zasobów, testować oba viewporty. Doprecyzować zakres H — obecny Qt ukrywa kursor głównego okna (`player.py:765`). Mierzyć realny odstęp swapów; ustawienie flagi nie wystarcza. [Kontekst GLFW](https://www.glfw.org/docs/latest/context_guide.html).

8. **[WAŻNE] Mapowanie klawiszy już istnieje, lecz nie usuwa zależności konfiguracji od Qt.**

   **Dowód:** istnieją `src/manimcue/player/keys.py:46` i `tests/test_player_keys.py:13`. Natomiast domyślne `Keys()` wywołuje `key_id()` importujące Qt (`slides/config.py:53`, `:92`). Wizard zapisuje wynik `event.key()` (`wizard.py:41`, `:123`), a TOML przechowuje liczbowe `ids` (`config.py:86`, `:176`).

   **Konsekwencja:** sam adapter wejścia ImGui nie pozwala tworzyć domyślnej konfiguracji bez Qt. Nieznany identyfikator nie musi mieć dostępnej nazwy. Ponadto Qt `Key_Plus` nie oznacza wyłącznie klawisza numerycznego, a obecna tabela mapuje go na `keypad_add` (`player/keys.py:83`); analogicznie `Asterisk`.

   **Poprawka planu:** wykorzystać istniejący moduł, przenieść tworzenie domyślnych kodów na stałe bez importu Qt i zachować zgodność liczbowego TOML. Zdefiniować mapowania wielokrotne dla klawiszy zależnych od modyfikatorów/układu. Błąd musi zawierać akcję, kod dziesiętny i hex; nazwę tylko gdy znana. Testować również routing i autorepeat, nie tylko istnienie enumów.

9. **[WAŻNE] Lista funkcji nie zastępuje tabeli przejść nawigacji.**

   **Dowód:** `player.py:678` rozróżnia next w przygotowaniu, pauzie i nad bazą statyczną. `:568` rozróżnia reverse → normalny plik tego samego slajdu. `:720` ignoruje replay podczas przygotowania. `:365` kończy zamówioną pętlę na końcu iteracji, opcjonalnie przechodząc dalej.

   **Konsekwencja:** implementacja „next/previous/replay/reverse/pauza” może formalnie spełnić listę i zmienić zachowanie prezentacji.

   **Poprawka planu:** dodać tabelę stan × akcja × wynik, obejmującą:

   - next w pauzie: wznowienie przed przejściem dalej;
   - next podczas przygotowania: zamówienie startu albo kolejne wejście;
   - zamówienie wyjścia z pętli, końcową klatkę i `auto_next`;
   - koniec bazy: zatrzymanie klipów i ruchu, ale nie live;
   - reverse → normalny ten sam slajd bez nowego wejścia live;
   - granice prezentacji, brak poprzedniego/następnego, replay i flagi zakończenia;
   - `skip_all` wymuszające pojedyncze odtworzenie oraz wyjście.

10. **[WAŻNE] Parytet CLI i Info nie ma kompletnego inwentarza odbiorowego.**

    **Dowód:** pełne CLI znajduje się w `slides/present/__init__.py:130`; domyślne ukrywanie Info na jednym monitorze w `:324`, wybór scen bez argumentów w `:43`, powtarzanie tej samej prezentacji w `:269`. Info ma czas lokalny i czas od uruchomienia (`player.py:69`), wspólny bieżący obraz (`:59`) i przekazywanie klawiatury (`:175`).

    **Konsekwencja:** łatwo zachować nazwy opcji, ale zgubić aliasy, wartości ujemne startu, domyślne rozmieszczenie okien, zmianę rozdzielczości między prezentacjami albo sterowanie z Info.

    **Poprawka planu:** załączyć macierz wszystkich opcji i dziewięciu akcji `Config.keys`, z odnośnikiem do testu. Uwzględnić `--full-screen` i aliasy, folder/config/verbosity, wybór scen, ujemne indeksy, powtórzone sceny, niepoprawny monitor, zamykanie obu okien i niezależność zegara Info od pauzy. Błędu upstreamu z traktowaniem zera w `start_at` (`present/__init__.py:297`) nie utrwalać bez świadomej decyzji.

11. **[WAŻNE] 5c i 5g wymagają pełnego modelu komunikatów, nie ogólnego „stan prelegenta”.**

    **Dowód:** `player.py:837` opisuje przygotowanie, zamówiony start, koniec, kierunek, pętlę, fokus, problemy klipów i operacje historii. `:904` wygasza komunikat po 2 s z ochroną rewizji. `SPEC.md:704` wymaga trwałej degradacji ponad READY.

    **Konsekwencja:** samo „ready/error” ukryje różnicę między gotowym stanem a niewysłanym cue, oczekiwaniem na koniec pętli i nieudanym restore. Stary timer może skasować nowszy komunikat.

    **Poprawka planu:** zrobić jeden model snapshotu dla Info i nakładki S. Przepisać przypadki z `tests/test_presenter_state.py:237` i `tests/test_live_checkpoint.py:515`, wraz z komunikatami granic nawigacji, blokady komend i degradacji.

12. **[WAŻNE] Podgląd w PoC ma inną semantykę niż 5d; ruch jest dodatkową funkcją.**

    **Dowód:** `stage.py:131` dołącza podgląd do źródeł wspólnej bariery i pauzy. `SPEC.md:640` wymaga niezależnych, wyciszonych pętli bez bariery głównej, z `rect_at(0)`. `PLAN.md:1345` dodaje ruch.

    **Konsekwencja:** wolny podgląd może opóźnić slajd, a pauza główna zatrzymać podgląd. Dla nowego ruchu nie wiadomo, czy czas resetuje pętla bazy, każdy klip osobno, czy zmiana podglądu.

    **Poprawka planu:** oddzielić grupę główną od podglądu. Zachować normalny kierunek, niezależne pętle i szybkości, miniatury live, brak dekoderów przy ukrytym Info oraz poprawne czyszczenie ostatniego podglądu. Ruch wyciąć z 10a — to rozszerzenie, nie parytet. Zachować test przejścia między prezentacjami o różnych rozdzielczościach (`test_preview_alpha_border.py:293`).

13. **[WAŻNE] D34, alfa i obwódki potrzebują kontraktu współrzędnych oraz wejścia.**

    **Dowód:** PoC ma stałe 16:9 (`stage.py:22`), czarne wypełnienie (`:161`) i obwódkę 3 px (`:173`). Qt ogranicza szerokość obwódki rozmiarem kontenera i rysuje ją wewnątrz (`live_layers.py:435`). `composition.py:246` trafia w najwyższy **kontener**, także jego przezroczysty margines. `SPEC.md:646` określa mnożenie alfy i priorytet ról.

    **Konsekwencja:** można uzyskać poprawne prostokąty i błędne kliknięcia, grubość zależną od DPI albo podwójne dopasowanie live. Pasy live są już w buforze workera; nie wolno dopasowywać go ponownie według proporcji wewnętrznej sceny.

    **Poprawka planu:** rozdzielić kadr decku, kontener warstwy, obraz wewnątrz kontenera i współrzędne viewportu. Zdefiniować clipping warstw wychodzących poza kadr, skalowanie `BorderStyle.width`, `None` bez utraty fokusu, priorytet aktywna/błąd i zachowanie alfy zachowanej klatki. Kolor pasów workera odróżnić od zewnętrznego tła playera. Testy pikselowe są tu konieczne.

14. **[KRYTYCZNE] „Przeniesienie `live_layers.py` 1:1” nie jest zadaniem o jasnych granicach.**

    **Dowód:** `live_layers.py:12` importuje QObject, sygnały, QTimer, QImage i QGraphics; `:322` zarządza życiem bajtów obrazu; `:387` korzysta z QPointF i geometrii kompozycji; `:443` przyjmuje QKeyEvent.

    **Konsekwencja:** mechaniczne przepisywanie jednocześnie zmieni protokół, przechowywanie obrazu, harmonogram i wejście. To szczególnie ryzykowne zadanie dla Haiku.

    **Poprawka planu:** Claude powinien sam ustalić i zrecenzować kontroler live: wejścia zdarzeń, przejścia historii, efekty transportowe, korelację granic i shutdown. Haiku może osobno dostarczyć adapter tekstur i adapter wejścia. Zachować `EntryHistory` i transport; nie przepisywać ich razem z UI. Zamykanie pozostać dwufazowe (`live_layers.py:472`, `:483`), ze zwolnieniem tekstur przed zniszczeniem kontekstu.

15. **[WAŻNE] Fokus D20 i gesty D28 nie wynikają automatycznie z wejścia ImGui.**

    **Dowód:** `live_layers.py:443` konsumuje autorepeat next/back bez wysyłania, pozwalając innym akcjom przejść do playera. `:462` blokuje cue/view podczas rezerwacji. `SPEC.md:541` traktuje oba okna jako jeden obszar aktywności. Gesty normalizują ruch przez rozmiar kontenera (`live_layers.py:393`).

    **Konsekwencja:** standardowa nawigacja ImGui może przejąć strzałki, a focus pojedynczego okna zwolnić live przy przejściu do Info. Złe współrzędne dadzą inną czułość kamery w podglądzie, przy DPI i letterboxie.

    **Poprawka planu:** określić kolejność routera, repeat, obsługę tekstu/Markdown, klik poza live, marginesy blokujące klik, drag z Shiftem, wheel i double-click. Fokus aplikacji agregować po wszystkich jej oknach. D28 dla CE pozostaje no-op zgodnie z `SPEC.md:673`.

16. **[WAŻNE] Test `ImDrawList` bez renderera jest wykonalny, ale opis pomija protokół tekstur 1.92.**

    **Dowód:** w lokalnym 1.93.0 `fonts.build()` i `get_tex_data_as_rgba32()` są nieobecne. Zwykłe `new_frame()` zgłasza asercję niezbudowanego atlasu. API udostępnia `renderer_has_textures` (`imgui/__init__.pyi:4490`) oraz `ImTextureData.set_tex_id/set_status` (`:11140`).

    **Konsekwencja:** fixture oparta na starszych poradnikach ImGui nie ruszy. Sam draw list nie dowodzi poprawności blendowania ani wykonania OpenGL.

    **Poprawka planu:** wpisać sprawdzoną fixture: kontekst, rozmiar, delta, wyłączony ini, minimalna atrapa protokołu tworzenia/aktualizacji tekstur i kontrolowana geometria okna. Próba lokalna uzyskała komendy z testową teksturą `123`. Sprawdzać bufory wierzchołków/indeksów, UV i clip rect; komendy bywają scalane. Alfę, DPI i backend weryfikować osobno w prawdziwym oknie.

17. **[WAŻNE] „Te same testy logiki w Pyodide” nie ma obecnie wykonalnej definicji.**

    **Dowód:** `PLAN.md:1386` obejmuje te same testy co 10a, a `:1351` zalicza do logiki także live. Obecne scenariusze playera używają qapp, workerów i subprocessów, np. `tests/test_live_checkpoint.py:84`. Model importuje natywne `rtoml` i Pydantic (`config.py:14`); media importują PyAV (`media.py:10`).

    **Konsekwencja:** pominięcie trzech plików platformowych nie zapewnia przenośności całego drzewa importów. W Pyodide nie uruchomią się lokalne workery multiprocessing ani obecne testy Qt. [Ograniczenia Pyodide](https://pyodide.org/en/latest/usage/wasm-constraints.html).

    **Poprawka planu:** zdefiniować wspólny, nazwany zestaw testów czystego kontrolera, zegara i geometrii z atrapami źródeł. Integracje live pozostają desktopowe. Dodać bramkę importów w Pyodide już na początku 10a i określić format danych dostarczanych przeglądarce. Przeglądarka może otrzymywać zwalidowany manifest; nie musi importować całego modelu i CLI.

18. **[WAŻNE] Drugie okno webowe wymaga protokołu repliki, nie tylko BroadcastChannel.**

    **Dowód:** `PLAN.md:1359` wymienia indeks, zegar i pauzę. Obecne bieżące Info współdzieli kompozycję (`composition.py:3`), natomiast druga strona ma osobny interpreter, dekodery i zegar. PoC mierzy jedno płótno.

    **Konsekwencja:** brakuje synchronizacji reverse, replay tego samego indeksu, granic pętli, przygotowania, zmiany decku i ponownego otwarcia Info. Dwa sterujące egzemplarze mogą wykonać akcję dwukrotnie. Bieżący obraz w Info będzie osobnym odtworzeniem, więc nie ma dotychczasowej gwarancji identycznego obrazu.

    **Poprawka planu:** jedno okno autorytatywne, drugie jako replika/prezenter. Snapshot początkowy, numer rewizji i generacji wejścia, jawne komendy, handshake po ponownym otwarciu, lokalne kotwice czasu i tolerancja dryfu. Zdefiniować zachowanie po throttlingu/minimalizacji i zamknięciu głównego okna. Pomiar wykonać z rzeczywiście otwartą drugą stroną.

19. **[WAŻNE] D44 jest świadomym wyjątkiem od parytetu; webowe audio nie jest jeszcze zweryfikowane.**

    **Dowód:** `PLAN.md:1322` jawnie dopuszcza brak audio na PC. PoC web wycisza każde wideo (`sources_web.py:29`), ignoruje Promise `play()` (`:65`), a launcher dodaje obejście autoplay (`serve.py:123`).

    **Konsekwencja:** wynik PoC nie potwierdza startu bazy z dźwiękiem w zwykłych warunkach. Odmowa autoplay może rozjechać stan „gra” z faktycznym odtwarzaniem. Drugie okno może zdublować audio.

    **Poprawka planu:** nazwać 10a „parytet z uzgodnionym wyjątkiem audio”. Ostrzegać raz na materiał z audio, pozostawić Qt jako ścieżkę dźwiękową. W webie odblokowanie przez gest, obsługa odrzuconego Promise i wspólnego startu dopiero po sukcesie. Tylko główna baza emituje audio; Info i klipy są wyciszone. Uwzględnić odrzucenie fullscreen/popup i Esc przeglądarki. [Aktywacja użytkownika](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/User_activation).

20. **[WAŻNE] `--offline` jest realny, ale cache dwóch artefaktów nie wystarczy.**

    **Dowód:** `web/index.html:7` pobiera loader z CDN, `:38` ładuje micropip/numpy, `:39` instaluje pakiet po nazwie z PyPI. `PLAN.md:1361` wymienia jedynie Pyodide i koło imgui-bundle.

    **Konsekwencja:** częściowo rozgrzany cache może zamaskować brak runtime WASM, biblioteki standardowej, lockfile, zależności lub zasobów fontów. Koło Windows z uv nie zastępuje koła Emscripten.

    **Poprawka planu:** przygotowywać przypięty lokalny zestaw runtime i całego domknięcia zależności, z manifestem i sumami. Instalować przez lokalne URL, bez niejawnego wyszukiwania w PyPI; `deps=False` wyłącznie po przygotowaniu zależności. Testować świeży profil, pusty cache HTTP i zablokowany ruch poza loopback. [Ładowanie pakietów Pyodide](https://pyodide.org/en/latest/usage/loading-packages.html).

21. **[WAŻNE] Jednowątkowy serwer PoC blokuje inne żądania i nie realizuje pełnego Range.**

    **Dowód:** `serve.py:64` czyta cały plik przed odpowiedzią, `:82` wykonuje blokujące `wfile.write`, a `:106` używa `HTTPServer`. Parser Range w `:66` nie obsługuje poprawnie granic i odpowiedzi 416.

    **Konsekwencja:** obsługa dużego filmu może zatrzymać dostarczanie innych strumieni i bootstrap drugiego okna. Pamięć rośnie z rozmiarem pliku, mimo że klient żąda małego fragmentu.

    **Poprawka planu:** zachować jeden wątek przez serwer asynchroniczny, z porcjowaniem plików i przerwami na inne połączenia. Zapisać obsługiwany zakres HTTP: GET/HEAD, poprawne 206/416, ograniczanie końca zakresu i allowlista plików manifestu. Nie przenosić handlera PoC jako gotowej implementacji.

22. **[WAŻNE] Kryteria pomiaru nie definiują jednoznacznie sukcesu.**

    **Dowód:** `PLAN.md:1379` mówi o „medianie każdego strumienia ≥55 kl./s”, bez okien agregacji i czasu próby. PoC liczy średnie uploady na całe okno (`stage.py:78`). `desktop-vsync-n3.json:5` ma render 208 fps mimo nazwy „vsync”; README wyjaśnia zablokowany ekran (`README.md:39`). Webowy `clip_2` ma 48,09 fps i 244/1379 odrzuconych klatek (`web-headless-n3.json:32`).

    **Konsekwencja:** PoC nie zalicza proponowanych kryteriów okienkowych. Łączne ~9% strat ukrywa znacznie gorszy pojedynczy strumień. „Zrzut zgodny w tolerancji” również nie ma ustalonej tolerancji.

    **Poprawka planu:** podać sprzęt, odświeżanie, rozgrzewkę, długość i liczbę powtórzeń; minimalny wynik każdego strumienia, delty liczników w tym samym oknie, p95/max ciszy i opóźnienie wejścia. Dodać zewnętrzny watchdog, serię zmian slajdów i pętli oraz dłuższą próbę stabilności. Testy Windows muszą obejmować dwa monitory, vsync, live GL/CE i przełączanie aplikacji. Zrzuty porównywać na kontrolowanych chwilach przez maski/geometrię, z liczbowymi tolerancjami.

23. **[WAŻNE] Budżet nie uwzględnia bramek technicznych i iteracji mniejszego modelu.**

    **Dowód:** `PLAN.md:1394` przeznacza 30 h na całość 10a, w tym 8 h na kontroler live i 4 h na okna. Tymczasem brak jeszcze potwierdzenia najtrudniejszych właściwości okien, określenia polityki dekodowania i wydzielonego zestawu testów.

    **Konsekwencja:** Haiku będzie rozstrzygać architekturę podczas implementacji. Limit 60 h stanie się momentem zatrzymania częściowego portu, a nie kontrolą przewidywalnego zakresu.

    **Poprawka planu:** estymować po bramkach technicznych. Nie podawałbym 30 h jako wiarygodnego budżetu parytetu; orientacyjnie rezerwowałbym **50–80 h łącznej pracy implementacji, przeglądu i prób**, z ponowną estymacją po pierwszych zadaniach. To ocena ryzyka, nie wynik pomiaru. Osobno rozliczać pracę Haiku i Claude oraz oczekiwanie na próbę człowieka.

Proponowany podział 10a dla Haiku, wykonywany kolejno:

| Zadanie | Wejście → wynik | Warunek odbioru |
|---|---|---|
| 0. Kontrakt — **Claude** | Obecny player i testy → macierz parytetu, przejść, wyjątków i portów platformowych | Rozstrzygnięte punkty 1–5, 9–12 |
| 1. Bramka Windows | Mała aplikacja hello_imgui → dwa okna, monitory, F/H, jawny OpenGL3 | Próba dwóch monitorów, DPI i przechodzenia do Info; bez reszty playera |
| 2. Bramka wspólnego kodu | Minimalny manifest → import kontrolera na PC i w Pyodide | Bez Qt/PyAV/multiprocessing w wspólnym drzewie importów |
| 3. Klawisze i konfiguracja | Istniejące `keys.py`, TOML → adapter bez Qt | Domyślne, własne, nieznane, repeat i klawisze modyfikowane |
| 4. Kontroler nawigacji | Tabela przejść, sztuczny zegar → czysty model stanu i efektów | Test każdej pozycji tabeli; żadnych okien i dekoderów |
| 5. Źródła PC | Ustalony protokół źródła → obraz, GIF, CFR, reset, pętla, EOF | Małe materiały z identyfikowalnymi klatkami; błędy i opóźnienia |
| 6. Kompozycja | Manifest i gotowe tekstury → geometria, clipping, alfa, obwódki | Fixture tekstur 1.92 + obrazy z prawdziwego renderera |
| 7. Live — **Claude** | `EntryHistory`, LiveSession, kontrakt bariery → kontroler bez Qt | Port scenariuszy 5g, stale granice, timeout, rezerwacja, shutdown |
| 8. Adapter wejścia live | Zdarzenia ImGui → klik/fokus/gesty/komendy kontrolera | D20/D28, Info, marginesy, repeat, rezerwacja |
| 9. Info i podgląd | Snapshot stanu, osobne źródła preview → wspólny bieżący obraz i niezależny podgląd | 5c/5d, ukryte Info bez dekoderów, przejście między deckami |
| 10. Integracja CLI | Gotowe moduły → `--player imgui`, Qt nadal domyślny | Macierz CLI i brak regresji Qt |
| 11. Odbiór — **Claude + człowiek** | Gotowy player → raport obrazu, wydajności i stabilności | Pełne testy, prawdziwe okna, dwa monitory, próba człowieka |

Każde zadanie powinno mieć zamkniętą listę plików, sygnatury wejść/wyjść, konkretne testy i zakaz zmiany semantyki bez powrotu do Claude. Kontrolera live nie oddawałbym Haiku jako „portu 1:1”.

Z 10a można wyciąć bez utraty celu: **ruch podglądu**, eksperymenty `hwaccel`, adaptacyjne skalowanie dekodowanych tekstur i implementację audio inną niż uzgodnione ostrzeżenie. 10c pozostawić poza zakresem. Nie wycinać testów bariery, shutdown, dwóch okien ani polityki przeciążenia — one bezpośrednio chronią cel „brak zawieszeń”.

**Werdykt końcowy: kierunek zaakceptować, kontrakt odesłać do poprawy. Najpierw bramki Windows/Pyodide oraz precyzyjny kontrakt zegara i live, potem małe zadania Haiku.**

## Runda 22 — codex, 2026-10-23: kontrakt 10d po próbie prelegenta

**Przedmiot:** niezacommitowany kontrakt „10d — poprawki po próbie prelegenta” w PLAN.md i D45–D47 w SPEC.md; zgodność z kodem i zamkniętym zakresem przyszłych zadań. Claude uruchomił `codex exec -s read-only`; recenzja statyczna diffu i kodu, bez zmian implementacji i testów GPU.

**Ustalenia i rozstrzygnięcia:**

1. **[BLOKUJĄCE] Krok uruchamiający LOOPS może blokować następny press.** Przyjęto rozdzielenie kroku wykonywanego i jednego oczekującego FIFO. Drugi fizyczny press po key-up dociera do workera i domyka/przerywa pierwszy według D9/D10; repeat nadal konsumowany. Dodano odbiór `step → cue zapętlone → key-up → step` w zadaniu 1.
2. **[ISTOTNE] Protokół nie wskazuje początku timeoutu pętli.** Przyjęto skorelowane STEP_STATUS waiting/running/looping, deadline’y przyjęcia, oczekiwania, wykonania i ACK oraz watchdog statusów pętli. Powtarzanie może trwać ponad 5 s, ale brak statusów lub wyniku po domknięciu zatrzymuje niepewną sesję według D41 i utrwala degradację bez skoku. Dodano test długiego powtórzenia i braku postępu po jego zakończeniu; CUE_DONE nie steruje deadline’em.
3. **[BLOKUJĄCE] Zakres pomija odcięcie historii po miniaturze.** Przyjęto p/live.py i m/live_entry.py w zadaniu 2: odcięcie stosu EntryHistory, starych oczekiwań i checkpointów, nowy has_predecessor=False. Zachowany socket nie resetuje generacji ani monotonicznych liczników; nowe entry_id odrzuca późne statusy/wyniki/ACK. Odbiór obejmuje miniaturę podczas restore, późne statusy i previous/V/R bez starej historii.
4. **[ISTOTNE] Zakres pomija reducer start_at.** Przyjęto p/controller.py w zadaniu 2 i no-op bieżącego celu po normalizacji indeksu, przed _enter(). Test sprawdza niezmienione entry_id, pauzę, reverse, trwające przygotowanie i brak efektów.
5. **[ISTOTNE] Globalny limit czterech procesów przeczy puli i odbiorowi preview.** Przyjęto niezależny limit jednego procesu ekstrakcji miniatur, obejmujący kończenie do potwierdzonego exit. Pula czterech oznacza bezczynny ciepły zapas, uzupełniany po pobraniu; proces obsługuje jedno źródło do końca życia. Osobno liczyć aktywne scena/preview/miniatura, bezczynne i kończące się oraz sumę żywych. Odbiór zadań 3 i 6 obejmuje bazę+3 klipy+ruchome preview+miniatury i anulowanie; zadanie 3 przeszacowano 4 → 6 h, etap 31 → 33 h, stop 62 → 66 h. Bez globalnego schedulera.

**Co weszło:** wszystkie pięć ustaleń do PLAN.md/SPEC.md; usunięto nieaktualną uwagę o blokadzie recenzji przez sieć. W akapicie „Stan poprawek Claude” odnotowano przekazany stan show_at/slotów, wyboru klatki bez zapisu w toku, ponownego glTexImage2D i bezczynnej puli; nie jest to nowy zakres projektowania ani zaliczenie odbioru.

**Weryfikacja:** spójność dokumentów i diff; bez zmian src/, tests/, experiments/, bez uruchamiania testów GPU i bez commita. Testy wymienione w kontrakcie są planowane, nie zaliczone.

**Werdykt:** ustalenia rozstrzygnięte w kontrakcie; przed implementacją przegląd Claude poprawionego kontraktu, odbiór wykonania pozostaje otwarty.

## Runda 23 — codex, 2026-10-23: kontrola rundy 22

**Przedmiot:** kontrola rundy 22 — niezacommitowany kontrakt 10d w PLAN.md i D45–D47 w SPEC.md. Claude uruchomił `codex exec -s read-only`.

**Ustalenie i rozstrzygnięcie:**

1. **[ISTOTNE] Timeout przerywa poprawne długie cue.** Running wymagał wyniku w 5 s, choć zwykłe cue nie mają limitu długości; `MeasurePanel2D.motion` trwa 35 s (`tests/scenes/live_ce_extra.py:128`). NEXT zatrzymałby zdrowego workera i utrwalił degradację. Przyjęto skorelowany heartbeat running/looping co ≤1 s, wyłącznie przy potwierdzonym postępie wykonania (także wait), oraz watchdog 5 s braku postępu zamiast limitu całego cue. Waiting odnawia tylko potwierdzony postęp poprzednika; żywy transport nie wystarcza. Od żądania przerwania/domknięcia pozostaje nieodnawialny deadline 5 s na wynik, także przy dalszych heartbeat; ACK 2 s. Do zadania 1 dodano test zwykłego cue >5 s i zatrzymania jego postępu oraz deadline’u przerwania mimo heartbeat.

**Weryfikacja:** spójność PLAN.md/SPEC.md i diff; bez zmian implementacji, testów ani eksperymentów, bez uruchamiania testów GPU i bez commita. Testy zadania 1 pozostają planowane.

**Werdykt:** ustalenie przyjęte i rozstrzygnięte w kontrakcie; odbiór implementacji pozostaje otwarty.

## Runda 24 — codex, 2026-10-23: kontrakt D48

**Przedmiot:** niezacommitowany D48 w SPEC.md i zadania 6–8 etapu 10d w PLAN.md. Claude uruchomił `codex exec -s read-only`; recenzja statyczna, bez testów i okna.

**Ustalenia i rozstrzygnięcia:**

1. **[BLOKUJĄCE] Hold bez wyjścia dla zwykłego live bez cue.** Przyjęto jawne adopt_prefetch skorelowane session/generation/entry_id/request_id także bez session_id: granica wejścia, kompozycja/ACK i release w D31 z zachowaniem pauzy. Bez sztucznego cue/historii. Dodano planowany test GL/CE: next bez session_id/cue oraz wejście podczas pauzy.
2. **[ISTOTNE] Pierwsza granica prefetcha wygasa przed next.** Przyjęto techniczny ACK READY w 2 s, osobny od granicy wejścia D41 z nowym frame_id i ACK po kompozycji. Deadline spekulacji 5 s kończy się po przygotowaniu z technicznym ACK; gotowy cel czeka do przyjęcia/anulowania. Dodano test GL/CE: hold >5 s, następnie checkpoint/kompozycja/ACK właściwego wejścia.
3. **[ISTOTNE] Lista plików pomija właściciela decku Qt.** Dodano m/slides/present/player.py do zadania 6: konfiguracja silników całego decku, poll także bez live, zamykanie zapasu po zmianie decku i końcowy shutdown. Dodano test offscreen decku zaczynającego się slajdem plikowym.
4. **[ISTOTNE] Admisja nie określa bezpiecznego oczekiwania.** Przyjęto take → worker albo None i waiting_slot pompowany przez poll dla LiveSession i Source, bez blokowania GUI i spawnu poza B. Deadline od nawigacji obejmuje czekanie; nowe entry_id anuluje stare żądanie, prefetch wiąże token. Dodano testy pełnego B, opóźnionego exit i ponownej nawigacji.

**Budżet:** zadanie 6: 8 → 10 h (Qt/admisja), zadanie 7: 9 → 11 h (hold/ACK/Source); 10d: 50 → 54 h, stop 100 → 108 h, nadal 2× zadania. Zadanie 8 bez zmiany budżetu. Bootstrap Lock/Pipe przy spawn, późniejsze LiveSpec/SHM i decyzja pula → prefetch pozostają przyjęte.

**Weryfikacja:** spójność dokumentów i diff; zmieniono wyłącznie PLAN.md, SPEC.md i REVIEW-LOG.md, bez implementacji, uruchamiania testów ani commita. Testy są planowane, nie zaliczone.

**Werdykt:** wszystkie cztery ustalenia przyjęte i rozstrzygnięte w kontrakcie; odbiór implementacji pozostaje otwarty.

## Runda 25 — codex, 2026-10-23: kontrola rundy 24

**Przedmiot:** niezacommitowany diff PLAN.md/SPEC.md/REVIEW-LOG.md — etap 10d z zadaniami D48 i wpis rundy 24.
Claude uruchomił `codex exec -s read-only`: czy każde z 4 ustaleń rundy 24 jest rozwiązane, czy poprawki
nie wprowadziły sprzeczności z kodem i D9/D10/D20/D28/D31/D39–D48, spójność list plików i budżetu.

**Wynik:** brak blokujących; brak dalszych ustaleń.

**Werdykt:** kontrakt 10d (D45–D48, budżet 54 h, stop 108 h) zamknięty rundami 22–25; implementacja codex
zadaniami po kolei, przegląd Claude i próba człowieka.

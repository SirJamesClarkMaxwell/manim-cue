# manim-cue — plan rozwoju

Stan (2026-10-22): **fazy 0, 1 i 2 zamknięte. Aktywna: faza 3.** Kierunek zmieniony 2026-10-21 decyzjami D13-D19 w `SPEC.md`:
projekt staje się forkiem manim-slides 5.7.0, rozszerzonym o warstwy i wstrzykiwany live.
Rundy 6-7 recenzji (codex) przebudowały fazy 2-9; decyzje D20-D22.

## Wizja (prelegent, 2026-10-21)

1. Fork manim-slides z rozszerzoną funkcjonalnością.
2. Scena jako obiekt w innej scenie: wyzwalanie jej animacji, przesuwanie finalnego renderu.
3. Notatki prelegenta i podgląd następnego slajdu.
4. Domyślnie prerender, z możliwością wstrzyknięcia sceny interaktywnej.
5. Silniki w kolejności: Manim CE, manimgl, manimgx.

**Co z tego już istnieje:**
- (3) okno Info manim-slides 5.7.0 — notatki w markdown, podgląd następnego slajdu, zegar,
  obsługa dwóch ekranów (`present/player.py:24-160`). Zero pracy dla slajdów prerenderowanych.
- (4, strona live) `LiveScene` z fazy 0 — TCP, `select`, klawisze, animowane cofanie, pętla,
  przerywanie animacji.
- (5, prerender) manim-slides renderuje CE (`slide/manim.py`) i GL (`slide/manimlib.py`).

**Zasada budżetu:** każda faza ma szacunek. Przy przekroczeniu dwukrotnym — zatrzymać się
i zgłosić, zamiast dociągać.

---

## Faza 0 — PoC żywej sceny (zamknięta)

`LiveScene` w manimgl: okno żyje, komendy po TCP z `127.0.0.1`, jeden wątek, `select` z timeoutem
jednej klatki. Dziewięć kryteriów z `SPEC.md`, wszystkie spełnione; trzecia pułapka (kolejność
klient-przed-listenerem) wyszła dopiero w teście w oknie.

Zrobione zaliczkowo w starej fazie 1 i zostaje: strzałki z sekwencją (D1, D2), animowane cofanie
(D3), zapętlenie cue (D9), przerywanie animacji w dowolnej klatce (D10), komendy `next`/`back`.

**Rola w nowym planie:** backend live. Faza 2 dokłada mu tryb headless ze strumieniem klatek.

---

## Faza 1 — fork manim-slides (czeka na próbę w oknie)

**Cel:** manim-slides 5.7.0 wchłonięty do `src/manimcue/slides/`, działający pod CLI `manim-cue`
tak samo jak oryginał. Nic nowego funkcjonalnie — fundament pod fazy 3-5.

**Źródło:** tag `v5.7.0`, commit `305bd8a`, licencja MIT (D13).

**Zakres:** przeniesienie kodu i testów upstreamu, przemianowanie importów `manim_slides` →
`manimcue.slides`, usunięcie `ipython/` i `docs/`, zależności w `pyproject.toml`, demo deck.

**Kryteria akceptacji:**
1. Kod upstreamu w `src/manimcue/slides/`, bez `ipython/` i `docs/`. Zero importów `manim_slides`
   w `src/` i `tests/`.
2. Licencja upstreamu leży obok kodu; `README.md` mówi, skąd kod pochodzi.
3. CLI `manim-cue` z komendami `render`, `present`, `convert`, `wizard`, `init`, `list-scenes`,
   `checkhealth`.
4. Testy upstreamu przeniesione i zielone; pominięte tylko z podanym powodem środowiskowym.
   30 testów fazy 0 nadal zielonych.
5. Demo deck `examples/demo.py` renderuje się w CE i w GL; `manim-cue present` pokazuje go
   z notatkami i podglądem — weryfikacja w oknie przez prelegenta.
6. Sprawdzanie nowej wersji na PyPI wyłączone: porównywałoby fork z manim-slides.

**Budżet:** ~2 h, stop przy 4 h.

**Wynik (2026-10-22, Windows 11):**
- 1-4, 6 — spełnione. `uv run pytest`: **269 passed, 1 skipped** (pominięcie jest upstreamowe:
  `test_present.py:142`, „Fails when running the whole test suite”). Demo deck renderuje się
  w CE i GL (3 slajdy, notatki, pętla w JSON); `manim-cue present` startuje bez tracebacku
  w trybie offscreen.
- 5 — spełnione 2026-10-22 po poprawce: próba prelegenta w oknie wykazała krzaki w notatkach.
  Błąd upstreamu: `PresentationConfig.from_file` czytał JSON kodowaniem systemowym (cp1252),
  a `to_file` zapisuje UTF-8 (`config.py:335`, test `test_notes_round_trip_utf8`). Po poprawce
  prelegent potwierdził notatki i podgląd.
- **Odstępstwo:** Manim CE przypięty do `<0.22` — manim-slides 5.7.0 pada na CE 0.22
  (`SPEC.md`, ustalenia rundy 6). Wsparcie CE 0.22 to osobna praca: przed adapterami CE
  (faza 7), bezwzględnie przed integracją seminarium (faza 8), bo seminarium stoi na CE 0.22.
- Przy okazji naprawione: testy fazy 0 padały na każdej opcji pytesta poza `-q`, bo manimgl
  parsuje `sys.argv` przy imporcie (`tests/conftest.py`).
- Czas pracy nie był mierzony zegarem — ta sama luka co w kryterium 9 fazy 0.

---

## Decyzje przed fazą 2 — rozstrzygnięte (2026-10-22)

Runda 6 wskazała sześć decyzji; prelegent przyjął 2-6 jak w propozycji, na 1 odpowiedział
kliknięciem w okno. Po rundzie 7: D20 (przygotowanie przy wejściu, aktywacja kliknięciem),
D21 (spawn + `Lock` + SharedMemory), D22 (korpus scen) w `SPEC.md`.

**Progi wydajności (decyzja 2):** panel 960×540 ≥ 60 różnych odebranych klatek/s, 1920×1080 ≥ 30,
CPU procesu live w statycznej bezczynności < 5% rdzenia, p95 komenda → odebrana zmieniona klatka
< 100 ms (ciepła sesja). Zimny start raportowany osobno.

**Semantyka warstw (decyzja 4):** źródła ładowane przed wspólnym startem; równe efektywne
długości (po `playback_rate`); slajd kończy wskazana warstwa plikowa albo prelegent; live nie
steruje końcem slajdu; reverse kompozycji ograniczony jawnie.

---

## Faza 2 — strumień klatek z procesu live (zamknięta)

**Cel:** osobny proces GL bez okna → SharedMemory → minimalny odbiornik Qt, z poprawnym czasem
animacji, klatkami granicznymi i zamykaniem. **Bez playera**, bez modelu slajdów, bez CE.

**Pliki:** `src/manimcue/live_worker.py` (target spawn, bootstrap, nadzór; bez importów Manima
i Qt na poziomie modułu), `src/manimcue/frame_buffer.py` (format bloku i kopia pod blokadą; bez
Manima i Qt), `src/manimcue/live_session.py` (właściciel procesu, pamięci i połączenia; API
nieblokujące GUI), `src/manimcue/live_scene.py` (tryb headless obok trybu okna),
`examples/live_receiver.py` (minimalny `QLabel`), sceny `tests/scenes/live_gl.py`, testy.

**Kontrakt:** pełna specyfikacja z rundy 7 — `REVIEW-LOG.md`, „Specyfikacja F2 do przekazania
wykonawcy”: API (`LiveSpec`, `run_worker`, `LiveSession`), bootstrap (spawn, czyste argv,
`Scene(window=None)`, wyłączony zapis filmu, READY po pierwszej klatce), protokół pamięci (D21),
transport (`shutdown`, `frame_seen <id>`, statusy READY/ERROR; parser odróżnia komendę od
przerwania — nieznana komenda nie przerywa cue), zegar (`time.monotonic()`, oczekiwanie przez
`select`, updatery zamrożone między cue, statyczna bezczynność bez renderu), zamykanie (2 s
kooperacyjnie, potem wymuszenie; świeże zasoby po restarcie).

**API (zamknięte 2026-10-22, wspólne dla scen, testów i implementacji):**

```python
# src/manimcue/live_session.py
@dataclass(frozen=True)
class LiveSpec:
    scene_file: str          # ścieżka absolutna do pliku sceny
    scene_name: str          # klasa, podklasa LiveScene
    width: int = 960
    height: int = 540
    fps: int = 60

@dataclass(frozen=True)
class OwnedFrame:
    frame_id: int
    width: int
    height: int
    timestamp: float         # time.monotonic() procesu live w chwili publikacji
    boundary: bool           # klatka graniczna: start, koniec/przerwanie cue, cofnięcie
    pixels: bytes            # RGBA8, wiersze od góry, stride = 4 * width
    def pixel(self, x: int, y: int) -> tuple[int, int, int, int]: ...  # (0, 0) = lewy górny róg

class LiveSession:
    state: str               # "idle" | "starting" | "ready" | "error" | "stopped"
    error: str | None
    def start(self, spec: LiveSpec) -> None: ...
    def poll(self) -> list[str]: ...   # nowe zdarzenia: "READY", "CUE_START <nazwa>",
                                       # "CUE_DONE <nazwa>", "SEQUENCE_END", "ERROR <opis>", "STOPPED"
    def send(self, command: str) -> None: ...
    def try_read_frame(self) -> OwnedFrame | None: ...  # najnowsza nowa klatka albo None
    def request_stop(self) -> None: ...
```

Żadna metoda `LiveSession` nie blokuje (GUI). Potwierdzenie `frame_seen` wysyła sama sesja przy
kopii klatki granicznej. `time.monotonic()` na Windows jest wspólne dla procesów jednej maszyny,
więc znaczniki czasu da się porównywać z czasem odbiornika.

**Kryteria jako testy:** 13 testów z kontraktu (`test_spawn_from_console_entrypoint` …
`test_no_movie_output`) plus pomiar akceptacyjny: progi wydajności z decyzji 2, 30 s prostej
animacji po rozgrzewce, osobne czasy renderu, odczytu GPU, publikacji i kopii odbiornika.
Testy z prawdziwym GL oznaczone `gpu`. Offscreen Qt nie zalicza płynności na projektorze ani
fokusu — to próba prelegenta.

**Wykonawca:** codex (workspace-write) jako jedyny właściciel integracji F2 — części są zależne
(definicje „gotowy”, „przerwany”, „ostatnia klatka”). Sceny korpusu F1/F2: Claude Haiku.
Przegląd, uruchomienie testów i pomiar: Claude.

**Budżet:** ~3 h, raport stanu przy 6 h.

**Wynik (2026-10-22, Windows 11, RTX 4060):**
- `uv run pytest`: testy projektu 80 passed + 1 skip środowiskowy (TeX, niżej); upstream
  slides 240 (1 skip upstreamu). 13 testów kontraktu zielone; korpus: 13 scen zielonych,
  `LiveGLTex` pominięta — scena TeX nie była wykonana na żadnej maszynie. Xfaile zdjęte.
- Pomiar (`live-measurement.json`, Qt offscreen, 30 s po rozgrzewce):

  | | 960×540 | 1920×1080 |
  |---|---|---|
  | klatki opublikowane / odebrane / różne (30 s) | 1800 / 1800 / 1799 | 1796 / 1796 / 1795 |
  | różne odebrane klatki/s | 59,97 (próg ≥ 60·T − 2) | 59,83 (próg ≥ 30·T − 2) |
  | CPU w bezczynności (próg < 5%) | 0% rdzenia | 2,2% |
  | p95 komenda → zmieniona klatka (próg < 100 ms) | 18 ms | 28 ms |
  | render / odczyt GPU / publikacja / kopia odbiornika | 0,6 / 4,7 / 0,2 / 1,6 ms | 0,5 / 7,4 / 0,5 / 3,9 ms |
  | zimny start | 1,8 s (31,7 s w pierwszym pomiarze dnia) | 1,8 s |

- **Próg fps (D26 po rundzie 8):** pierwotne 59,96 przy progu „≥ 60” to granica okna, nie strata —
  każda opublikowana klatka została odebrana. Próg to teraz „≥ fps·T − 2 klatki”; pomiar zamraża
  liczniki z końcem okna i zapisuje surowe liczby. Pierwszy pomiar (29 fps) wyprzedzał poprawkę
  tempa: `select` na Windows zaokrągla timeout w górę do
  ~15,6 ms, tempo trzyma teraz `time.sleep` (`live_scene.py:505`).
- Test `test_clock_skips_missed_deadlines` po poprawce tempa wisiał w nieskończonej pętli
  (fałszywy zegar szedł tylko przez `live_poll`); teraz podmienia też `time.sleep`.
- **TeX nie działa na tej maszynie z manimgl:** manimgl woła `latex -no-pdf`, a pdfTeX z MiKTeX
  24.4 odrzuca tę opcję (`optionError="unknown option"`). Błąd środowiska/upstreamu, nie F2;
  `test_tex_renders` sonduje teraz właściwą kompilację i robi jawny skip (D22).
- Próba w oknie (`examples/live_receiver.py`): sekwencja, cofanie do początku, koniec sekwencji
  i zamknięcie bez tracebacku — z logu. Scena musi być podklasą `LiveScene` z własnego pliku:
  `live_scene.py` ładowany po ścieżce to drugi moduł, a `issubclass` z oryginałem zawodzi.

---

## Faza 3 — model danych slajdu + minimalna kompozycja (aktywna)

**Cel:** slajd deklaruje warstwę live; JSON jest wersjonowany; player rysuje slajd w
`QGraphicsView`, a okno Info pokazuje tę samą kompozycję. Warstwa live pokazuje w F3 miniaturę
(pierwszą klatkę sceny z renderu) — proces live wchodzi w F4. **Bez** procesu live w playerze,
bez fokusu i routingu klawiszy, bez warstw wideo/obrazu i transformacji (F5).

**Deklaracja autorska** — nowe pole `layers` w `BaseSlideConfig`, więc wrapper
(`config.py:202`) od razu robi z niego argument `next_slide`, a zapis i odczyt JSON idą
dotychczasową drogą:

```python
from manimcue.slides import LiveLayer, Slide

self.next_slide(
    notes="...",
    layers=[LiveLayer(scene_file="panels.py", scene_name="NVPanel", rect=(0.55, 0.1, 0.4, 0.4))],
)
self.play(...)  # slajd nadal potrzebuje klipu bazowego (walidator upstreamu, config.py:291)
```

**Model (D24):**
- `LiveLayer`: `scene_file: FilePath`, `scene_name: str`, `rect: (x, y, w, h)` jako ułamki kadru
  slajdu z (0, 0) w lewym górnym rogu (walidacja: w kadrze, w, h > 0), `fps: int = 60`,
  `thumbnail: FilePath | None`. Rozdzielczość procesu live = `rect` × `resolution` prezentacji.
- `PresentationConfig.version: int = 2`; plik bez pola (upstream 5.7.0) czyta się jako zgodny,
  bo `layers` ma wartość domyślną; wersja > 2 → czytelny błąd „nowszy format”.
- Ścieżki warstw rozwiązywane jak `file`/`rev_file` w `from_file` (względem `path.parent.parent`).

**Miniatura (render):** `_save_slides` dla każdej warstwy live uruchamia scenę headless przez
`LiveSession` (osobny proces spawn, więc render CE nie importuje manimgl), bierze pierwszą klatkę
po READY i zapisuje PNG w `slides/files/<Scena>/`. Nazwa z hasha (bajty pliku sceny, nazwa klasy,
rozmiar) — cache jak przy klipach. Błąd sceny live przerywa render z treścią `ERROR`.

**Kompozycja (D25):** `src/manimcue/composition.py` — `SlideComposition(QGraphicsScene)` (rect
sceny = `resolution`, tło `background_color`; element wideo `QGraphicsVideoItem`, element obrazu,
elementy warstw z miniaturą w `rect`) i `SlideView(QGraphicsView)` (dopasowanie `fitInView` przy
resize, tryb proporcji z `--aspect-ratio`). Okno główne i bieżący widok Info to **dwa widoki tej
samej sceny** — zgodność obrazu z konstrukcji. Ochrona przed czarną klatką z `frame_changed`
(`player.py:664`) przechodzi na sink elementu wideo. Podgląd następnego slajdu to osobna
`SlideComposition` z `next_media_player`. Prototyp (Qt 6.12, Windows, real display): dwa widoki,
klip 60 fps — 361 klatek / 6 s, rysowanie elementu mediana 0,38 ms, p95 9 ms.

**`convert` (D23):** prezentacja z warstwą live → jawny błąd z indeksem slajdu i nazwą sceny.
Obraz zastępczy odrzucony: wymagałby kompozycji w każdym konwerterze (HTML, PDF, PPTX).

**Kryteria akceptacji:**
1. JSON upstreamu 5.7.0 (`tests/slides/data/slides/BasicSlide.json`) czyta się bez zmian
   i zapisuje z `version: 2`; plik z `version: 3` → `ValidationError` z komunikatem o nowszym
   formacie.
2. `LiveLayer` odrzuca `rect` poza kadrem, zerowe wymiary i NaN; rozmiar renderu ≥ 1 px.
   Ścieżki warstwy z JSON rozwiązują się względem `path.parent.parent` także z innego CWD.
3. Render CE **i GL** decku z warstwą live daje JSON z warstwą i PNG miniatury; piksele
   miniatury odpowiadają pierwszej klatce sceny (narożniki `LiveGLCorners`). Drugi render bez
   zmian nie nadpisuje miniatury (cache). Błąd sceny warstwy przerywa render z treścią błędu
   i bez JSON. Zawieszone budowanie → `TimeoutError`, bez pozostawionego workera. Znacznik `gpu`.
4. Player offscreen: element warstwy stoi w `rect` (współrzędne sceny) z miniaturą; widok Info
   pokazuje tę samą `QGraphicsScene`; podgląd następnego slajdu zawiera miniaturę jego warstwy;
   piksele dwóch widoków w prostokącie warstwy to miniatura, poza nim — obraz bazowy (`src=`).
   Przejście do prezentacji o innej rozdzielczości zmienia kadr bieżący i podglądu;
   `hide_mouse` działa nad viewportem.
5. Nieprawidłowa klatka wideo w sinku zastąpiona poprzednią, ale tylko poprawną (bez
   rekurencji sygnału przy pustej poprzedniej).
6. `convert`, konwertery użyte z kodu i `copy_to` odrzucają warstwę live z numerem prezentacji,
   slajdu i nazwą sceny.
7. Wszystkie testy upstreamu i F0-F2 nadal zielone.
8. **Próba prelegenta w oknie:** `examples/demo.py` z warstwą live — miniatura w prostokącie
   w obu oknach, resize zachowuje proporcje, przejścia między slajdami bez czarnego mignięcia,
   podgląd następnego slajdu z miniaturą.

**Budżet (po rundzie 8):** ~6 h (model i miniatura ~2 h, player i akceptacja ~4 h), stop
i raport przy 12 h. Start pracy: 2026-10-22 ~14:00.

## Faza 4 — warstwa live w playerze

**Cel:** D20 w jednym oknie. Wejście na slajd z warstwą uruchamia proces, pierwsza klatka
zastępuje miniaturę, kliknięcie warstwy daje jej strzałki, Esc oddaje je playerowi, wyjście ze
slajdu zatrzymuje proces. **Bez** transformacji, wspólnego startu z wideo i wielu warstw
naraz w aktywnym sterowaniu (F5).

**Projekt:**
- `src/manimcue/live_layers.py` — `LiveLayerController`, właściciel sesji warstw bieżącego
  slajdu (runda 8, p. 12: kompozycja nie zna `LiveSession`). Jeden `QTimer` pompuje `poll()`
  i `try_read_frame()` wszystkich sesji, także zatrzymywanych, aż do `STOPPED`; nowa klatka →
  `QImage` (RGBA8888, kopia przez `QPixmap.fromImage`) → `SlideComposition.set_layer_image`.
  Timer stoi, gdy nie ma żadnej sesji.
- **Cykl życia:** `show(slide_config)` z `Player.load_current_slide` i z konstruktora — jedna
  zatwierdzona zmiana slajdu, nie setter indeksu. Ten sam obiekt slajdu (replay, pętla) →
  sesje zostają. Inny slajd → `request_stop()` starych, nowe sesje dla warstw nowego. Ponowne
  wejście = nowa sesja (świeże zasoby, F2). Zamknięcie playera zatrzymuje i odbiera wszystkie.
- **Fokus (D20):** klik w okno główne trafia przez `SlideView.mousePressEvent` + `itemAt` do
  warstwy (albo poza nią → zwolnienie). Widok Info nie aktywuje (podgląd). Aktywna warstwa ma
  obwódkę (`QGraphicsRectItem` w scenie, więc widać ją też w Info). Zwolnienie: Esc, klik poza
  warstwą, zmiana slajdu, `applicationStateChanged` ≠ aktywna, błąd sesji.
- **Router klawiszy** przed `dispatch` w `Player.keyPressEvent` (tam trafiają też klawisze z
  Info): przy aktywnej warstwie Esc zwalnia; klawisze `NEXT`/`PREVIOUS` z konfiguracji →
  `send("next")`/`send("back")`; reszta skrótów playera bez zmian. Komenda idzie tylko do sesji
  w stanie `ready` — klik w trakcie startu nie kolejkuje cue (D20, tabela rundy 7).
- **Błąd sesji:** warstwa zostaje z ostatnim obrazem, obwódka czerwona, treść `ERROR` w logu
  i w tytule okna Info; player działa dalej, sterowanie wraca do playera.

**Kryteria akceptacji:**
1. Wejście na slajd z warstwą: proces startuje, do READY widać miniaturę, potem piksele
   warstwy to pierwsza klatka sceny (korpus `LiveGLCorners` z innym kolorem miniatury).
2. Wyjście ze slajdu: proces odebrany (`mp.active_children()` puste po pompowaniu), ponowne
   wejście tworzy nową `SharedMemory`.
3. Klik w warstwę + `→` wykonuje cue w scenie (zmiana pikseli), indeks slajdu bez zmian;
   Esc, potem `→` zmienia slajd. To samo dla klawiszy przekazanych z Info. Klik poza warstwą
   zwalnia. (`LiveLayerFocus` z korpusu rundy 7.)
4. Klik i `→` przed READY nie wykonują cue po READY.
5. Wyjątek w cue (`LiveGLCueRaises`): czerwona obwódka, błąd w logu, player przechodzi dalej
   strzałkami; zamknięcie bez pozostawionego procesu.
6. Utrata aktywności aplikacji zwalnia warstwę.
7. Testy F0-F3 i upstreamu zielone.
8. **Próba prelegenta:** demo deck, slajd 3 — klik w panel, strzałki sterują rotate → pulse →
   sweep i cofaniem, Esc wraca do slajdów, wyjście i powrót na slajd restartuje panel, płynność
   na ekranie i w Info.

**Budżet:** ~4 h, stop i raport przy 8 h.

## Faza 5 — warstwy pełne

Pozycja, skala, z-order, animowane przesuwanie; gotowość wszystkich źródeł przed wspólnym
startem i pauzą (D17); walidacja równych efektywnych długości.

## Faza 6a — `SceneView` z gotowych klatek

Mobject w scenie-gospodarzu odtwarzający wcześniej przygotowane klatki innej sceny; transformacje
gospodarza działają. Nie zależy od live CE.

## Faza 6b — PoC krokowania sceny podrzędnej

Gospodarz i dziecko postępują równolegle bez rekurencyjnego `play()` (synchroniczny w obu
silnikach). Wynik może zamknąć ten kierunek.

## Faza 7 — live w CE

Najpierw adapter Cairo (zegar, publikacja w trakcie `play()`, przerwanie, `wait()`, wyłączony
cache, brak plików filmu), potem OpenGL jako osobny adapter z własnymi testami. Zgodność z CE 0.22
sprawdzić przed adapterami.

## Faza 8 — integracja z seminarium

Seminarium przechodzi z vendorowanej manim-slides 5.7.0 na fork — wymaga zgodności z CE 0.22.
Panel NV⁻ w scenie czterowidokowej (D9 tamtego planu) jako warstwa live obok trzech
prerenderowanych. Punkt wejścia: `SeminarScene`/`SeminarScene3D` w tamtym `deck/base.py`
(D10 tamtego planu). **Warunek wejścia:** próba na komputerze prelegenta — dwa monitory, fokus.
Do tego czasu nic w seminarium od tego projektu nie zależy (R8 tamtego planu).

## Faza 9 — manimgx (warunkowa)

Wchodzi, gdy manimgx dostanie udokumentowany tryb interaktywny (warunek z D12).

---

## Poza zakresem całego projektu

- Fork albo łatanie Manima (CE, GL, GX). Forkujemy manim-slides, nie Manima.
- Zegar główny i seek warstw, synchronizacja co do klatki (D17).
- Przechwytywanie ekranu / OBS jako architektura.
- Uwierzytelnianie i transport między hostami. Zakres to lokalne `127.0.0.1`.
- Back-pressure i kolejka aplikacyjna.
- `%%manim_slides` w IPythonie i dyrektywa Sphinx — usunięte z forka (D13).
- Dane grupowe i cokolwiek z teorii grup — to jest `groupy`, nie tutaj.
